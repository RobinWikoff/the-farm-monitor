import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
from PIL import Image

# --- CONFIGURATION & SECURITY ---
try:
    API_KEY = st.secrets["WEATHER_API_KEY"]
except:
    API_KEY = "6893fccbe935414644a37268660065a8"

LAT, LON = "40.3720", "-105.0579"
# Switching to the Forecast API to get "history" for the current day
URL = f"https://api.openweathermap.org/data/2.5/forecast?lat={LAT}&lon={LON}&appid={API_KEY}&units=imperial"
LOCAL_TZ = pytz.timezone("US/Mountain")

st.set_page_config(page_title="The Farm Monitor", page_icon="🏔️", layout="wide")

# Load Custom Icon
try:
    farm_icon = Image.open('farm-icon.png')
    st.set_page_config(page_title="The Farm Monitor", page_icon=farm_icon, layout="wide")
except:
    pass

# --- DATA FETCHING (CACHED) ---
@st.cache_data(ttl=600) # Only fetch from the web once every 10 minutes
def get_day_data():
    try:
        response = requests.get(URL, timeout=10).json()
        list_of_temps = response['list']
        
        # We filter the list to only include readings from TODAY in Mountain Time
        today = datetime.now(LOCAL_TZ).date()
        daily_history = []
        
        for entry in list_of_temps:
            # Convert UTC timestamp to Mountain Time
            dt_utc = datetime.fromtimestamp(entry['dt'], tz=pytz.UTC)
            dt_mountain = dt_utc.astimezone(LOCAL_TZ)
            
            if dt_mountain.date() == today:
                daily_history.append({
                    'Time': dt_mountain.strftime("%I:%M %p"),
                    'Temperature': round(entry['main']['temp'], 1),
                    'Timestamp': dt_mountain # Keep for sorting
                })
        
        df = pd.DataFrame(daily_history).sort_values('Timestamp')
        return df
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

# --- SIDEBAR SETTINGS ---
st.sidebar.title("🚜 The Farm Settings")
threshold = st.sidebar.slider("Temperature Threshold", 60, 80, 70)

# --- DASHBOARD FRAGMENT ---
@st.fragment(run_every=60)
def render_dashboard():
    df = get_day_data()
    
    if not df.empty:
        # 1. Calculate Real Daily Stats
        current_temp = df['Temperature'].iloc[-1]
        daily_high = df['Temperature'].max()
        last_updated = datetime.now(LOCAL_TZ).strftime("%I:%M:%S %p")
        
        # 2. Header
        st.title("🚜 The Farm - Environmental Watchdog")
        st.markdown(f"**Loveland, CO** | Last Checked: `{last_updated}`")
        
        # 3. Metrics
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            st.metric(label="Current Temp", value=f"{current_temp}°F")
        with col2:
            st.metric(label="Today's True High", value=f"{daily_high}°F")
        
        # 4. Alerts
        if current_temp <= threshold:
            st.markdown("### 🌬️ A cool breeze has arrived!")
            st.toast('Cooling detected!', icon='🌬️')
        else:
            st.warning(f"🔥 Waiting for {threshold}°F (Current: {current_temp}°F)")

        # 5. The Graph (Entire Day)
        with col3:
            # Add threshold line to the chart data
            df['Target'] = threshold
            st.line_chart(df.set_index('Time')[['Temperature', 'Target']], 
                          color=["#00f2ff", "#ff4b4b"])
    else:
        st.info("Gathering today's data... check back in a moment.")

render_dashboard()
