import streamlit as st
import requests
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import pytz
import logging

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
LAT = "40.3720"
LON = "-105.0579"
LOCAL_TZ = pytz.timezone("US/Mountain")
HISTORY_YEARS = 5

THRESHOLDS = {"Winter (Warming Focus)": 65.0, "Summer (Cooling Focus)": 70.0}

METEO_URL = (
    f"https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}&longitude={LON}"
    f"&hourly=apparent_temperature"
    f"&temperature_unit=fahrenheit"
    f"&timezone=auto"
)
OWM_BASE = "https://api.openweathermap.org/data/2.5/weather"
VC_BASE = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def _get_api_key() -> str:
    """Return OWM API key from secrets."""
    try:
        return st.secrets["WEATHER_API_KEY"]
    except (KeyError, FileNotFoundError):
        st.error("⚠️ WEATHER_API_KEY not found in Streamlit secrets. Add it to `.streamlit/secrets.toml`.")
        st.stop()


def _get_vc_api_key() -> str:
    """Return Visual Crossing API key from secrets."""
    try:
        return st.secrets["VISUAL_CROSSING_API_KEY"]
    except (KeyError, FileNotFoundError):
        st.error("⚠️ VISUAL_CROSSING_API_KEY not found in Streamlit secrets. Add it to `.streamlit/secrets.toml`.")
        st.stop()


@st.cache_data(ttl=300)
def fetch_forecast() -> pd.DataFrame:
    """
    Fetch today's hourly apparent-temperature forecast from Open-Meteo.
    Returns a DataFrame with columns: Hour (int), Temperature (float).
    Open-Meteo returns local time when timezone=auto, so NO tz conversion needed.
    """
    resp = requests.get(METEO_URL, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    now_date = datetime.now(LOCAL_TZ).date()
    rows = []
    for t, temp in zip(data["hourly"]["time"], data["hourly"]["apparent_temperature"]):
        dt = datetime.fromisoformat(t)
        if dt.date() == now_date:
            rows.append({"Hour": dt.hour, "Temperature": round(temp, 1)})

    return pd.DataFrame(rows)


@st.cache_data(ttl=60)
def fetch_live_temp(api_key: str) -> tuple[float, str, str]:
    """Fetch current feels-like temperature from OpenWeatherMap.
    Returns (feels_like, station_name, station_id).
    """
    params = {"lat": LAT, "lon": LON, "appid": api_key, "units": "imperial"}
    resp = requests.get(OWM_BASE, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    feels_like = round(data["main"]["feels_like"], 1)
    station_name = data.get("name", "Unknown")
    station_id = str(data.get("id", "N/A"))
    return feels_like, station_name, station_id


@st.cache_data(ttl=86400)
def fetch_historical_band(today: datetime, vc_api_key: str) -> pd.DataFrame:
    """
    Fetch the same calendar day (month/day) across the past HISTORY_YEARS years
    using the Visual Crossing Timeline API — a single request per year, with
    feelslike as the apparent temperature equivalent.
    Returns a DataFrame with columns: Hour (int), HistHigh (float), HistLow (float), HistMean (float)
    """
    today_naive = today.replace(tzinfo=None)
    all_rows = []

    for years_back in range(1, HISTORY_YEARS + 1):
        try:
            past_date = today_naive.replace(year=today_naive.year - years_back)
        except ValueError:
            past_date = today_naive.replace(month=2, day=28, year=today_naive.year - years_back)
        date_str = past_date.strftime("%Y-%m-%d")
        location = f"{LAT},{LON}"
        url = f"{VC_BASE}/{location}/{date_str}/{date_str}"
        params = {
            "unitGroup": "us",
            "include": "hours",
            "elements": "datetime,feelslike",
            "key": vc_api_key,
            "contentType": "json",
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for day in data.get("days", []):
                for hour in day.get("hours", []):
                    temp = hour.get("feelslike")
                    dt_str = hour.get("datetime", "")   # format: "HH:mm:ss"
                    if temp is not None and dt_str:
                        hour_int = int(dt_str.split(":")[0])
                        all_rows.append({"Hour": hour_int, "Temperature": temp})
        except requests.RequestException as e:
            logger.warning("Historical fetch failed for %s: %s", date_str, e)
            continue

    if not all_rows:
        return pd.DataFrame(columns=["Hour", "HistHigh", "HistLow", "HistMean"])

    hist_df = pd.DataFrame(all_rows)
    band = (
        hist_df.groupby("Hour")["Temperature"]
        .agg(HistHigh="max", HistLow="min", HistMean="mean")
        .reset_index()
    )
    band["HistHigh"] = band["HistHigh"].round(1)
    band["HistLow"] = band["HistLow"].round(1)
    band["HistMean"] = band["HistMean"].round(1)
    return band


def get_temp_trend(df: pd.DataFrame, live_temp: float, current_hour: int) -> tuple[float | None, str | None]:
    """
    Compute the 1-hour temperature delta for the trend indicator.
    Compares live_temp at current_hour against the forecast value at current_hour - 1.
    Returns (delta, since_label) or (None, None) if prior hour data is unavailable.
    """
    if current_hour == 0:
        return None, None
    prior_hour = current_hour - 1
    prior_rows = df[df["Hour"] == prior_hour]
    if prior_rows.empty:
        return None, None
    prior_temp = prior_rows.iloc[0]["Temperature"]
    delta = round(live_temp - prior_temp, 1)
    since_label = f"since {prior_hour:02d}:00"
    return delta, since_label


def build_chart(df: pd.DataFrame, live_temp: float, threshold: float, current_hour: int, hist_band: pd.DataFrame) -> alt.LayerChart:
    """Assemble the Altair line chart with actual/forecast/target layers plus historical band."""
    plot = df.copy()
    plot.loc[plot["Hour"] == current_hour, "Temperature"] = live_temp

    plot["Status"] = plot["Hour"].apply(lambda h: "Actual" if h <= current_hour else "Forecast")

    bridge = plot[plot["Hour"] == current_hour].copy().assign(Status="Forecast")

    target = pd.DataFrame({
        "Hour": range(24),
        "Temperature": [threshold] * 24,
        "Status": ["Target"] * 24,
    })

    full = pd.concat([plot, bridge, target], ignore_index=True)

    x = alt.X("Hour:Q", axis=alt.Axis(labelFontSize=11, titleFontSize=14, labelExpr="datum.value + ':00'", values=list(range(24)), labelAngle=-45))
    y = alt.Y(
        "Temperature:Q",
        scale=alt.Scale(zero=False, padding=40),
        axis=alt.Axis(labelFontSize=13, titleFontSize=14, labelExpr="datum.value + '°F'"),
    )

    color_scale = alt.Scale(
        domain=["Actual", "Forecast", "Target", "Hist Avg (5yr)"],
        range=["#00f2ff", "#ffffff", "#32CD32", "#a0c4ff"],
    )
    dash_scale = alt.Scale(
        domain=["Actual", "Forecast", "Target", "Hist Avg (5yr)"],
        range=[[0], [5, 5], [8, 4], [3, 3]],
    )

    lines = (
        alt.Chart(full)
        .mark_line(strokeWidth=4)
        .encode(
            x=x,
            y=y,
            color=alt.Color(
                "Status:N",
                scale=color_scale,
                legend=alt.Legend(
                    orient="bottom",
                    labelFontSize=12,
                    title=None,
                    columns=2,
                    columnPadding=20,
                    rowPadding=6,
                ),
            ),
            strokeDash=alt.StrokeDash("Status:N", scale=dash_scale, legend=None),
        )
    )

    dot = (
        alt.Chart(plot[plot["Hour"] == current_hour])
        .mark_circle(size=450, color="#00f2ff")
        .encode(x=x, y=y)
    )

    actuals = plot[plot["Status"] == "Actual"]
    hi = actuals["Temperature"].max()
    lo = actuals["Temperature"].min()
    first_hi_h = actuals.loc[actuals["Temperature"] == hi, "Hour"].iloc[0]
    first_lo_h = actuals.loc[actuals["Temperature"] == lo, "Hour"].iloc[0]

    def label_cfg(row):
        if row["Hour"] == current_hour:
            return ("Top", f"{row['Temperature']}°F")
        if row["Hour"] == first_hi_h:
            return ("Top", f"{row['Temperature']}°F")
        if row["Hour"] == first_lo_h:
            return ("Bottom", f"{row['Temperature']}°F")
        return ("None", "")

    plot[["Lab_Pos", "Lab_Txt"]] = plot.apply(lambda r: pd.Series(label_cfg(r)), axis=1)

    lbl_top = (
        alt.Chart(plot[plot["Lab_Pos"] == "Top"])
        .mark_text(dy=-22, fontSize=13, fontWeight="bold", color="white")
        .encode(x=x, y=y, text="Lab_Txt")
    )
    lbl_bot = (
        alt.Chart(plot[plot["Lab_Pos"] == "Bottom"])
        .mark_text(dy=22, fontSize=13, fontWeight="bold", color="white", baseline="top")
        .encode(x=x, y=y, text="Lab_Txt")
    )

    if not hist_band.empty:
        hist_area = (
            alt.Chart(hist_band)
            .mark_area(opacity=0.18, color="#a0c4ff")
            .encode(
                x=alt.X("Hour:Q"),
                y=alt.Y("HistLow:Q", title=""),
                y2=alt.Y2("HistHigh:Q"),
                tooltip=[
                    alt.Tooltip("Hour:Q", title="Hour"),
                    alt.Tooltip("HistHigh:Q", title="Hist High °F"),
                    alt.Tooltip("HistLow:Q", title="Hist Low °F"),
                    alt.Tooltip("HistMean:Q", title="Hist Mean °F"),
                ],
            )
        )
        hist_mean = (
            alt.Chart(hist_band.assign(Status="Hist Avg (5yr)"))
            .mark_line(strokeWidth=2, opacity=0.65)
            .encode(
                x=alt.X("Hour:Q"),
                y=alt.Y("HistMean:Q"),
                color=alt.Color(
                    "Status:N",
                    scale=color_scale,
                    legend=alt.Legend(
                        orient="bottom",
                        labelFontSize=12,
                        title=None,
                        columns=2,
                        columnPadding=20,
                        rowPadding=6,
                    ),
                ),
                strokeDash=alt.StrokeDash(
                    "Status:N",
                    scale=dash_scale,
                    legend=None,
                ),
            )
        )
        chart = (hist_area + hist_mean + lines + dot + lbl_top + lbl_bot)
    else:
        chart = (lines + dot + lbl_top + lbl_bot)

    return (
        chart
        .properties(height=500)
        .configure_legend(fillColor="#1e1e1e", padding=10)
    )


def render_status_banner(live_temp: float, threshold: float, forecast_future: pd.DataFrame, mode: str) -> None:
    """Show contextual warming/cooling status banner."""
    if "Winter" in mode:
        if live_temp >= threshold:
            st.success(f"✅ Above target ({threshold}°F). House warming active.")
        else:
            hits = forecast_future[forecast_future["Temperature"] >= threshold]
            if not hits.empty:
                st.info(f"⏳ Warming: Reaching {threshold}°F at {hits.iloc[0]['Hour']}:00")
            else:
                st.warning(f"❄️ Alert: Remaining below {threshold}°F today.")
    else:
        if live_temp <= threshold:
            st.success(f"✅ Below target ({threshold}°F). Open windows.")
        else:
            hits = forecast_future[forecast_future["Temperature"] <= threshold]
            if not hits.empty:
                st.info(f"🌡️ Cooling: Dropping to {threshold}°F at {hits.iloc[0]['Hour']}:00")
            else:
                st.warning(f"🔥 Alert: Staying above {threshold}°F today.")


# ---------------------------------------------------------------------------
# APP
# ---------------------------------------------------------------------------
st.set_page_config(page_title="The Farm", page_icon="🏔️", layout="wide")
st.title("The Farm: How's the Weather?")

now_mtn = datetime.now(LOCAL_TZ)
st.markdown(f"**Loveland, CO** | `{now_mtn.strftime('%H:%M:%S')}`")

# Sidebar
st.sidebar.title("Settings")
mode = st.sidebar.selectbox("Monitoring Mode", list(THRESHOLDS.keys()))
threshold = THRESHOLDS[mode]

# Fetch data
api_key = _get_api_key()
with st.spinner("Fetching latest weather data…"):
    try:
        df = fetch_forecast()
        live_temp, owm_station_name, owm_station_id = fetch_live_temp(api_key)
        vc_api_key = _get_vc_api_key()
        hist_band = fetch_historical_band(now_mtn, vc_api_key)
    except requests.RequestException as e:
        logger.error("Weather fetch failed: %s", e)
        st.error(f"Could not reach weather API: {e}")
        st.stop()

if df.empty:
    st.warning("No forecast data available for today.")
    st.stop()

current_hour = now_mtn.hour

# Metrics
actuals = df[df["Hour"] <= current_hour].copy()
actuals.loc[actuals["Hour"] == current_hour, "Temperature"] = live_temp
hi = actuals["Temperature"].max()
lo = actuals["Temperature"].min()

# 1-hour trend delta for "Feels Like Now"
temp_delta, since_label = get_temp_trend(df, live_temp, current_hour)
if temp_delta is not None:
    delta_str = f"{temp_delta:+.1f}°F {since_label}"
else:
    delta_str = None

m1, m2, m3 = st.columns(3)
m1.metric(
    "Feels Like Now",
    f"{live_temp}°F",
    delta=delta_str,
    delta_color="normal",   # green = warmer, red = cooler
)
m2.metric("Today's High (Feels Like)", f"{hi}°F")
m3.metric("Today's Low (Feels Like)", f"{lo}°F")
st.caption("🌡️ All temperatures are *feels like* (apparent temperature), accounting for wind chill, humidity, and sun warmth.")

# Status banner
forecast_future = df[df["Hour"] >= current_hour].copy()
forecast_future.loc[forecast_future["Hour"] == current_hour, "Temperature"] = live_temp
render_status_banner(live_temp, threshold, forecast_future, mode)

# Chart
st.altair_chart(build_chart(df, live_temp, threshold, current_hour, hist_band), width="stretch")

# Data Sources
st.write("---")
with st.expander("📡 About the Data Sources"):
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("""
        **🌐 Open-Meteo** *(Hourly Forecast)*

        Open-Meteo blends multiple global weather models. For forecasts it uses:
        - **NOAA's GFS (Global Forecast System)**, updated every 6 hours
        - Interpolated for coordinates `40.3720°N, 105.0579°W` at ~2.5 km grid resolution

        This is **not** a single local weather station — it's a gridded model estimate.

        **📅 Visual Crossing** *(5-Year Historical Band)*

        The shaded historical band is sourced from Visual Crossing's Timeline API, which pulls from:
        - NWS/NOAA weather station observations
        - METAR airport reports and global reanalysis data
        - Blended for accuracy at the requested coordinates
        """)
    with col_b:
        st.markdown(f"""
        **🏢 OpenWeatherMap** *(Live "Feels Like" Temperature)*

        OWM aggregates data from multiple sources near your location:
        - NWS (National Weather Service) reporting stations
        - METAR airport observation data (likely **KFNL** — Fort Collins/Loveland Airport)
        - Citizen/personal weather stations in the network

        **Resolved station:** `{owm_station_name}` (OWM ID: `{owm_station_id}`)
        The live temp refreshes every **60 seconds**.
        """)
    st.caption("💡 Because both sources use gridded or blended models, readings may differ slightly from a backyard weather station at The Farm's exact location.")

# Roadmap
with st.expander("🚀 Features Coming Soon"):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **🌨️ Precipitation Tracker**
        * Real-time Rain/Snow probability.
        * Hourly accumulation forecasts.

        **💧 Humidity**
        * Current relative humidity.
        * Hourly forecast trend.
        * Dew point tracking.

        **🌬️ Wind**
        * Now, Min & Max speeds.
        * Forecasted gusts.
        * Direction (compass).
        * Change in direction over time *(local unit: Corgi Spins 🐕)*.

        **🌅 Sunrise / Sunset**
        * Today's exact sunrise & sunset times.
        * Golden hour window.
        * Daylight duration & change from yesterday.

        **☀️ Brightness**
        * Cloud cover percentage & trend.
        * UV Index with exposure guidance.
        """)
    with col2:
        st.markdown("""
        **🌬️ Summer Optimization**
        * **AM:** Too Warm, Time to Close the Windows.
        * **PM:** Cool Enough, Time to Open the Windows.

        **🌫️ Air Quality Index (AQI)**
        * Current AQI with health category label.
        * Primary pollutant breakdown.
        * Hourly AQI forecast trend.

        **🐱 Kitty Comfort Thresholds**
        * *Winter:* Warm enough outside? (above 32°F) · No big wind? · No rain or snow?
        * *Summer:* Not too hot? (below 80°F) · No big wind? · No rain?

        **🌡️ Real vs. Feels Like Toggle**
        * Settings panel toggle to switch between actual air temperature and apparent (feels like) temperature across all readings and the chart.
        """)
