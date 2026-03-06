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

# METEO_URL already pulls 24h of "today" and "tomorrow" forecasts
METEO_URL = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=temperature_2m&temperature_unit=fahrenheit&timezone=auto"
OWM_URL = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=imperial"

try:
    farm_icon = Image.open('farm-icon.png')
    st.set_page_config(page_title="The Farm", page_icon=farm_icon, layout="wide")
except:
    st.set_page_config(page_title="The Farm", page_icon="🏔️", layout="wide")

# --- DATA FUNCTIONS ---
def get_all_day_data():
    """Fetches History + Forecast for the full 24h of Today."""
    try:
        response = requests.get(METEO_URL, timeout=10).json()
        now_mtn = datetime.now(LOCAL_TZ)
        
        times = response['hourly']['time']
        temps = response['hourly']['temperature_2m']
        
        data_points = []
        for t, temp in zip(times, temps):
            dt = datetime.fromisoformat(t).replace(tzinfo=pytz.UTC).astimezone(LOCAL_TZ)
            # Take only data belonging to the current calendar day
            if dt.date() == now_mtn.date():
                # Label data as 'Actual' or 'Forecast' based on current hour
                status = 'Actual' if dt.hour <= now_mtn.hour else 'Forecast'
                data_points.append({
                    'Hour': dt.hour,
                    'Temperature': round(temp, 1),
                    'Time Label': f"{dt.hour:02}:00",
                    'Status': status
                })
        return pd.DataFrame(data_points)
    except:
        return pd.DataFrame(columns=['Hour', 'Temperature', 'Time Label', 'Status'])

def get_live_temp():
    try:
        response = requests.get(OWM_URL, timeout=10).json()
        return round(response['main']['temp'], 1)
    except:
        return None

# --- INITIAL DATA ---
if 'daily_history' not in st.session_state:
    st.session_state.daily_history = get_all_day_data()

# --- SIDEBAR ---
st.sidebar.title("Settings")
now_mtn = datetime.now(LOCAL_TZ)
mode = st.sidebar.selectbox("Monitoring Mode", ["Winter (Warming Focus)", "Summer (Cooling Focus)"], index=0 if now_mtn.month not in [6,7,8,9] else 1)
threshold = 65.0 if "Winter" in mode else 70.0

if st.sidebar.button("Update All Data"):
    st.session_state.daily_history = get_all_day_data()
    st.rerun()

# --- DASHBOARD ---
@st.fragment(run_every=60)
def show_dashboard():
    now_mtn = datetime.now(LOCAL_TZ)
    live_temp = get_live_temp()
    current_hour = now_mtn.hour
    
    # 1. Update Live Data in the Dataframe
    df = st.session_state.daily_history.copy()
    if live_temp is not None:
        df.loc[df['Hour'] == current_hour, 'Temperature'] = live_temp
    
    # 2. Split data for specialized charting
    actual_df = df[df['Hour'] <= current_hour].copy()
    forecast_df = df[df['Hour'] >= current_hour].copy() # Overlap at current hour to connect lines
    current_point_df = df[df['Hour'] == current_hour].copy()

    # --- ALTAIR CHARTING ---
    # Common X-axis
    x_axis = alt.X('Time Label:O', sort=None, title='Time (24h)')
    y_axis = alt.Y('Temperature:Q', scale=alt.Scale(zero=False), title='Degrees (°F)')

    # A. Actual History Line (Solid)
    actual_line = alt.Chart(actual_df).mark_line(color='#00f2ff', strokeWidth=4).encode(x=x_axis, y=y_axis)

    # B. Forecast Line (Dashed & Faded)
    forecast_line = alt.Chart(forecast_df).mark_line(
        color='#00f2ff', strokeWidth=2, strokeDash=[4,4], opacity=0.5
    ).encode(x=x_axis, y=y_axis)

    # C. Threshold Line (Red)
    threshold_line = alt.Chart(pd.DataFrame({'y': [threshold]})).mark_rule(
        color='#ff4b4b', strokeDash=[2,2], size=2
    ).encode(y='y:Q')

    # D. THE BALL (14pt Marker)
    current_ball = alt.Chart(current_point_df).mark_circle(size=250, color='#00f2ff').encode(x=x_axis, y=y_axis)

    final_chart = (actual_line + forecast_line + threshold_line + current_ball).properties(height=400)

    # --- UI ---
    st.title("The Farm")
    st.markdown(f"**Loveland, CO** | `{now_mtn.strftime('%H:%M:%S')}`")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Live", f"{live_temp}°F")
    m2.metric("High Today", f"{df['Temperature'].max()}°F")
    m3.metric("Low Today", f"{df['Temperature'].min()}°F")

    st.write("---")

    col_left, col_right = st.columns([1, 2])
    with col_left:
        st.write(f"### Current Mode: {mode}")
        if "Winter" in mode:
            if live_temp >= threshold: st.success(f"☀️ Threshold met! {live_temp}°F")
            else: st.info(f"❄️ Below threshold ({threshold}°F)")
        else:
            if live_temp <= threshold: st.success(f"🌬️ Threshold met! {live_temp}°F")
            else: st.warning(f"🔥 Above threshold ({threshold}°F)")

    with col_right:
        st.altair_chart(final_chart, use_container_width=True)

show_dashboard()
