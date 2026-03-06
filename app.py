import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz
from PIL import Image

# --- CONFIGURATION ---
try:
    API_KEY = st.secrets["WEATHER_API_KEY"]
except:
    API_KEY = "6893fccbe935414644a37268660065a8"

LAT, LON = "40.3720", "-105.0579"
# Switching back to Current Weather for more frequent "live" updates
URL = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=imperial"
LOCAL_TZ = pytz.timezone("US/Mountain")

# Load Custom Icon
try:
    farm_icon = Image.open('farm-icon.png')
    st.set_page_config(page_title="The Farm Monitor", page_icon=farm_icon, layout="wide")
except:
    st.set_page_config(page_title="The Farm Monitor", page_icon="🏔️", layout="wide")

# --- INITIALIZE MEMORY ---
if 'daily_history' not in st.session_state:
    st.session_state.daily_history = pd.DataFrame(columns=['Time', 'Temp', 'Date'])

def get_live_data():
    try:
        response = requests.get(URL, timeout=10).json()
        return round(response['main']['temp'], 1)
    except:
        return None

# --- DASHBOARD FRAGMENT ---
@st.fragment(run_every=60)
def show_dashboard():
    new_temp = get_live_data()
    now_mtn = datetime.now(LOCAL_TZ)
    current_date = now_mtn.date()
    
    if new_temp is not None:
        # 1. Check for Midnight Reset: If the stored data is from yesterday, clear it.
        if not st.session_state.daily_history.empty:
            if st.session_state.daily_history['Date'].iloc[0] != current_date:
                st.session_state.daily_history = pd.DataFrame(columns=['Time', 'Temp', 'Date'])

        # 2. Add current reading to history
        new_entry = pd.DataFrame({
            'Time': [now_mtn.strftime("%I:%M %p")],
            'Temp': [new_temp],
            'Date': [current_date]
        })
        st.session_state.daily_history = pd.concat([st.session_state.daily_history, new_entry], ignore_index=True)

        # 3. Calculations
        daily_high = st.session_state.daily_history['Temp'].max()
        
        # --- UI DISPLAY ---
        st.title("🚜 The Farm - Environmental Watchdog")
        st.markdown(f"**Loveland, CO** | Status as of `{now_mtn.strftime('%I:%M:%S %p')}`")
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            st.metric(label="Live Temp", value=f"{new_temp}°F")
        with col2:
            st.metric(label="High Since Midnight", value=f"{daily_high}°F")

        # --- GRAPH ---
        with col3:
            # We add the threshold line (65 or 70 based on season)
            month = now_mtn.month
            threshold = 65.0 if month not in [6, 7, 8, 9] else 70.0
            
            chart_df = st.session_state.daily_history.copy()
            chart_df['Target'] = threshold
            
            st.line_chart(chart_df.set_index('Time')[['Temp', 'Target']], color=["#00f2ff", "#ff4b4b"])

show_dashboard()
