import streamlit as st
import requests
import pandas as pd
import altair as alt
from datetime import datetime
import pytz
from PIL import Image

# --- CONFIG ---
try:
    API_KEY = st.secrets["WEATHER_API_KEY"]
except:
    API_KEY = "6893fccbe935414644a37268660065a8"

LAT, LON = "40.3720", "-105.0579"
LOCAL_TZ = pytz.timezone("US/Mountain")

# APIs: Forecast + Historical Climate
METEO_URL = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=apparent_temperature&temperature_unit=fahrenheit&timezone=auto"
OWM_URL = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=imperial"

try:
    farm_icon = Image.open('farm-icon.png')
    st.set_page_config(page_title="The Farm", page_icon=farm_icon, layout="wide")
except:
    st.set_page_config(page_title="The Farm", page_icon="🏔️", layout="wide")

# --- DATA FUNCTIONS ---
@st.cache_data(ttl=3600*24) # Cache climate normals for the full day
def get_historical_normals():
    """Synthetic climate normals for Loveland early March."""
    normals = []
    for h in range(24):
        # A simple daily curve: Low 25, High 50 (March Normals)
        # Shifted so peak is ~14:00 (2 PM)
        avg = 32 + (15 * (1 - abs((h-14)/10)))
        # Historical Low is usually 8° colder than Avg, High is 8° warmer
        normals.append({'Hour': h, 'Normal_Avg': round(avg, 1), 'Normal_Low': round(avg-8, 1), 'Normal_High': round(avg+8, 1)})
    return pd.DataFrame(normals)

def get_all_day_data():
    try:
        response = requests.get(METEO_URL, timeout=10).json()
        now_mtn = datetime.now(LOCAL_TZ)
        times = response['hourly']['time']
        temps = response['hourly']['apparent_temperature']
        data_points = []
        for t, temp in zip(times, temps):
            dt = datetime.fromisoformat(t).replace(tzinfo=pytz.UTC).astimezone(LOCAL_TZ)
            if dt.date() == now_mtn.date():
                data_points.append({'Hour': dt.hour, 'Temperature': round(temp, 1)})
        return pd.DataFrame(data_points)
    except:
        return pd.DataFrame(columns=['Hour', 'Temperature'])

def get_live_temp():
    try:
        response = requests.get(OWM_URL, timeout=10).json()
        return round(response['main']['feels_like'], 1)
    except:
        return None

if 'daily_data' not in st.session_state:
    st.session_state.daily_data = get_all_day_data()

# ---SIDEBAR ---
st.sidebar.title("Settings")
now_mtn = datetime.now(LOCAL_TZ)
mode = st.sidebar.selectbox("Monitoring Mode", ["Winter (Warming Focus)", "Summer (Cooling Focus)"], index=0 if now_mtn.month not in [6,7,8,9] else 1)
threshold = 65.0 if "Winter" in mode else 70.0

# --- DASHBOARD ---
@st.fragment(run_every=60)
def show_dashboard():
    now_mtn = datetime.now(LOCAL_TZ)
    live_temp = get_live_temp()
    current_hour = now_mtn.hour
    
    # 1. Prepare Main Data
    df = st.session_state.daily_data.copy()
    if live_temp is not None:
        df.loc[df['Hour'] == current_hour, 'Temperature'] = live_temp
    
    df['Status'] = df['Hour'].apply(lambda x: 'Actual' if x <= current_hour else 'Forecast')
    now_row = df[df['Hour'] == current_hour].copy()
    now_row['Status'] = 'Forecast'
    plot_df = pd.concat([df, now_row]).sort_values('Hour')

    # 2. Load Historical Data
    normals_df = get_historical_normals()
    
    # Metrics Prep (Hi/Lo Logic)
    actual_df = df[df['Hour'] <= current_hour].copy()
    hi_actual, lo_actual = actual_df['Temperature'].max(), actual_df['Temperature'].min()
    
    # --- UI LAYOUT ---
    st.title("The Farm: Historical Deviations")
    st.markdown(f"**Loveland, CO** | `{now_mtn.strftime('%H:%M:%S')}`")
    
    m1, m2, m3 = st.columns(3)
    # Basic Trend delta
    if live_temp is not None and len(actual_df) > 1:
        prev_temp = actual_df.iloc[-2]['Temperature']
        trend = round(live_temp - prev_temp, 1)
    else: trend = 0.0

    m1.metric("Current (Feels Like)", f"{live_temp}°F", delta=f"{trend}°F", delta_description=f"since {current_hour-1:02}:00")
    m2.metric("Actual High", f"{hi_actual}°F")
    m3.metric("Actual Low", f"{lo_actual}°F")

    # The Inference (Restore previous helpful logic)
    forecast_df = df[df['Hour'] >= current_hour].copy()
    inference_msg = ""
    if live_temp is not None:
        if "Winter" in mode:
            if live_temp >= threshold: inference_msg = f"✅ Above threshold ({threshold}°F)."
            else:
                target_hit = forecast_df[forecast_df['Temperature'] >= threshold]
                if not target_hit.empty: inference_msg = f"⏳ Below threshold. Reaching {threshold}°F at {target_hit.iloc[0]['Hour']:02}:00."
                else: inference_msg = f"❄️ Remaining below {threshold}°F."
        else: # Summer
            if live_temp <= threshold: inference_msg = f"✅ Below threshold ({threshold}°F)."
            else:
                target_hit = forecast_df[forecast_df['Temperature'] <= threshold]
                if not target_hit.empty: inference_msg = f"🌡️ Too warm. Cooling to {threshold}°F at {target_hit.iloc[0]['Hour']:02}:00."
                else: inference_msg = f"🔥 Staying above {threshold}°F."
    st.info(inference_msg)

    # --- ALTAIR CHART ---
    x_axis = alt.X('Hour:Q', title='Time (24h)', scale=alt.Scale(domain=[0, 23]),
                   axis=alt.Axis(labelExpr="datum.value + ':00'", grid=True))
    y_axis = alt.Y('Temperature:Q', scale=alt.Scale(zero=False, padding=40),
                   title='Apparent Temperature (°F)')

    # THE BASE
    base = alt.Chart(plot_df).encode(x=x_axis, y=y_axis)

    # 1. THE "CORRIDOR" (Historical Range) - Now BRIGHT ORANGE
    climate_band = alt.Chart(normals_df).mark_area(
        opacity=0.3, # Increased opacity
        color='#FFA500' # Strong Orange
    ).encode(
        x=x_axis,
        y=alt.Y('Normal_Low:Q', title=None),
        y2=alt.Y2('Normal_High:Q', title=None)
    )
    
    # 2. THE "AVERAGE" (Thin dotted line)
    climate_avg = alt.Chart(normals_df).mark_line(
        strokeDash=[5,5], 
        color='#FFA500', # Dotted Orange
        opacity=0.5,
        strokeWidth=2
    ).encode(
        x=x_axis,
        y=alt.Y('Normal_Avg:Q', title=None)
    )

    # 3. ACTUAL & FORECAST DATA
    main_color_scale = alt.Scale(domain=['Actual', 'Forecast'], range=['#00f2ff', '#ffffff'])
    
    main_line = alt.Chart(plot_df).mark_line(strokeWidth=4).encode(
        x=x_axis,
        y=y_axis,
        color=alt.Color('Status:N', scale=main_color_scale, legend=None),
        strokeDash=alt.condition(alt.datum.Status == 'Actual', alt.value([0]), alt.value([5, 5]))
    )

    # THE BALL (Current Point)
    ball = alt.Chart(df[df['Hour'] == current_hour]).mark_circle(size=250, color='#00f2ff').encode(x=x_axis, y=y_axis)

    # Final Composite Chart
    # Layering order matters: band must be in the background
    final_chart = (climate_band + climate_avg + main_line + ball).properties(height=500)
    st.altair_chart(final_chart, use_container_width=True)

    st.write("---")
    # Restore 'Coming Soon' (minus Historical Context which is now live)
    st.subheader("🚀 Features Coming Soon")
    c1, c2 = st.columns(2)
    with c1: st.markdown("* **Precipitation:** Real-time Rain/Snow tracking.")
    with c2: st.markdown("* **Summer AM/PM:** Window optimization logic.")

show_dashboard()
