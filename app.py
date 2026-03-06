import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz

# --- CONFIGURATION & SECURITY ---
try:
    API_KEY = st.secrets["WEATHER_API_KEY"]
except:
    API_KEY = "6893fccbe935414644a37268660065a8"

# Loveland, CO Coordinates
LAT, LON = "40.3720", "-105.0579"
URL = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=imperial"
LOCAL_TZ = pytz.timezone("US/Mountain")

st.set_page_config(page_title="The Farm Monitor", page_icon="🚜", layout="wide")

# Initialize Session Data
if 'history' not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=['Time', 'Temperature', 'Threshold'])
if 'max_temp' not in st.session_state:
    st.session_state.max_temp = -999.0

def get_live_temp():
    try:
        response = requests.get(URL, timeout=10)
        return round(response.json()['main']['temp'], 1)
    except:
        return None

# --- SIDEBAR SETTINGS ---
st.sidebar.title("🚜 The Farm Settings")
month = datetime.now(LOCAL_TZ).month
default_mode = "Summer (Cooling Focus)" if 6 <= month <= 9 else "Winter (Warming Focus)"
mode = st.sidebar.selectbox("Monitoring Mode", 
                            ["Winter (Warming Focus)", "Summer (Cooling Focus)"], 
                            index=0 if "Winter" in default_mode else 1)

threshold = 65.0 if "Winter" in mode else 70.0

# --- DASHBOARD FRAGMENT ---
@st.fragment(run_every=60)
def update_dashboard():
    new_temp = get_live_temp()
    
    if new_temp is not None:
        # Get Time in Loveland
        now_mountain = datetime.now(LOCAL_TZ)
        last_updated = now_mountain.strftime("%I:%M:%S %p")
        now_short = now_mountain.strftime("%H:%M:%S")
        
        # Max Temp Tracking
        if new_temp > st.session_state.max_temp:
            st.session_state.max_temp = new_temp
            
        # Update History
        new_row = pd.DataFrame({'Time': [now_short], 'Temperature': [new_temp], 'Threshold': [threshold]})
        st.session_state.history = pd.concat([st.session_state.history, new_row], ignore_index=True)
        
        # Trend Calculation
        delta = round(new_temp - st.session_state.history['Temperature'].iloc[-2], 2) if len(st.session_state.history) > 1 else None

        # --- HEADER ---
        st.title("🚜 The Farm - Environmental Watchdog")
        st.markdown(f"**Current Time in Loveland:** `{last_updated}`")
        
        # --- METRICS ---
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            st.metric(label="Live Temp", value=f"{new_temp}°F", delta=f"{delta}°F" if delta is not None else None)
        with col2:
            st.metric(label="Today's High", value=f"{st.session_state.max_temp}°F")

        # --- ALERTS ---
        if "Winter" in mode:
            if new_temp >= threshold:
                st.balloons()
                st.success(f"☀️ Warming up! Currently {new_temp}°F.")
            else:
                st.info(f"❄️ Brisk at the Farm. Waiting for {threshold}°F.")
        else:
            if new_temp <= threshold:
                st.markdown("### 🌬️ A cool breeze has arrived!")
                st.toast('Cooler air detected!', icon='🌬️')
            else:
                st.warning(f"🔥 Waiting for the evening cool-down (Target: {threshold}°F)")

        # --- CHART ---
        with col3:
            if len(st.session_state.history) > 1:
                # Optimized for Dark Mode
                st.line_chart(st.session_state.history.set_index('Time')[['Temperature', 'Threshold']], 
                              color=["#00f2ff", "#ff4b4b"])

update_dashboard()

with st.sidebar:
    st.write("---")
    if st.button("Reset Session Logs"):
        st.session_state.history = pd.DataFrame(columns=['Time', 'Temperature', 'Threshold'])
        st.session_state.max_temp = -999.0
        st.rerun()
