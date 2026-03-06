import streamlit as st
import requests
import pandas as pd
import altair as alt
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

METEO_URL = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=temperature_2m&temperature_unit=fahrenheit&timezone=auto"
OWM_URL = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=imperial"

try:
    farm_icon = Image.open('farm-icon.png')
    st.set_page_config(page_title="The Farm", page_icon=farm_icon, layout="wide")
except:
    st.set_page_config(page_title="The Farm", page_icon="🏔️", layout="wide")

# --- DATA FUNCTIONS ---
def get_all_day_data():
    try:
        response = requests.get(METEO_URL, timeout=10).json()
        now_mtn = datetime.now(LOCAL_TZ)
        times = response['hourly']['time']
        temps = response['hourly']['temperature_2m']
        
        data_points = []
        for t, temp in zip(times, temps):
            dt = datetime.fromisoformat(t).replace(tzinfo=pytz.UTC).astimezone(LOCAL_TZ)
            if dt.date() == now_mtn.date():
                data_points.append({'Hour': dt.hour, 'Temperature': round(temp, 1)})
        return pd.DataFrame(data_points)
    except:
        return pd.DataFrame(columns=['Hour', 'Temperature'])

def get_live_temp():
    try:
        response = requests.get(OWM_URL, timeout=10).json()
        return round(response['main']['temp'], 1)
    except:
        return None

if 'daily_data' not in st.session_state:
    st.session_state.daily_data = get_all_day_data()

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
    
    df = st.session_state.daily_data.copy()
    
    # Calculate Delta (Trend) before updating with live temp
    # We compare live_temp to the most recent historical hour (current_hour or current_hour-1)
    prev_hour_val = df.loc[df['Hour'] == (current_hour - 1 if current_hour > 0 else 0), 'Temperature
