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

METEO_URL = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=temperature_2m&temperature_unit=fahrenheit&timezone=auto"
OWM_URL = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=imperial"

try:
    farm_icon = Image.open('farm-icon.png')
    st.set_page_config(page_title="The Farm", page_icon=farm_icon, layout="wide")
except:
    st.set_page_config(page_title="The Farm", page_icon="🏔️", layout="wide")

# --- DATA FUNCTIONS ---
def get_all_day_data():
    try:
        response = requests.get(METEO_URL, timeout=10).json()
        now_mtn = datetime.now(LOCAL_TZ)
        times = response['hourly']['time']
        temps = response['hourly']['temperature_2m']
        
        data_points = []
        for t, temp in zip(times, temps):
            dt = datetime.fromisoformat(t).replace(tzinfo=pytz.UTC).astimezone(LOCAL_TZ)
            if dt.date() == now_mtn.date():
                data_points.append({
                    'Hour': dt.hour,
                    'Temperature': round(temp, 1)
                })
        return pd.DataFrame(data_points)
    except:
        return pd.DataFrame(columns=['Hour', 'Temperature'])

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

# --- DASHBOARD ---
@st.fragment(run_every=60)
def show_dashboard():
    now_mtn = datetime.now(LOCAL_TZ)
    live_temp = get_live_temp()
    current_hour = now_mtn.hour
    
    # Refresh data at midnight
    if not st.session_state.daily_history.empty:
        # Simple check: if the first hour in history isn't today, refresh
        pass 

    df = st.session_state.daily_history.copy()
    if live_temp is not None:
        df.loc[df['Hour'] == current_hour, 'Temperature'] = live_temp
    
    # Split data
    actual_df = df[df['Hour'] <= current_hour].copy()
    forecast_df = df[df['Hour'] >= current_hour].copy()
    current_point_df = df[df['Hour'] == current_hour].copy()

    # --- ALTAIR CHARTING ---
    # We use 'Hour:Q' (Quantitative) to avoid the "undefined" error
    x_axis = alt.X('Hour:Q', title='Time (24h)', scale=alt.Scale(domain=[0, 23]),
                   axis=alt.Axis(labelExpr="datum.value + ':00'"))
    y_axis = alt.Y('Temperature:Q', scale=alt.Scale(zero=False), title='Degrees (°F)')

    # 1. Past Line (Solid)
    line_past = alt.Chart(actual_df).mark_line(color='#00f2ff', strokeWidth=4).encode(x=x_axis, y=y_axis)

    # 2. Future Line (Dashed)
    line_future = alt.Chart(forecast_df).mark_line(color='#00f2ff', strokeWidth=2, strokeDash=[4,4], opacity=0.4).encode(x=x_axis, y=y_axis)

    # 3. Threshold (Red)
    rule = alt.Chart(pd.DataFrame({'y': [threshold]})).mark_rule(color='#ff4b4b', strokeDash=[2,2]).encode(y='y:Q')

    # 4. THE BALL (14pt Marker)
    ball = alt.Chart(current_point_df).mark_circle(size=250, color='#00f2ff').encode(x=x_axis, y=y_axis)

    final_chart = (line_past + line_future + rule + ball).properties(height=400)

    # --- UI ---
    st.title("The Farm")
    st.markdown(f"**Loveland, CO** | `{now_mtn.strftime('%H:%M:%S')}`")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Live", f"{live_temp}°F")
    m2.metric("High Today", f"{df['Temperature'].max()}°F")
    m3.metric("Low Today", f"{df['Temperature'].min()}°F")

    st.write("---")
    st.altair_chart(final_chart, use_container_width=True)

show_dashboard()
