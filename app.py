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
    
    # Calculate Trend and identify the comparison hour
    comp_hour = current_hour - 1 if current_hour > 0 else 0
    prev_hour_val = df.loc[df['Hour'] == comp_hour, 'Temperature'].values
    
    delta = 0.0
    if live_temp is not None and len(prev_hour_val) > 0:
        delta = round(live_temp - prev_hour_val[0], 1)

    if live_temp is not None:
        df.loc[df['Hour'] == current_hour, 'Temperature'] = live_temp
    
    # --- CHART DATA PREP ---
    df['Status'] = df['Hour'].apply(lambda x: 'Actual' if x <= current_hour else 'Forecast')
    now_row = df[df['Hour'] == current_hour].copy()
    now_row['Status'] = 'Forecast'
    
    target_data = pd.DataFrame({
        'Hour': range(24),
        'Temperature': [threshold] * 24,
        'Status': ['Target'] * 24
    })
    
    plot_df = pd.concat([df, now_row, target_data]).sort_values('Hour')

    # --- ALTAIR CHARTING ---
    x_axis = alt.X('Hour:Q', title='Time (24h)', scale=alt.Scale(domain=[0, 23]),
                   axis=alt.Axis(labelExpr="datum.value + ':00'", grid=True))
    y_axis = alt.Y('Temperature:Q', scale=alt.Scale(zero=False), title='Temperature (°F)')

    color_scale = alt.Scale(
        domain=['Actual', 'Forecast', 'Target'], 
        range=['#00f2ff', '#ffffff', '#FFA500']
    )

    chart = alt.Chart(plot_df).mark_line().encode(
        x=x_axis,
        y=y_axis,
        color=alt.Color('Status:N', scale=color_scale, legend=alt.Legend(title="Legend")),
        strokeDash=alt.condition(
            alt.datum.Status == 'Actual',
            alt.value([0]), 
            alt.value([5, 5]) 
        ),
        strokeWidth=alt.condition(
            alt.datum.Status == 'Target',
            alt.value(2),
            alt.value(4)
        )
    )

    ball = alt.Chart(df[df['Hour'] == current_hour]).mark_circle(size=250, color='#00f2ff').encode(x=x_axis, y=y_axis)
    final_chart = (chart + ball).properties(height=450)

    # --- UI ---
    st.title("The Farm")
    st.markdown(f"**Loveland, CO** | `{now_mtn.strftime('%H:%M:%S')}`")
    
    m1, m2, m3 = st.columns(3)
    # Added "since HH:00" to the metric label
    m1.metric(f"Current (since {comp_hour:02}:00)", f"{live_temp}°F", delta=f"{delta}°F" if delta != 0 else None)
    m2.metric("High Today", f"{df['Temperature'].max()}°F")
    m3.metric("Low Today", f"{df['Temperature'].min()}°F")

    st.write("---")
    st.altair_chart(final_chart, use_container_width=True)

show_dashboard()
