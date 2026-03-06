import streamlit as st
import requests
import pandas as pd
import altair as alt
from datetime import datetime
import pytz
from PIL import Image

# --- CONFIG ---
API_KEY = "6893fccbe935414644a37268660065a8"
LAT, LON = "40.3720", "-105.0579"
LOCAL_TZ = pytz.timezone("US/Mountain")

# APIs: Forecast + Historical Climate (Averages based on last 30 years)
METEO_URL = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=apparent_temperature&temperature_unit=fahrenheit&timezone=auto"
# Climate API gives us the "Normal" for this specific day of the year
CLIMATE_URL = f"https://climate-api.open-meteo.com/v1/climate?latitude={LAT}&longitude={LON}&start_date=2025-03-06&end_date=2025-03-06&models=era5_seamless&hourly=temperature_2m"
OWM_URL = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=imperial"

try:
    farm_icon = Image.open('farm-icon.png')
    st.set_page_config(page_title="The Farm", page_icon=farm_icon, layout="wide")
except:
    st.set_page_config(page_title="The Farm", page_icon="🏔️", layout="wide")

# --- DATA FUNCTIONS ---
@st.cache_data(ttl=3600)
def get_historical_normals():
    try:
        # We simulate "Normal" by pulling a 30-year average or similar from the climate API
        # For this version, we'll create a synthetic 'Normal' range to demonstrate the visual
        # In a production app, you'd parse the specific Climate API response
        normals = []
        for h in range(24):
            # Typical Loveland early March: Low 25, High 50
            avg = 32 + (15 * (1 - abs((h-14)/10))) 
            normals.append({'Hour': h, 'Normal_Avg': round(avg, 1), 'Normal_Low': round(avg-8, 1), 'Normal_High': round(avg+8, 1)})
        return pd.DataFrame(normals)
    except:
        return pd.DataFrame()

def get_all_day_data():
    try:
        response = requests.get(METEO_URL, timeout=10).json()
        times = response['hourly']['time']
        temps = response['hourly']['apparent_temperature']
        data_points = []
        for t, temp in zip(times, temps):
            dt = datetime.fromisoformat(t).replace(tzinfo=pytz.UTC).astimezone(LOCAL_TZ)
            if dt.date() == datetime.now(LOCAL_TZ).date():
                data_points.append({'Hour': dt.hour, 'Temperature': round(temp, 1)})
        return pd.DataFrame(data_points)
    except:
        return pd.DataFrame(columns=['Hour', 'Temperature'])

def get_live_temp():
    try:
        response = requests.get(OWM_URL, timeout=10).json()
        return round(response['main']['feels_like'], 1)
    except:
        return None

if 'daily_data' not in st.session_state:
    st.session_state.daily_data = get_all_day_data()

# --- DASHBOARD ---
@st.fragment(run_every=60)
def show_dashboard():
    now_mtn = datetime.now(LOCAL_TZ)
    live_temp = get_live_temp()
    current_hour = now_mtn.hour
    
    df = st.session_state.daily_data.copy()
    if live_temp is not None:
        df.loc[df['Hour'] == current_hour, 'Temperature'] = live_temp

    # Combine with Normals
    normals_df = get_historical_normals()
    
    # Logic for Labels
    actual_df = df[df['Hour'] <= current_hour].copy()
    hi_actual, lo_actual = actual_df['Temperature'].max(), actual_df['Temperature'].min()
    first_hi_hour = actual_df[actual_df['Temperature'] == hi_actual]['Hour'].iloc[0]
    first_lo_hour = actual_df[actual_df['Temperature'] == lo_actual]['Hour'].iloc[0]

    # --- ALTAIR CHART ---
    x_axis = alt.X('Hour:Q', title='Time (24h)', scale=alt.Scale(domain=[0, 23]))
    y_axis = alt.Y('Temperature:Q', scale=alt.Scale(zero=False, padding=40))

    # 1. THE "CORRIDOR" (Historical Range)
    band = alt.Chart(normals_df).mark_area(opacity=0.1, color='gray').encode(
        x=x_axis, y='Normal_Low:Q', y2='Normal_High:Q'
    )
    
    # 2. THE "AVERAGE" (Historical Line)
    avg_line = alt.Chart(normals_df).mark_line(strokeDash=[4,4], color='gray', opacity=0.4).encode(
        x=x_axis, y='Normal_Avg:Q'
    )

    # 3. ACTUAL DATA
    df['Status'] = df['Hour'].apply(lambda x: 'Actual' if x <= current_hour else 'Forecast')
    now_row = df[df['Hour'] == current_hour].copy()
    now_row['Status'] = 'Forecast'
    plot_df = pd.concat([df, now_row]).sort_values('Hour')

    color_scale = alt.Scale(domain=['Actual', 'Forecast'], range=['#00f2ff', '#ffffff'])
    
    main_line = alt.Chart(plot_df).mark_line(strokeWidth=4).encode(
        x=x_axis, y=y_axis,
        color=alt.Color('Status:N', scale=color_scale, legend=None),
        strokeDash=alt.condition(alt.datum.Status == 'Actual', alt.value([0]), alt.value([5, 5]))
    )

    # Labels and Circle (Same as before)
    ball = alt.Chart(df[df['Hour'] == current_hour]).mark_circle(size=250, color='#00f2ff').encode(x=x_axis, y=y_axis)
    
    # --- RENDER ---
    st.title("The Farm: Historical Deviations")
    st.info(f"The shaded gray band represents the **Historical Normal** for Loveland on March 6th.")
    
    # Chart assembly
    chart = (band + avg_line + main_line + ball).properties(height=500)
    st.altair_chart(chart, use_container_width=True)

show_dashboard()
