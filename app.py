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
URL = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=imperial"
LOCAL_TZ = pytz.timezone("US/Mountain")

if 'daily_history' not in st.session_state:
    st.session_state.daily_history = pd.DataFrame(columns=['Time', 'Temp', 'Date'])

# Load Custom Fractal Farmhouse Icon
try:
    farm_icon = Image.open('farm-icon.png')
    st.set_page_config(page_title="The Farm Monitor", page_icon=farm_icon, layout="wide")
except:
    st.set_page_config(page_title="The Farm Monitor", page_icon="🏔️", layout="wide")

def get_live_data():
    try:
        response = requests.get(URL, timeout=10).json()
        return round(response['main']['temp'], 1)
    except:
        return None

# --- SIDEBAR SETTINGS ---
st.sidebar.title("Settings")
now_mtn = datetime.now(LOCAL_TZ)
month = now_mtn.month
default_winter = month not in [6, 7, 8, 9]

mode = st.sidebar.selectbox(
    "Monitoring Mode", 
    ["Winter (Warming Focus)", "Summer (Cooling Focus)"], 
    index=0 if default_winter else 1
)

threshold = 65.0 if "Winter" in mode else 70.0
st.sidebar.info(f"Target Threshold: {threshold}°F")

# --- DASHBOARD FRAGMENT ---
@st.fragment(run_every=60)
def show_dashboard():
    new_temp = get_live_data()
    now_mtn = datetime.now(LOCAL_TZ)
    current_date = now_mtn.date()
    
    if new_temp is not None:
        # Midnight Reset Logic
        if not st.session_state.daily_history.empty:
            if st.session_state.daily_history['Date'].iloc[0] != current_date:
                st.session_state.daily_history = pd.DataFrame(columns=['Time', 'Temp', 'Date'])

        # Append Current Reading
        new_entry = pd.DataFrame({
            'Time': [now_mtn.strftime("%I:%M %p")],
            'Temp': [new_temp],
            'Date': [current_date]
        })
        st.session_state.daily_history = pd.concat([st.session_state.daily_history, new_entry], ignore_index=True)

        # Calculations
        daily_high = st.session_state.daily_history['Temp'].max()
        daily_low = st.session_state.daily_history['Temp'].min()
        
        # --- UI DISPLAY ---
        st.title("The Farm")
        st.markdown(f"**Loveland, CO** | `{now_mtn.strftime('%I:%M:%S %p')}`")
        
        # Metric Layout: Current, High, Low
        m1, m2, m3 = st.columns([1, 1, 1])
        with m1:
            st.metric(label="Live Temp", value=f"{new_temp}°F")
        with m2:
            st.metric(label="High Today", value=f"{daily_high}°F")
        with m3:
            st.metric(label="Low Today", value=f"{daily_low}°F")

        st.write("---")

        # --- CHART & ALERTS ---
        col_left, col_right = st.columns([1, 2])
        
        with col_left:
            if "Winter" in mode:
                if new_temp >= threshold:
                    st.balloons()
                    st.success(f"☀️ Warming up! Currently {new_temp}°F.")
                else:
                    st.info(f"❄️ Waiting for {threshold}°F...")
            else:
                if new_temp <= threshold:
                    st.markdown("### 🌬️ A cool breeze has arrived!")
                    st.toast('Cooling detected!', icon='🌬️')
                else:
                    st.warning(f"🔥 Waiting for {threshold}°F")

        with col_right:
            chart_df = st.session_state.daily_history.copy()
            chart_df['Target'] = threshold
            st.line_chart(chart_df.set_index('Time')[['Temp', 'Target']], color=["#00f2ff", "#ff4b4b"])

show_dashboard()

with st.sidebar:
    st.write("---")
    if st.button("Reset Daily History"):
        st.session_state.daily_history = pd.DataFrame(columns=['Time', 'Temp', 'Date'])
        st.rerun()
