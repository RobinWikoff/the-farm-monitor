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
                # Check if the data point belongs to today
                if dt_mtn.date() == today_date:
                    past_data.append({
                        'Hour': dt_mtn.hour,
                        'Temp': round(entry['main']['temp'], 1),
                        'Date': dt_mtn.date(),
                        'Status': 'Historical/Forecast'
                    })
        
        return pd.DataFrame(past_data)
    except Exception as e:
        return pd.DataFrame(columns=['Hour', 'Temp', 'Date', 'Status'])

def get_live_temp():
    try:
        response = requests.get(CURRENT_URL, timeout=10).json()
        return round(response['main']['temp'], 1)
    except:
        return None

# --- SESSION STATE ---
if 'daily_history' not in st.session_state:
    st.session_state.daily_history = get_midnight_history()

# --- SIDEBAR & DEBUG ---
st.sidebar.title("Settings")
mode = st.sidebar.selectbox("Mode", ["Winter", "Summer"], index=0)
threshold = 65.0 if mode == "Winter" else 70.0

with st.sidebar.expander("🔍 API Data Inspector"):
    st.write("Current Data in Memory:")
    st.dataframe(st.session_state.daily_history)
    if st.button("Force Refresh History"):
        st.session_state.daily_history = get_midnight_history()
        st.rerun()

# --- DASHBOARD ---
@st.fragment(run_every=60)
def show_dashboard():
    new_temp = get_live_temp()
    now_mtn = datetime.now(LOCAL_TZ)
    current_hour = now_mtn.hour
    
    if new_temp is not None:
        # Append Live Reading
        new_entry = pd.DataFrame({
            'Hour': [current_hour], 
            'Temp': [new_temp], 
            'Date': [now_mtn.date()],
            'Status': ['Live']
        })
        st.session_state.daily_history = pd.concat([st.session_state.daily_history, new_entry], ignore_index=True).drop_duplicates('Hour', keep='last')

        # --- GRAPH ENGINE ---
        chart_df = pd.DataFrame({'Hour': range(24)})
        chart_df = pd.merge(chart_df, st.session_state.daily_history[['Hour', 'Temp']], on='Hour', how='left')
        
        # Ensure we have a starting point for the line
        first_valid = chart_df['Temp'].first_valid_index()
        if first_valid is not None:
             chart_df.loc[0, 'Temp'] = chart_df.loc[first_valid, 'Temp']
        
        chart_df['Temp'] = chart_df['Temp'].interpolate(method='linear')
        chart_df.loc[chart_df['Hour'] > current_hour, 'Temp'] = None 
        chart_df['Target'] = threshold
        chart_df['24h'] = chart_df['Hour'].apply(lambda x: f"{x:02}:00")
        chart_df = chart_df.set_index('24h')

        # --- UI ---
        st.title("The Farm")
        st.markdown(f"**Loveland, CO** | `{now_mtn.strftime('%H:%M:%S')}`")
        
        d_high = st.session_state.daily_history['Temp'].max()
        d_low = st.session_state.daily_history['Temp'].min()

        m1, m2, m3 = st.columns(3)
        m1.metric("Live", f"{new_temp}°F")
        m2.metric("High Today", f"{d_high}°F")
        m3.metric("Low Today", f"{d_low}°F")

        st.write("---")

        col_left, col_right = st.columns([1, 2])
        with col_left:
            st.info(f"Goal: {threshold}°F")
            if new_temp >= threshold: st.success("Condition Met!")

        with col_right:
            st.line_chart(chart_df[['Temp', 'Target']], color=["#00f2ff", "#ff4b4b"])

show_dashboard()
