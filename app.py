import streamlit as st
import requests
import pandas as pd
import altair as alt
from datetime import datetime
import pytz
import logging

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
LAT = "40.3720"
LON = "-105.0579"
LOCAL_TZ = pytz.timezone("US/Mountain")

THRESHOLDS = {"Winter (Warming Focus)": 65.0, "Summer (Cooling Focus)": 70.0}

METEO_URL = (
    f"https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}&longitude={LON}"
    f"&hourly=apparent_temperature"
    f"&temperature_unit=fahrenheit"
    f"&timezone=auto"
)
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


def build_chart(df: pd.DataFrame, live_temp: float, threshold: float, current_hour: int) -> alt.LayerChart:
    """Assemble the Altair line chart with actual/forecast/target layers."""
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

    x = alt.X("Hour:Q", axis=alt.Axis(labelFontSize=16, titleFontSize=18, labelExpr="datum.value + ':00'"))
    y = alt.Y(
        "Temperature:Q",
        scale=alt.Scale(zero=False, padding=60),
        axis=alt.Axis(labelFontSize=16, titleFontSize=18, labelExpr="datum.value + '°F'"),
    )

    color_scale = alt.Scale(
        domain=["Actual", "Forecast", "Target"],
        range=["#00f2ff", "#ffffff", "#32CD32"],
    )
    dash_scale = alt.Scale(
        domain=["Actual", "Forecast", "Target"],
        range=[[0], [5, 5], [8, 4]],
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

    return (lines + dot + lbl_top + lbl_bot).properties(height=500).configure_legend(
        fillColor="#1e1e1e", padding=10
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
m1.metric("Current (Feels)", f"{live_temp}°F")
m2.metric("Today's High", f"{hi}°F")
m3.metric("Today's Low", f"{lo}°F")

# Status banner
forecast_future = df[df["Hour"] >= current_hour].copy()
forecast_future.loc[forecast_future["Hour"] == current_hour, "Temperature"] = live_temp
render_status_banner(live_temp, threshold, forecast_future, mode)

# Chart
st.altair_chart(build_chart(df, live_temp, threshold, current_hour), use_container_width=True)

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
