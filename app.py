import streamlit as st
import requests
import pandas as pd
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

METEO_URL = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=temperature_2m&temperature_unit=fahrenheit&timezone=auto&past_days=1"
OWM_URL = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=imperial"

try:
    farm_icon = Image.open('farm-icon.png')
    st.set_page_config(page_title="The Farm", page_icon=farm_icon, layout="wide")
except:
    st.set_page_config(page_title="The Farm", page_icon="🏔️", layout="wide")

# --- DATA FUNCTIONS ---
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
                data_points.append({'Hour': dt.hour, 'Temperature': round(temp, 1), 'Date': dt.date()})
        return pd.DataFrame(data_points)
    except:
        return pd.DataFrame(columns=['Hour', 'Temperature', 'Date'])

def get_live_temp():
    try:
        response = requests.get(OWM_URL, timeout=10).json()
        return round(response['main']['temp'], 1)
    except:
        return None

# --- SESSION STATE ---
if 'daily_history' not in st.session_state or st.session_state.daily_history.empty:
    st.session_state.daily_history = get_historical_data()

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
    
    if live_temp is not None:
        if not st.session_state.daily_history.empty and st.session_state.daily_history['Date'].iloc[0] != now_mtn.date():
            st.session_state.daily_history = get_historical_data()

        # Track trend
        prev_temp = st.session_state.daily_history['Temperature'].iloc[-1] if not st.session_state.daily_history.empty else live_temp
        new_entry = pd.DataFrame({'Hour': [current_hour], 'Temperature': [live_temp], 'Date': [now_mtn.date()]})
        st.session_state.daily_history = pd.concat([st.session_state.daily_history, new_entry], ignore_index=True).drop_duplicates('Hour', keep='last')

        # --- GRAPH ENGINE ---
        chart_df = pd.DataFrame({'Hour': range(24)})
        chart_df = pd.merge(chart_df, st.session_state.daily_history[['Hour', 'Temperature']], on='Hour', how='left')
        
        # 1. Temperature Line
        chart_df['Temperature'] = chart_df['Temperature'].interpolate(method='linear')
        chart_df.loc[chart_df['Hour'] > current_hour, 'Temperature'] = None 
        
        # 2. Threshold Line
        chart_df['Target'] = threshold
        
        # 3. VERTICAL LINE TRICK
        # We create a column that is null everywhere except the current hour
        # We set it to 100 so it stretches from bottom to top of the chart
        chart_df['Now'] = None
        chart_df.loc[chart_df['Hour'] == current_hour, 'Now'] = 100 

        chart_df['24h'] = chart_df['Hour'].apply(lambda x: f"{x:02}:00")
        chart_df = chart_df.set_index('24h')

        # --- UI ---
        st.title("The Farm")
        st.markdown(f"**Loveland, CO** | `{now_mtn.strftime('%H:%M:%S')}`")
        
        d_high = st.session_state.daily_history['Temperature'].max()
        d_low = st.session_state.daily_history['Temperature'].min()
        delta = round(live_temp - prev_temp, 1)

        m1, m2, m3 = st.columns(3)
        m1.metric("Live", f"{live_temp}°F", delta=f"{delta}°F" if delta != 0 else None)
        m2.metric("High Today", f"{d_high}°F")
        m3.metric("Low Today", f"{d_low}°F")

        st.write("---")

        col_left, col_right = st.columns([1, 2])
        with col_left:
            if "Winter" in mode:
                if live_temp >= threshold: st.success(f"☀️ Warming up! Currently {live_temp}°F.")
                else: st.info(f"❄️ Waiting for {threshold}°F.")
            else:
                if live_temp <= threshold: st.success("### 🌬️ Cool breeze has arrived!")
                else: st.warning(f"🔥 Waiting for {threshold}°F")

        with col_right:
            # We add 'Now' to the list of plotted columns
            st.line_chart(
                chart_df[['Temperature', 'Target', 'Now']], 
                color=["#00f2ff", "#ff4b4b", "#ffffff"], # White for the 'Now' line
                y_label="Degrees (°F)"
            )

show_dashboard()
