import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz
from PIL import Image

# --- CONFIGURATION & SECURITY ---
try:
    API_KEY = st.secrets["WEATHER_API_KEY"]
except:
    API_KEY = "6893fccbe935414644a37268660065a8"

LAT, LON = "40.3720", "-105.0579"
URL = f"https://api.openweathermap.org/data/2.5/forecast?lat={LAT}&lon={LON}&appid={API_KEY}&units=imperial"
LOCAL_TZ = pytz.timezone("US/Mountain")

# Load Custom Fractal Farmhouse Icon
try:
    farm_icon = Image.open('farm-icon.png')
    st.set_page_config(page_title="The Farm Monitor", page_icon=farm_icon, layout="wide")
except:
    st.set_page_config(page_title="The Farm Monitor", page_icon="🏔️", layout="wide")

# --- DATA FETCHING (FULL DAY HISTORY) ---
@st.cache_data(ttl=600)
def get_daily_history():
    try:
        response = requests.get(URL, timeout=10).json()
        today = datetime.now(LOCAL_TZ).date()
        daily_points = []
        
        for entry in response['list']:
            dt_mtn = datetime.fromtimestamp(entry['dt'], tz=pytz.UTC).astimezone(LOCAL_TZ)
            if dt_mtn.date() == today:
                daily_points.append({
                    'Time': dt_mtn.strftime("%I:%M %p"),
                    'Temp': round(entry['main']['temp'], 1),
                    'raw_dt': dt_mtn
                })
        
        return pd.DataFrame(daily_points).sort_values('raw_dt')
    except:
        return pd.DataFrame()

# --- SEASONAL LOGIC ---
st.sidebar.title("🚜 The Farm Settings")
month = datetime.now(LOCAL_TZ).month
# Winter/Spring (Oct-May) vs Summer/Fall (June-Sept)
default_winter = month not in [6, 7, 8, 9]

mode = st.sidebar.selectbox("Monitoring Mode", 
                            ["Winter (Warming Focus)", "Summer (Cooling Focus)"], 
                            index=0 if default_winter else 1)

# Restore your specific thresholds
threshold = 65.0 if "Winter" in mode else 70.0
st.sidebar.info(f"Current Goal: {threshold}°F")

# --- DASHBOARD FRAGMENT ---
@st.fragment(run_every=60)
def show_dashboard():
    df = get_daily_history()
    
    if not df.empty:
        current_temp = df['Temp'].iloc[-1]
        daily_high = df['Temp'].max()
        last_updated = datetime.now(LOCAL_TZ).strftime("%I:%M:%S %p")
        
        st.title("🚜 The Farm - Environmental Watchdog")
        st.markdown(f"**Loveland, CO** | Status as of `{last_updated}`")
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            st.metric(label="Current Temp", value=f"{current_temp}°F")
        with col2:
            st.metric(label="Today's High", value=f"{daily_high}°F")

        # --- RESTORED ALERT LOGIC ---
        if "Winter" in mode:
            if current_temp >= threshold:
                st.balloons()
                st.success(f"☀️ Warming up! The Farm is at {current_temp}°F (Target: {threshold}°F)")
            else:
                st.info(f"❄️ Waiting for {threshold}°F...")
        else:
            if current_temp <= threshold:
                st.markdown("### 🌬️ A cool breeze has arrived!")
                st.toast('Cooling detected!', icon='🌬️')
                st.info(f"It's {current_temp}°F. Perfect time to open the windows.")
            else:
                st.warning(f"🔥 Waiting for {threshold}°F (Current: {current_temp}°F)")

        # --- FULL DAY CHART ---
        with col3:
            df['Target'] = threshold
            st.line_chart(df.set_index('Time')[['Temp', 'Target']], 
                          color=["#00f2ff", "#ff4b4b"])
    else:
        st.warning("Connecting to Loveland weather station...")

show_dashboard()
