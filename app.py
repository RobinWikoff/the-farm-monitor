import streamlit as st
import requests
import pandas as pd
from datetime import datetime, time
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

# --- DATA FETCHING (START AT MIDNIGHT) ---
@st.cache_data(ttl=600)
def get_daily_history():
    try:
        response = requests.get(URL, timeout=10).json()
        
        # Get "Midnight Today" in Mountain Time
        now_mtn = datetime.now(LOCAL_TZ)
        midnight_today = LOCAL_TZ.localize(datetime.combine(now_mtn.date(), time(0, 0)))
        
        daily_points = []
        
        for entry in response['list']:
            # Convert API UTC time to Mountain Time
            dt_mtn = datetime.fromtimestamp(entry['dt'], tz=pytz.UTC).astimezone(LOCAL_TZ)
            
            # Only include data points that happened AFTER midnight today
            if dt_mtn >= midnight_today and dt_mtn <= now_mtn:
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
default_winter = month not in [6, 7, 8, 9]

mode = st.sidebar.selectbox("Monitoring Mode", 
                            ["Winter (Warming Focus)", "Summer (Cooling Focus)"], 
                            index=0 if default_winter else 1)

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
            st.metric(label="Today's High (Since Midnight)", value=f"{daily_high}°F")

        # --- ALERT LOGIC ---
        if "Winter" in mode:
            if current_temp >= threshold:
                st.balloons()
                st.success(f"☀️ Warming up! Currently {current_temp}°F.")
            else:
                st.info(f"❄️ Waiting for {threshold}°F...")
        else:
            if current_temp <= threshold:
                st.markdown("### 🌬️ A cool breeze has arrived!")
                st.toast('Cooling detected!', icon='🌬️')
            else:
                st.warning(f"🔥 Waiting for {threshold}°F")

        # --- FULL DAY CHART (Midnight Start) ---
        with col3:
            df['Target'] = threshold
            # Set the index to Time so the X-axis labels are correct
            st.line_chart(df.set_index('Time')[['Temp', 'Target']], 
                          color=["#00f2ff", "#ff4b4b"])
    else:
        st.info("Gathering data starting from midnight...")

show_dashboard()
