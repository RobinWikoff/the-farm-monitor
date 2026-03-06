import streamlit as st
import requests
import pandas as pd
from datetime import datetime, time, timedelta
import pytz
from PIL import Image

# --- CONFIGURATION ---
try:
    API_KEY = st.secrets["WEATHER_API_KEY"]
except:
    API_KEY = "6893fccbe935414644a37268660065a8"

LAT, LON = "40.3720", "-105.0579"
CURRENT_URL = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=imperial"
FORECAST_URL = f"https://api.openweathermap.org/data/2.5/forecast?lat={LAT}&lon={LON}&appid={API_KEY}&units=imperial"
LOCAL_TZ = pytz.timezone("US/Mountain")

# Load Custom Icon
try:
    farm_icon = Image.open('farm-icon.png')
    st.set_page_config(page_title="The Farm", page_icon=farm_icon, layout="wide")
except:
    st.set_page_config(page_title="The Farm", page_icon="🚜", layout="wide")

# --- DATA FUNCTIONS ---
def get_midnight_history():
    try:
        response = requests.get(FORECAST_URL, timeout=10).json()
        now_mtn = datetime.now(LOCAL_TZ)
        midnight = LOCAL_TZ.localize(datetime.combine(now_mtn.date(), time(0, 0)))
        
        past_data = []
        for entry in response['list']:
            dt_mtn = datetime.fromtimestamp(entry['dt'], tz=pytz.UTC).astimezone(LOCAL_TZ)
            if midnight <= dt_mtn <= now_mtn:
                past_data.append({
                    'Time': dt_mtn.strftime("%H:%M"),
                    'Temp': round(entry['main']['temp'], 1),
                    'Date': dt_mtn.date()
                })
        return pd.DataFrame(past_data)
    except:
        return pd.DataFrame(columns=['Time', 'Temp', 'Date'])

def get_live_temp():
    try:
        response = requests.get(CURRENT_URL, timeout=10).json()
        return round(response['main']['temp'], 1)
    except:
        return None

# --- INITIALIZE HISTORY ---
if 'daily_history' not in st.session_state or st.session_state.daily_history.empty:
    st.session_state.daily_history = get_midnight_history()

# --- SIDEBAR ---
st.sidebar.title("Settings")
now_mtn = datetime.now(LOCAL_TZ)
mode = st.sidebar.selectbox("Monitoring Mode", ["Winter (Warming Focus)", "Summer (Cooling Focus)"], index=0 if now_mtn.month not in [6,7,8,9] else 1)
threshold = 65.0 if "Winter" in mode else 70.0

# --- DASHBOARD FRAGMENT ---
@st.fragment(run_every=60)
def show_dashboard():
    new_temp = get_live_temp()
    now_mtn = datetime.now(LOCAL_TZ)
    
    if new_temp is not None:
        # Midnight Reset
        if not st.session_state.daily_history.empty and st.session_state.daily_history['Date'].iloc[0] != now_mtn.date():
            st.session_state.daily_history = get_midnight_history()

        # Add current point
        new_entry = pd.DataFrame({'Time': [now_mtn.strftime("%H:%M")], 'Temp': [new_temp], 'Date': [now_mtn.date()]})
        st.session_state.daily_history = pd.concat([st.session_state.daily_history, new_entry], ignore_index=True).drop_duplicates('Time')

        # --- PREPARE 24-HOUR CHART ---
        # Create a full range of times from 00:00 to 23:00 (every hour) to anchor the axis
        full_day_times = [f"{h:02d}:00" for h in range(24)]
        full_day_df = pd.DataFrame({'Time': full_day_times})
        
        # Merge real data into the 24-hour structure
        chart_df = pd.merge(full_day_df, st.session_state.daily_history, on='Time', how='left')
        chart_df['Target'] = threshold
        chart_df = chart_df.set_index('Time')

        # Metrics
        st.title("The Farm")
        st.markdown(f"**Loveland, CO** | `{now_mtn.strftime('%I:%M %p')}`")
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Live Temp", f"{new_temp}°F")
        m2.metric("High Today", f"{st.session_state.daily_history['Temp'].max()}°F")
        m3.metric("Low Today", f"{st.session_state.daily_history['Temp'].min()}°F")

        st.write("---")

        # Layout
        col_left, col_right = st.columns([1, 2])
        with col_left:
            if "Winter" in mode:
                if new_temp >= threshold: st.success(f"☀️ Warming up! Currently {new_temp}°F.")
                else: st.info(f"❄️ Waiting for {threshold}°F...")
            else:
                if new_temp <= threshold: st.success("### 🌬️ Cool breeze has arrived!")
                else: st.warning(f"🔥 Waiting for {threshold}°F")

        with col_right:
            # Displaying the 24-hour chart
            st.line_chart(chart_df[['Temp', 'Target']], color=["#00f2ff", "#ff4b4b"])

show_dashboard()
