import streamlit as st
import requests
import pandas as pd
import altair as alt
from datetime import datetime
import pytz
import logging
import math
import os

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
LAT = "40.3720"
LON = "-105.0579"
LOCAL_TZ = pytz.timezone("US/Mountain")
HISTORY_YEARS = 5

THRESHOLDS = {"Winter (Warming Focus)": 65.0, "Summer (Cooling Focus)": 70.0}

VC_BASE = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def wind_degree_to_cardinal(degrees: float | None) -> str:
    if degrees is None:
        return "Unknown"
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int(((degrees + 22.5) % 360) / 45)
    return dirs[idx]


def _get_vc_api_key() -> str:
    """Return Visual Crossing API key from Streamlit secrets or environment."""
    env_key = os.getenv("VISUAL_CROSSING_API_KEY")
    if env_key:
        return env_key
    try:
        return st.secrets["VISUAL_CROSSING_API_KEY"]
    except (KeyError, FileNotFoundError):
        st.error(
            "⚠️ VISUAL_CROSSING_API_KEY not found in Streamlit secrets. Add it to `.streamlit/secrets.toml`."
        )
        st.stop()


def _build_dev_sample_payload(
    now_mtn: datetime,
) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Create deterministic sample weather payload for local dev without external API calls."""
    rows = []
    hist_rows = []

    for h in range(24):
        base = 54.0 + 10.0 * math.sin((h - 6) * math.pi / 12.0)
        feels = base - 1.5 + 1.2 * math.sin(h * math.pi / 6.0)
        wind_speed = max(0.0, 9.0 + 4.0 * math.sin((h + 2) * math.pi / 12.0))
        precip = max(0.0, 0.08 * math.sin((h - 3) * math.pi / 8.0))
        precip_prob = max(0.0, min(100.0, 55.0 + 35.0 * math.sin((h - 2) * math.pi / 8.0)))
        humidity = max(10.0, min(100.0, 62.0 + 22.0 * math.sin((h + 1) * math.pi / 10.0)))
        snow = precip if base <= 32.0 else 0.0
        wind_deg = (h * 15) % 360

        rows.append(
            {
                "Hour": h,
                "Actual": round(base, 1),
                "FeelsLike": round(feels, 1),
                "WindSpeed": round(wind_speed, 1),
                "WindDeg": round(wind_deg, 1),
                "WindDir": wind_degree_to_cardinal(wind_deg),
                "PrecipIn": round(precip, 2),
                "PrecipProb": round(precip_prob, 1),
                "Humidity": round(humidity, 1),
                "SnowIn": round(snow, 2),
            }
        )

        hist_rows.append(
            {
                "Hour": h,
                "ActualHigh": round(base + 6.5, 1),
                "ActualLow": round(base - 6.0, 1),
                "ActualMean": round(base + 0.3, 1),
                "FeelsLikeHigh": round(feels + 6.0, 1),
                "FeelsLikeLow": round(feels - 6.2, 1),
                "FeelsLikeMean": round(feels + 0.2, 1),
                "WindSpeedHigh": round(wind_speed + 3.5, 1),
                "WindSpeedLow": round(max(0.0, wind_speed - 3.0), 1),
                "WindSpeedMean": round(wind_speed + 0.4, 1),
            }
        )

    df = pd.DataFrame(rows)
    hist_band = pd.DataFrame(hist_rows)

    current_hour = now_mtn.hour
    live_row = df[df["Hour"] == current_hour].iloc[0]
    live_temp = {
        "Actual": float(live_row["Actual"]),
        "FeelsLike": float(live_row["FeelsLike"]),
        "WindSpeed": float(live_row["WindSpeed"]),
        "WindDeg": float(live_row["WindDeg"]),
        "WindDir": str(live_row["WindDir"]),
        "PrecipIn": float(live_row["PrecipIn"]),
        "PrecipProb": float(live_row["PrecipProb"]),
        "Humidity": float(live_row["Humidity"]),
        "SnowIn": float(live_row["SnowIn"]),
    }

    return df, live_temp, hist_band


def _as_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


@st.cache_data(ttl=600)
def fetch_forecast_and_current(vc_api_key: str) -> tuple[pd.DataFrame, dict]:
    """
    Fetch today's hourly forecast AND current conditions from
    Visual Crossing Timeline API in a single call.
    Returns (forecast_df, live_temp) where forecast_df has columns: Hour (int), Actual (float), FeelsLike (float).
    """
    location = f"{LAT},{LON}"
    url = f"{VC_BASE}/{location}/today"
    params = {
        "unitGroup": "us",
        "include": "hours,current",
        "elements": "datetime,temp,feelslike,windspeed,wdir,precip,precipprob,humidity,snow",
        "key": vc_api_key,
        "contentType": "json",
        "timezone": "America/Denver",
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    # Hourly forecast
    rows = []
    for day in data.get("days", []):
        for hour in day.get("hours", []):
            actual = hour.get("temp")
            feelslike = hour.get("feelslike")
            windspeed = hour.get("windspeed")
            winddeg = hour.get("wdir")
            precip = hour.get("precip")
            precipprob = hour.get("precipprob")
            humidity = hour.get("humidity")
            snow = hour.get("snow")
            dt_str = hour.get("datetime", "")  # "HH:mm:ss"
            # Only require temp/feelslike; optional fields get None if missing
            if dt_str and actual is not None and feelslike is not None:
                hour_int = int(dt_str.split(":")[0])
                rows.append(
                    {
                        "Hour": hour_int,
                        "Actual": round(actual, 1),
                        "FeelsLike": round(feelslike, 1),
                        "WindSpeed": round(windspeed, 1) if windspeed is not None else None,
                        "WindDeg": round(winddeg, 1) if winddeg is not None else None,
                        "WindDir": wind_degree_to_cardinal(winddeg),
                        "PrecipIn": round(precip, 2) if precip is not None else None,
                        "PrecipProb": round(precipprob, 1) if precipprob is not None else None,
                        "Humidity": round(humidity, 1) if humidity is not None else None,
                        "SnowIn": round(snow, 2) if snow is not None else None,
                    }
                )
    forecast_df = pd.DataFrame(rows)

    # Current conditions
    current = data.get("currentConditions", {})
    live_actual = current.get("temp")
    live_feelslike = current.get("feelslike")
    live_windspeed = current.get("windspeed")
    live_winddeg = current.get("wdir")
    live_precip = current.get("precip")
    live_precipprob = current.get("precipprob")
    live_humidity = current.get("humidity")
    live_snow = current.get("snow")
    if live_actual is None and not forecast_df.empty:
        live_actual = forecast_df.iloc[-1]["Actual"]
    if live_feelslike is None and not forecast_df.empty:
        live_feelslike = forecast_df.iloc[-1]["FeelsLike"]
    if live_windspeed is None and not forecast_df.empty:
        live_windspeed = forecast_df.iloc[-1]["WindSpeed"]
    if live_winddeg is None and not forecast_df.empty:
        live_winddeg = forecast_df.iloc[-1]["WindDeg"]
    if live_precip is None and not forecast_df.empty:
        live_precip = forecast_df.iloc[-1]["PrecipIn"]
    if live_precipprob is None and not forecast_df.empty:
        live_precipprob = forecast_df.iloc[-1]["PrecipProb"]
    if live_humidity is None and not forecast_df.empty:
        live_humidity = forecast_df.iloc[-1]["Humidity"]
    if live_snow is None and not forecast_df.empty:
        live_snow = forecast_df.iloc[-1]["SnowIn"]

    live_temp = {
        "Actual": round(live_actual, 1) if live_actual is not None else None,
        "FeelsLike": round(live_feelslike, 1) if live_feelslike is not None else None,
        "WindSpeed": round(live_windspeed, 1) if live_windspeed is not None else None,
        "WindDeg": round(live_winddeg, 1) if live_winddeg is not None else None,
        "WindDir": wind_degree_to_cardinal(live_winddeg) if live_winddeg is not None else "Unknown",
        "PrecipIn": round(live_precip, 2) if live_precip is not None else None,
        "PrecipProb": round(live_precipprob, 1) if live_precipprob is not None else None,
        "Humidity": round(live_humidity, 1) if live_humidity is not None else None,
        "SnowIn": round(live_snow, 2) if live_snow is not None else None,
    }

    return forecast_df, live_temp


@st.cache_data(ttl=604800)  # 7-day TTL — historical data barely changes
def fetch_historical_band(today_str: str, vc_api_key: str) -> pd.DataFrame:
    """
    Fetch the same calendar day (month/day) across the past HISTORY_YEARS years
    using the Visual Crossing Timeline API — one request per year.
    today_str format: YYYY-MM-DD — string keeps cache key stable all day.
    Returns a DataFrame with columns: Hour (int), HistHigh (float), HistLow (float), HistMean (float)
    """
    today = datetime.strptime(today_str, "%Y-%m-%d")
    all_rows = []

    for years_back in range(1, HISTORY_YEARS + 1):
        try:
            past_date = today.replace(year=today.year - years_back)
        except ValueError:
            past_date = today.replace(month=2, day=28, year=today.year - years_back)
        date_str = past_date.strftime("%Y-%m-%d")
        location = f"{LAT},{LON}"
        url = f"{VC_BASE}/{location}/{date_str}/{date_str}"
        params = {
            "unitGroup": "us",
            "include": "hours",
            "elements": "datetime,temp,feelslike,windspeed",
            "key": vc_api_key,
            "contentType": "json",
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for day in data.get("days", []):
                for hour in day.get("hours", []):
                    actual = hour.get("temp")
                    feelslike = hour.get("feelslike")
                    windspeed = hour.get("windspeed")
                    dt_str = hour.get("datetime", "")  # format: "HH:mm:ss"
                    if (
                        actual is not None
                        and feelslike is not None
                        and windspeed is not None
                        and dt_str
                    ):
                        hour_int = int(dt_str.split(":")[0])
                        all_rows.append(
                            {
                                "Hour": hour_int,
                                "Actual": actual,
                                "FeelsLike": feelslike,
                                "WindSpeed": windspeed,
                            }
                        )
        except requests.RequestException as e:
            status_code = getattr(getattr(e, "response", None), "status_code", None)
            if status_code == 429:
                logger.warning(
                    "Historical fetch rate-limited on %s; stopping further yearly requests.",
                    date_str,
                )
                break
            logger.warning("Historical fetch failed for %s: %s", date_str, e)
            continue

    if not all_rows:
        return pd.DataFrame(
            columns=[
                "Hour",
                "ActualHigh",
                "ActualLow",
                "ActualMean",
                "FeelsLikeHigh",
                "FeelsLikeLow",
                "FeelsLikeMean",
            ]
        )

    hist_df = pd.DataFrame(all_rows)
    band = (
        hist_df.groupby("Hour")
        .agg(
            ActualHigh=("Actual", "max"),
            ActualLow=("Actual", "min"),
            ActualMean=("Actual", "mean"),
            FeelsLikeHigh=("FeelsLike", "max"),
            FeelsLikeLow=("FeelsLike", "min"),
            FeelsLikeMean=("FeelsLike", "mean"),
            WindSpeedHigh=("WindSpeed", "max"),
            WindSpeedLow=("WindSpeed", "min"),
            WindSpeedMean=("WindSpeed", "mean"),
        )
        .reset_index()
    )

    for c in [
        "ActualHigh",
        "ActualLow",
        "ActualMean",
        "FeelsLikeHigh",
        "FeelsLikeLow",
        "FeelsLikeMean",
        "WindSpeedHigh",
        "WindSpeedLow",
        "WindSpeedMean",
    ]:
        band[c] = band[c].round(1)

    return band


def get_temp_trend(
    df: pd.DataFrame, live_temp: float, current_hour: int
) -> tuple[float | None, str | None]:
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


def build_chart(
    df: pd.DataFrame,
    live_temp: float,
    threshold: float,
    current_hour: int,
    hist_band: pd.DataFrame,
) -> alt.LayerChart:
    """Assemble the Altair line chart with actual/forecast/target layers plus historical band."""
    plot = df.copy()
    plot.loc[plot["Hour"] == current_hour, "Temperature"] = live_temp

    plot["Status"] = (
        plot["Hour"].apply(lambda h: "Actual" if h <= current_hour else "Forecast").astype(object)
    )

    bridge = plot[plot["Hour"] == current_hour].copy().assign(Status="Forecast")

    target = pd.DataFrame(
        {
            "Hour": range(24),
            "Temperature": [threshold] * 24,
            "Status": ["Target"] * 24,
        }
    )

    full = pd.concat([plot, bridge, target], ignore_index=True)

    x = alt.X(
        "Hour:Q",
        axis=alt.Axis(
            labelFontSize=11,
            titleFontSize=14,
            labelExpr="datum.value + ':00'",
            values=list(range(24)),
            labelAngle=-45,
        ),
    )
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
        chart = hist_area + hist_mean + lines + dot + lbl_top + lbl_bot
    else:
        chart = lines + dot + lbl_top + lbl_bot

    return chart.properties(height=500).configure_legend(fillColor="#1e1e1e", padding=10)


def render_status_banner(
    live_temp: float, threshold: float, forecast_future: pd.DataFrame, mode: str
) -> None:
    """Show contextual warming/cooling status banner."""
    is_winter = "Winter" in mode
    delta = round(live_temp - threshold, 1)

    if is_winter:
        if live_temp >= threshold:
            st.success(
                f"It's warm outside; maybe wear shorts! {live_temp}°F (threshold {threshold}°F). -- Cool Months"
            )
        else:
            hits = forecast_future[forecast_future["Temperature"] >= threshold]
            if not hits.empty:
                forecast_hour = int(hits.iloc[0]["Hour"])
                st.info(
                    f"It's cool now and will be warm later: {live_temp}°F, warming to {threshold}°F by {forecast_hour:02d}:00. Delta {delta:+.1f}°F. -- Cool Months"
                )
            else:
                st.warning(
                    f"It's cool now and won't be warm later: {live_temp}°F is below {threshold}°F. -- Cool Months"
                )
    else:
        if live_temp <= threshold:
            st.success(
                f"It's cool outside! Windows Open: {live_temp}°F (threshold {threshold}°F). Cooling target met. -- Warm Months"
            )
        else:
            hits = forecast_future[forecast_future["Temperature"] <= threshold]
            if not hits.empty:
                forecast_hour = int(hits.iloc[0]["Hour"])
                st.info(
                    f"Its' warm out and will be cool later: {live_temp}°F, cooling to {threshold}°F by {forecast_hour:02d}:00. Delta {delta:+.1f}°F. -- Warm Months"
                )
            else:
                st.warning(
                    f"It's warm outside and won't be cool later: {live_temp}°F stays above {threshold}°F. -- Warm Months"
                )


def render_wind_banner(wind_speed: float | None, wind_dir: str | None) -> None:
    """Show current wind status banner."""
    if wind_speed is None or wind_dir is None:
        st.warning("Wind information is currently unavailable.")
        return
    st.markdown(f"**Wind Speed Now:** {wind_speed} mph | **Wind Direction:** {wind_dir}")


def build_wind_chart(
    df: pd.DataFrame, current_hour: int, hist_band: pd.DataFrame
) -> alt.LayerChart:
    wind_df = df.copy()
    wind_df["Status"] = (
        wind_df["Hour"]
        .apply(lambda h: "Actual" if h <= current_hour else "Forecast")
        .astype(object)
    )

    max_speed = (
        wind_df["WindSpeed"].dropna().max() if not wind_df["WindSpeed"].dropna().empty else 0
    )
    y_max = max(50, max_speed + 5)

    x_axis = alt.Axis(
        values=list(range(24)),
        labelAngle=-45,
        labelFontSize=11,
        labelExpr="datum.value + ':00'",
    )

    wind_line = (
        alt.Chart(wind_df)
        .mark_line(strokeWidth=4)
        .encode(
            x=alt.X("Hour:Q", axis=x_axis),
            y=alt.Y(
                "WindSpeed:Q",
                axis=alt.Axis(title="Wind Speed (mph)", labelFontSize=11, titleFontSize=14),
                scale=alt.Scale(domain=[0, y_max]),
            ),
            color=alt.Color(
                "Status:N",
                scale=alt.Scale(domain=["Actual", "Forecast"], range=["#00f2ff", "#ffffff"]),
            ),
        )
    )

    if not hist_band.empty and "WindSpeedMean" in hist_band.columns:
        wind_band = (
            alt.Chart(hist_band)
            .mark_area(opacity=0.18, color="#a0c4ff")
            .encode(
                x=alt.X("Hour:Q"),
                y=alt.Y("WindSpeedLow:Q"),
                y2=alt.Y2("WindSpeedHigh:Q"),
            )
        )
        wind_hist_line = (
            alt.Chart(hist_band)
            .mark_line(color="#66b2ff", opacity=0.7)
            .encode(
                x="Hour:Q",
                y="WindSpeedMean:Q",
            )
        )
        chart = wind_band + wind_hist_line + wind_line
    else:
        chart = wind_line

    return chart.properties(height=300).configure_legend(fillColor="#1e1e1e", padding=10)


def build_precip_chart(df: pd.DataFrame, current_hour: int) -> alt.LayerChart:
    """Build hourly precipitation chart (inches) for actual hours only."""
    precip_df = df.copy()
    precip_df["Status"] = precip_df["Hour"].apply(
        lambda h: "Actual" if h <= current_hour else "Future"
    )
    actual = precip_df[(precip_df["Status"] == "Actual") & (precip_df["PrecipIn"].notna())]

    max_precip = actual["PrecipIn"].max() if not actual.empty else 0
    y_max = max(0.3, max_precip + 0.05)

    x = alt.X(
        "Hour:Q",
        axis=alt.Axis(
            values=list(range(24)),
            labelAngle=-45,
            labelFontSize=11,
            labelExpr="datum.value + ':00'",
        ),
    )
    y = alt.Y(
        "PrecipIn:Q",
        axis=alt.Axis(title="Precipitation (in)", labelFontSize=11, titleFontSize=14),
        scale=alt.Scale(domain=[0, y_max]),
    )

    line = (
        alt.Chart(actual)
        .mark_line(strokeWidth=4, color="#4db6ff")
        .encode(
            x=x,
            y=y,
            tooltip=[
                alt.Tooltip("Hour:Q", title="Hour"),
                alt.Tooltip("PrecipIn:Q", title="Precip in"),
            ],
        )
    )

    now_dot = (
        alt.Chart(actual[actual["Hour"] == current_hour])
        .mark_circle(size=260, color="#00f2ff")
        .encode(x=x, y=y)
    )

    if not actual.empty:
        max_row = actual.loc[actual["PrecipIn"] == actual["PrecipIn"].max()].iloc[0]
        label_df = pd.DataFrame(
            [
                {
                    "Hour": max_row["Hour"],
                    "PrecipIn": max_row["PrecipIn"],
                    "Label": f"{max_row['PrecipIn']} in",
                }
            ]
        )
        label = (
            alt.Chart(label_df)
            .mark_text(dy=-16, fontSize=12, fontWeight="bold", color="#d9f2ff")
            .encode(x=x, y=y, text="Label")
        )
    else:
        label = alt.Chart(pd.DataFrame({"Hour": [], "PrecipIn": [], "Label": []})).mark_text()

    return (
        (line + now_dot + label)
        .properties(height=280)
        .configure_legend(fillColor="#1e1e1e", padding=10)
    )


# ---------------------------------------------------------------------------
# APP
# ---------------------------------------------------------------------------
def run_app() -> None:
    _env = st.secrets.get("ENV", os.getenv("ENV", "prod"))
    _is_dev = str(_env).strip().lower() == "dev"
    _page_title = "The Farm [DEV]" if _is_dev else "The Farm"

    st.set_page_config(page_title=_page_title, page_icon="🏔️", layout="wide")
    st.title("The Farm: How's the Weather?" + (" — DEV" if _is_dev else ""))

    now_mtn = datetime.now(LOCAL_TZ)
    st.markdown(f"**Loveland, CO** | `{now_mtn.strftime('%H:%M:%S')}`")

    # Sidebar
    st.sidebar.title("Settings")
    mode = st.sidebar.selectbox("Monitoring Mode", list(THRESHOLDS.keys()))
    threshold = THRESHOLDS[mode]

    # Temperature operand toggle (actual vs feels like)
    temp_mode = st.sidebar.radio("Temperature Type", ["Feels Like", "Actual"])
    selected_temp_key = "FeelsLike" if temp_mode == "Feels Like" else "Actual"
    selected_metric_title = f"{temp_mode} Now"

    dev_sample_setting = st.secrets.get("DEV_USE_SAMPLE_DATA", os.getenv("DEV_USE_SAMPLE_DATA"))
    dev_use_sample_data = _is_dev and _as_bool(dev_sample_setting, default=True)

    if dev_use_sample_data:
        st.info("Using local dev sample weather data (no external API calls).")
        df, live_temp, hist_band = _build_dev_sample_payload(now_mtn)
    else:
        # Fetch data
        vc_api_key = _get_vc_api_key()
        with st.spinner("Fetching latest weather data…"):
            # Forecast + current — fall back to session state if API is rate limited
            try:
                df, live_temp = fetch_forecast_and_current(vc_api_key)
                if not df.empty:
                    st.session_state["df"] = df
                    st.session_state["live_temp"] = live_temp
            except requests.RequestException as e:
                logger.warning("Forecast fetch failed, using cached fallback: %s", e)
                df = st.session_state.get("df", pd.DataFrame())
                live_temp = st.session_state.get("live_temp", None)
                if df.empty or live_temp is None:
                    st.error(
                        "Could not reach the weather API and no cached data is available. Please try again in a few minutes."
                    )
                    st.stop()
                else:
                    st.warning("⚠️ Weather API temporarily unavailable — showing last known data.")

            # Historical band — cached 7 days, falls back to session state if API is rate limited
            today_str = now_mtn.strftime("%Y-%m-%d")
            try:
                hist_band = fetch_historical_band(today_str, vc_api_key)
                if not hist_band.empty:
                    st.session_state["hist_band"] = hist_band
                else:
                    hist_band = st.session_state.get(
                        "hist_band",
                        pd.DataFrame(columns=["Hour", "HistHigh", "HistLow", "HistMean"]),
                    )
                    if hist_band.empty:
                        st.caption("⚠️ Historical band temporarily unavailable.")
            except requests.RequestException as e:
                logger.warning("Historical band fetch failed, using cached fallback: %s", e)
                hist_band = st.session_state.get(
                    "hist_band",
                    pd.DataFrame(columns=["Hour", "HistHigh", "HistLow", "HistMean"]),
                )
                if hist_band.empty:
                    st.caption("⚠️ Historical band temporarily unavailable.")

    if df.empty:
        st.warning("No forecast data available for today.")
        st.stop()

    # Choose dataset for display mode (actual or feels like)
    if selected_temp_key not in df.columns:
        st.error(
            f"Selected temperature key '{selected_temp_key}' is not available in fetched data."
        )
        st.stop()

    df_display = (
        df[["Hour", selected_temp_key]].rename(columns={selected_temp_key: "Temperature"}).copy()
    )
    selected_live_temp = live_temp.get(selected_temp_key)
    if selected_live_temp is None:
        st.error(f"Selected latest temperature value for '{selected_temp_key}' is unavailable.")
        st.stop()

    if hist_band.empty:
        hist_band_display = hist_band
    else:
        if selected_temp_key == "Actual":
            hist_band_display = hist_band[["Hour", "ActualHigh", "ActualLow", "ActualMean"]].rename(
                columns={
                    "ActualHigh": "HistHigh",
                    "ActualLow": "HistLow",
                    "ActualMean": "HistMean",
                }
            )
        else:
            hist_band_display = hist_band[
                ["Hour", "FeelsLikeHigh", "FeelsLikeLow", "FeelsLikeMean"]
            ].rename(
                columns={
                    "FeelsLikeHigh": "HistHigh",
                    "FeelsLikeLow": "HistLow",
                    "FeelsLikeMean": "HistMean",
                }
            )

    current_hour = now_mtn.hour

    # Metrics
    actuals = df_display[df_display["Hour"] <= current_hour].copy()
    actuals.loc[actuals["Hour"] == current_hour, "Temperature"] = selected_live_temp
    hi = actuals["Temperature"].max()
    lo = actuals["Temperature"].min()

    # 1-hour trend delta
    trend_delta, since_label = get_temp_trend(df_display, selected_live_temp, current_hour)
    if trend_delta is not None:
        delta_str = f"{trend_delta:+.1f}°F {since_label}"
    else:
        delta_str = None

    m1, m2, m3 = st.columns(3)
    m1.metric(
        selected_metric_title,
        f"{selected_live_temp}°F",
        delta=delta_str,
        delta_color="normal",
    )
    m2.metric(f"Today's High ({temp_mode})", f"{hi}°F")
    m3.metric(f"Today's Low ({temp_mode})", f"{lo}°F")
    caption_heat = (
        "apparent temperature" if selected_temp_key == "FeelsLike" else "actual air temperature"
    )
    st.caption(f"🌡️ All temperatures are shown as {caption_heat}.")

    # Status banner
    forecast_future = df_display[df_display["Hour"] >= current_hour].copy()
    forecast_future.loc[forecast_future["Hour"] == current_hour, "Temperature"] = selected_live_temp
    render_status_banner(selected_live_temp, threshold, forecast_future, mode)

    # Wind section
    wind_df = df[["Hour", "WindSpeed", "WindDir"]].copy()
    selected_wind_speed = live_temp.get("WindSpeed")
    selected_wind_dir = live_temp.get("WindDir")
    if (
        not wind_df.empty
        and current_hour in wind_df["Hour"].values
        and selected_wind_speed is not None
    ):
        wind_df.loc[wind_df["Hour"] == current_hour, "WindSpeed"] = selected_wind_speed

    render_wind_banner(selected_wind_speed, selected_wind_dir)

    # Wind chart
    if hist_band.empty:
        wind_hist_band = pd.DataFrame(
            columns=["Hour", "WindSpeedHigh", "WindSpeedLow", "WindSpeedMean"]
        )
    else:
        wind_hist_band = hist_band[["Hour", "WindSpeedHigh", "WindSpeedLow", "WindSpeedMean"]]

    st.altair_chart(build_wind_chart(wind_df, current_hour, wind_hist_band), width="stretch")

    # Chart
    st.altair_chart(
        build_chart(df_display, selected_live_temp, threshold, current_hour, hist_band_display),
        width="stretch",
    )

    st.write("---")

    # Precipitation section (just before Data Sources)
    for precip_col in ["PrecipIn", "PrecipProb", "Humidity", "SnowIn"]:
        if precip_col not in df.columns:
            df[precip_col] = None

    precip_df = df[["Hour", "PrecipIn", "PrecipProb", "Humidity", "SnowIn"]].copy()
    live_precip_in = live_temp.get("PrecipIn")
    live_precip_prob = live_temp.get("PrecipProb")
    live_humidity = live_temp.get("Humidity")
    live_snow_in = live_temp.get("SnowIn")

    if not precip_df.empty and current_hour in precip_df["Hour"].values:
        if live_precip_in is not None:
            precip_df.loc[precip_df["Hour"] == current_hour, "PrecipIn"] = live_precip_in
        if live_precip_prob is not None:
            precip_df.loc[precip_df["Hour"] == current_hour, "PrecipProb"] = live_precip_prob
        if live_humidity is not None:
            precip_df.loc[precip_df["Hour"] == current_hour, "Humidity"] = live_humidity
        if live_snow_in is not None:
            precip_df.loc[precip_df["Hour"] == current_hour, "SnowIn"] = live_snow_in

    precip_actual = precip_df[precip_df["Hour"] <= current_hour].copy()
    if precip_actual.empty or precip_actual["PrecipIn"].dropna().empty:
        total_precip_so_far = 0.0
    else:
        total_precip_so_far = round(float(precip_actual["PrecipIn"].fillna(0).sum()), 2)

    # Use the most recent actual datapoint in the chart series for "recently" status.
    if precip_actual.empty:
        rain_or_snow_recently = False
    else:
        latest_row = precip_actual.sort_values("Hour").iloc[-1]
        latest_precip = latest_row.get("PrecipIn")
        latest_snow = latest_row.get("SnowIn")
        rain_or_snow_recently = (latest_precip or 0) > 0 or (latest_snow or 0) > 0

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Rain or Snow Recently?", "Yes" if rain_or_snow_recently else "No")
    p2.metric("Total Accumulation So Far Today", f"{total_precip_so_far} in")
    p3.metric(
        "Forecasted Precipitation Now %",
        f"{live_precip_prob}%" if live_precip_prob is not None else "N/A",
    )
    p4.metric(
        "Relative Humidity Now %",
        f"{live_humidity}%" if live_humidity is not None else "N/A",
    )

    st.altair_chart(build_precip_chart(precip_df, current_hour), width="stretch")
    st.caption("💧 Precipitation chart shows hourly actual precipitation amount in inches.")

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
            st.markdown("""
            **🏢 Visual Crossing** *(Live + Hourly Conditions)*

            Visual Crossing blends data from multiple trusted sources:
            - NWS/NOAA weather station observations
            - METAR airport reports (including nearby **KFNL** — Fort Collins/Loveland Airport)
            - High-resolution global forecast models updated continuously

            Additional fields used in this app:
            - **Precipitation amount** (`precip`, inches)
            - **Precipitation probability** (`precipprob`, %)
            - **Relative humidity** (`humidity`, %)
            - **Snow amount** (`snow`, inches)

            Live conditions and today's hourly forecast refresh every **5 minutes**.
            The 5-year historical band refreshes once daily.
            """)
        st.caption(
            "💡 All sources use gridded or blended models — readings may differ slightly from a backyard weather station at The Farm's exact location."
        )


if __name__ == "__main__":
    run_app()
