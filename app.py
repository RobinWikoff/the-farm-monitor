import streamlit as st
import requests
import pandas as pd
from datetime import datetime, time
import pytz
from PIL import Image

# --- CONFIG ---
try:
    API_KEY = st.secrets["WEATHER_API_KEY"]
except:
    API_KEY = "6893fccbe935414644a37268660065a8"

LAT, LON = "40.3720", "-105.0579"
CURRENT_URL = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=imperial"
FORECAST_URL = f"https://api.openweathermap.org/data/2.5/forecast?lat={LAT}&lon={LON}&appid={API_KEY}&units=imperial"
LOCAL_TZ = pytz.timezone("US/Mountain")

try:
    farm_icon = Image.open('farm-icon.png')
    st.set_page_config(page_title="The Farm", page_icon=farm_icon, layout="wide")
except:
    st.set_page_config(page_title="The Farm", page_icon="🏔️", layout="wide")

# --- DATA FUNCTIONS ---
def get_midnight_history():
    try:
        response = requests.get(FORECAST_URL, timeout=10).json()
        now_mtn = datetime.now(LOCAL_TZ)
        today_date = now_mtn.date()
        
        past_data = []
        if "list" in response:
            for entry in response['list']:
                dt_mtn = datetime.fromtimestamp(entry['dt'], tz=pytz.UTC).astimezone(LOCAL_TZ)
                
                # GRAB EVERYTHING FROM TODAY (Midnight to Now)
                if dt_mtn.date() == today_date and dt_mtn <= now_mtn:
                    past_data.append({
                        'Hour': dt_mtn.hour,
                        'Temp': round(entry['main']['temp'], 1),
                        'Date': dt_mtn.date()
                    })
        
        df = pd.DataFrame(past_data)
        return df
    except Exception as e:
        print(f"Error fetching history: {e}")
        return pd.DataFrame(columns=['Hour', 'Temp', 'Date'])

def get_live_temp():
    try:
        response = requests.get(CURRENT_URL, timeout=10).json()
        return round(response['main']['temp'], 1)
    except:
        return None

# --- SESSION STATE ---
if 'daily_history' not in st.session_state or st.session_state.daily_history.empty:
    st.session_state.daily_history = get_midnight_history()

# --- SIDEBAR ---
st.sidebar.title("Settings")
now_mtn = datetime.now(LOCAL_TZ)
mode = st.sidebar.selectbox("Mode", ["Winter", "Summer"], index=0 if now_mtn.month not in [6,7,8,9] else 1)
threshold = 65.0 if mode == "Winter" else 70.0

# --- DASHBOARD ---
@st.fragment(run_every=60)
def show_dashboard():
    new_temp = get_live_temp()
    now_mtn = datetime.now(LOCAL_TZ)
    current_hour = now_mtn.hour
    
    if new_temp is not None:
        # Reset Logic if date changed
        if not st.session_state.daily_history.empty:
            if st.session_state.daily_history['Date'].iloc[0] != now_mtn.date():
                st.session_state.daily_history = get_midnight_history()

        # Update Session History with Live Data
        new_entry = pd.DataFrame({'Hour': [current_hour], 'Temp': [new_temp], 'Date': [now_mtn.date()]})
        st.session_state.daily_history = pd.concat([st.session_state.daily_history, new_entry], ignore_index=True).drop_duplicates('Hour', keep='last')

        # --- GRAPH ENGINE ---
        chart_df = pd.DataFrame({'Hour': range(24)})
        chart_df = pd.merge(chart_df, st.session_state.daily_history[['Hour', 'Temp']], on='Hour', how='left')
        
        # Ensure the line starts at the earliest available data point
        first_temp_idx = chart_df['Temp'].first_valid_index()
        if first_temp_idx is not None:
             chart_df.loc[0, 'Temp'] = chart_df.loc[first_temp_idx, 'Temp']
        
        # Fill the line up to right now
        chart_df['Temp'] = chart_df['Temp'].interpolate(method='linear')
        chart_df.loc[chart_df['Hour'] > current_hour, 'Temp'] = None 
        
        chart_df['Target'] = threshold
        chart_df['24h'] = chart_df['Hour'].apply(lambda x: f"{x:02}:00")
        chart_df = chart_df.set_index('24h')

        # --- UI ---
        st.title("The Farm")
        st.markdown(f"**Loveland, CO** | `{now_mtn.strftime('%H:%M:%S')}`")
        
        # CALCULATE HIGH/LOW FROM ALL DATA COLLECTED TODAY
        d_high = st.session_state.daily_history['Temp'].max()
        d_low = st.session_state.daily_history['Temp'].min()

        m1, m2, m3 = st.columns(3)
        m1.metric("Live", f"{new_temp}°F")
        m2.metric("High Today", f"{d_high}°F")
        m3.metric("Low Today", f"{d_low}°F")

        st.write("---")

        col_left, col_right = st.columns([1, 2])
        with col_left:
            if mode == "Winter":
                if new_temp >= threshold: st.success(f"☀️ Warming! {new_temp}°F")
                else: st.info(f"❄️ Waiting for {threshold}°F")
            else:
                if new_temp <= threshold: st.success("🌬️ Cool breeze!")
                else: st.warning(f"🔥 Waiting for {threshold}°F")

        with col_right:
            st.line_chart(chart_df[['Temp', 'Target']], color=["#00f2ff", "#ff4b4b"])

show_dashboard()
