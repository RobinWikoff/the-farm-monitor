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
METEO_ARCHIVE_BASE = "https://archive-api.open-meteo.com/v1/archive"
OWM_BASE = "https://api.openweathermap.org/data/2.5/weather"

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def _get_api_key() -> str:
    """Return API key from secrets; raise a clear error if missing."""
    try:
        return st.secrets["WEATHER_API_KEY"]
    except (KeyError, FileNotFoundError) as e:
        st.error("⚠️ WEATHER_API_KEY not found in Streamlit secrets. Add it to `.streamlit/secrets.toml`.")
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
        # Open-Meteo ISO strings are already in the requested timezone
        dt = datetime.fromisoformat(t)
        if dt.date() == now_date:
            rows.append({"Hour": dt.hour, "Temperature": round(temp, 1)})

    return pd.DataFrame(rows)


@st.cache_data(ttl=60)   # live temp refreshes more frequently
def fetch_live_temp(api_key: str) -> float:
    """Fetch current feels-like temperature from OpenWeatherMap."""
    params = {"lat": LAT, "lon": LON, "appid": api_key, "units": "imperial"}
    resp = requests.get(OWM_BASE, params=params, timeout=10)
    resp.raise_for_status()
    return round(resp.json()["main"]["feels_like"], 1)


@st.cache_data(ttl=86400)  # historical data changes daily at most
def fetch_historical_band(today: datetime) -> pd.DataFrame:
    """
    Fetch the same calendar day (month/day) across the past HISTORY_YEARS years
    from Open-Meteo Archive API. Returns a DataFrame with columns:
      Hour (int), HistHigh (float), HistLow (float), HistMean (float)
    
    We fetch each past year's matching date as a single-day window, collect
    all hourly apparent_temperature readings, then compute per-hour min/max/mean.
    """
    all_rows = []
    for years_back in range(1, HISTORY_YEARS + 1):
        past_date = today.replace(year=today.year - years_back)
        date_str = past_date.strftime("%Y-%m-%d")
        params = {
            "latitude": LAT,
            "longitude": LON,
            "start_date": date_str,
            "end_date": date_str,
            "hourly": "apparent_temperature",
            "temperature_unit": "fahrenheit",
            "timezone": "America/Denver",
        }
        try:
            resp = requests.get(METEO_ARCHIVE_BASE, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            for t, temp in zip(data["hourly"]["time"], data["hourly"]["apparent_temperature"]):
                if temp is not None:
                    all_rows.append({"Hour": datetime.fromisoformat(t).hour, "Temperature": temp})
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


def build_chart(df: pd.DataFrame, live_temp: float, threshold: float, current_hour: int, hist_band: pd.DataFrame) -> alt.LayerChart:
    """Assemble the Altair line chart with actual/forecast/target layers plus historical band."""
    # Inject live temp for current hour AFTER caching, so cache stays clean
    plot = df.copy()
    plot.loc[plot["Hour"] == current_hour, "Temperature"] = live_temp

    # Status column
    plot["Status"] = plot["Hour"].apply(lambda h: "Actual" if h <= current_hour else "Forecast")

    # Bridge row so line is visually continuous at the current hour
    bridge = plot[plot["Hour"] == current_hour].copy().assign(Status="Forecast")

    # Target line
    target = pd.DataFrame({
        "Hour": range(24),
        "Temperature": [threshold] * 24,
        "Status": ["Target"] * 24,
    })

    full = pd.concat([plot, bridge, target], ignore_index=True)

    x = alt.X("Hour:Q", axis=alt.Axis(labelFontSize=12, titleFontSize=18, labelExpr="datum.value + ':00'", values=list(range(24)), labelAngle=-45))
    y = alt.Y(
        "Temperature:Q",
        scale=alt.Scale(zero=False, padding=60),
        axis=alt.Axis(labelFontSize=16, titleFontSize=18, labelExpr="datum.value + '°F'"),
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
                legend=alt.Legend(orient="bottom-left", labelFontSize=14, title=None),
            ),
            strokeDash=alt.StrokeDash("Status:N", scale=dash_scale),
        )
    )

    # Current-hour dot
    dot = (
        alt.Chart(plot[plot["Hour"] == current_hour])
        .mark_circle(size=450, color="#00f2ff")
        .encode(x=x, y=y)
    )

    # Label helpers (only on actuals to avoid duplicates on target layer)
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
        .mark_text(dy=-25, fontSize=16, fontWeight="bold", color="white")
        .encode(x=x, y=y, text="Lab_Txt")
    )
    lbl_bot = (
        alt.Chart(plot[plot["Lab_Pos"] == "Bottom"])
        .mark_text(dy=25, fontSize=16, fontWeight="bold", color="white", baseline="top")
        .encode(x=x, y=y, text="Lab_Txt")
    )

    # Historical band layers (rendered first so they sit behind everything)
    hist_layers = alt.layer()
    if not hist_band.empty:
        band_x = alt.X("Hour:Q")
        hist_area = (
            alt.Chart(hist_band)
            .mark_area(opacity=0.18, color="#a0c4ff")
            .encode(
                x=band_x,
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
                x=band_x,
                y=alt.Y("HistMean:Q"),
                color=alt.Color(
                    "Status:N",
                    scale=color_scale,
                    legend=alt.Legend(orient="bottom-left", labelFontSize=14, title=None),
                ),
                strokeDash=alt.StrokeDash(
                    "Status:N",
                    scale=dash_scale,
                ),
            )
        )
        hist_layers = hist_area + hist_mean

    return (
        (hist_layers + lines + dot + lbl_top + lbl_bot)
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
        live_temp = fetch_live_temp(api_key)
        hist_band = fetch_historical_band(now_mtn)
    except requests.RequestException as e:
        logger.error("Weather fetch failed: %s", e)
        st.error(f"Could not reach weather API: {e}")
        st.stop()

if df.empty:
    st.warning("No forecast data available for today.")
    st.stop()

current_hour = now_mtn.hour

# Metrics (compute AFTER we know live_temp so current hour is accurate)
actuals = df[df["Hour"] <= current_hour].copy()
actuals.loc[actuals["Hour"] == current_hour, "Temperature"] = live_temp
hi = actuals["Temperature"].max()
lo = actuals["Temperature"].min()

m1, m2, m3 = st.columns(3)
m1.metric("Feels Like Now", f"{live_temp}°F")
m2.metric("Today's High (Feels Like)", f"{hi}°F")
m3.metric("Today's Low (Feels Like)", f"{lo}°F")
st.caption("🌡️ All temperatures are *feels like* (apparent temperature), accounting for wind chill and humidity.")

# Status banner
forecast_future = df[df["Hour"] >= current_hour].copy()
forecast_future.loc[forecast_future["Hour"] == current_hour, "Temperature"] = live_temp
render_status_banner(live_temp, threshold, forecast_future, mode)

# Chart
st.altair_chart(build_chart(df, live_temp, threshold, current_hour, hist_band), use_container_width=True)

# Roadmap
st.write("---")
st.subheader("🚀 Features Coming Soon")
col1, col2 = st.columns(2)
with col1:
    st.markdown("""
    **🌨️ Precipitation Tracker**
    * Real-time Rain/Snow probability.
    * Hourly accumulation forecasts.
    """)
with col2:
    st.markdown("""
    **🌬️ Summer Optimization**
    * **AM:** Too Warm, Time to Close the Windows.
    * **PM:** Cool Enough, Time to Open the Windows.
    """)
