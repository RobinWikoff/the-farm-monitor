import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz
from PIL import Image

# --- CONFIGURATION & SECRETS ---
try:
    API_KEY = st.secrets["WEATHER_API_KEY"]
except:
    # Manual fallback for local testing
    API_KEY = "6893fccbe935414644a37268660065a8"

LAT, LON = "40.3720", "-105.0579"
LOCAL_TZ = pytz.timezone("US/Mountain")

# APIs: Open-Meteo (History) & OpenWeather (Live)
METEO_URL = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=temperature_2m&temperature_unit=fahrenheit&timezone=auto&past_days=1"
OWM_URL = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=imperial"

# Browser Tab Setup
try:
    farm_icon = Image.open('farm-icon.png')
    st.set_page_config(page_title="The Farm", page_icon=farm_icon, layout="wide")
except:
    st.set_page_config(page_title="The Farm", page_icon="🏔️", layout="wide")

# --- DATA FETCHING ---
def get_historical_data():
    try:
        response = requests.get(METEO_URL, timeout=10).json()
        now_mtn = datetime.now(LOCAL_TZ)
        times = response['hourly']['time']
        temps = response['hourly']['temperature_2m']
        
        data_points = []
        for t, temp in zip(times, temps):
            dt = datetime.fromisoformat(t).replace(tzinfo=pytz.UTC).astimezone(LOCAL_TZ)
            if dt.date() == now_mtn.date() and dt <= now_mtn:
                data_points.append({'Hour': dt.hour, 'Temp': round(temp, 1), 'Date': dt.date()})
        return pd.DataFrame(data_points)
    except:
        return pd.DataFrame(columns=['Hour', 'Temp', 'Date'])

def get_live_temp():
    try:
        response = requests.get(OWM_URL, timeout=10).json()
        return round(response['main']['temp'], 1)
    except:
        return None

# --- SESSION STATE ---
if 'daily_history' not in st.session_state or st.session_state.daily_history.empty:
    st.session_state.daily_history = get_historical_data()

# --- SIDEBAR SETTINGS ---
st.sidebar.title("Settings")
now_mtn = datetime.now(LOCAL_TZ)

# Restored Descriptive Labels
mode = st.sidebar.selectbox(
    "Monitoring Mode", 
    ["Winter (Warming Focus)", "Summer (Cooling Focus)"], 
    index=0 if now_mtn.month not in [6,7,8,9] else 1
)

threshold = 65.0 if "Winter" in mode else 70.0

if st.sidebar.button("Refresh History"):
    st.session_state.daily_history = get_historical_data()
    st.rerun()

# --- DASHBOARD FRAGMENT ---
@st.fragment(run_every=60)
def show_dashboard():
    now_mtn = datetime.now(LOCAL_TZ)
    live_temp = get_live_temp()
    
    if live_temp is not None:
        # Reset at Midnight
        if not st.session_state.daily_history.empty:
            if st.session_state.daily_history['Date'].iloc[0] != now_mtn.date():
                st.session_state.daily_history = get_historical_data()

        # Update Session History
        new_entry = pd.DataFrame({'Hour': [now_mtn.hour], 'Temp': [live_temp], 'Date': [now_mtn.date()]})
        st.session_state.daily_history = pd.concat([st.session_state.daily_history, new_entry], ignore_index=True).drop_duplicates('Hour', keep='last')

        # --- GRAPH ENGINE ---
        chart_df = pd.DataFrame({'Hour': range(24)})
        chart_df = pd.merge(chart_df, st.session_state.daily_history[['Hour', 'Temp']], on='Hour', how='left')
        chart_df['Temp'] = chart_df['Temp'].interpolate(method='linear')
        chart_df.loc[chart_df['Hour'] > now_mtn.hour, 'Temp'] = None 
        
        chart_df['Target'] = threshold
        chart_df['24h'] = chart_df['Hour'].apply(lambda x: f"{x:02}:00")
        chart_df = chart_df.set_index('24h')

        # --- UI DISPLAY ---
        st.title("The Farm")
        st.markdown(f"**Loveland, CO** | `{now_mtn.strftime('%H:%M:%S')}`")
        
        d_high = st.session_state.daily_history['Temp'].max()
        d_low = st.session_state.daily_history['Temp'].min()

        m1, m2, m3 = st.columns(3)
        m1.metric("Live", f"{live_temp}°F")
        m2.metric("High Today", f"{d_high}°F")
        m3.metric("Low Today", f"{d_low}°F")

        st.write("---")

        col_left, col_right = st.columns([1, 2])
        with col_left:
            if "Winter" in mode:
                if live_temp >= threshold: 
                    st.success(f"☀️ Warming up! Currently {live_temp}°F.")
                else: 
                    st.info(f"❄️ Waiting for {threshold}°F.")
            else:
                if live_temp <= threshold: 
                    st.success("### 🌬️ Cool breeze has arrived!")
                else: 
                    st.warning(f"🔥 Waiting for {threshold}°F")

        with col_right:
            st.line_chart(chart_df[['Temp', 'Target']], color=["#00f2ff", "#ff4b4b"])

show_dashboard()
