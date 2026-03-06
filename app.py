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

METEO_URL = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}_longitude={LON}&hourly=apparent_temperature&temperature_unit=fahrenheit&timezone=auto"
OWM_URL = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=imperial"

try:
    farm_icon = Image.open('farm-icon.png')
    st.set_page_config(page_title="The Farm", page_icon=farm_icon, layout="wide")
except:
    st.set_page_config(page_title="The Farm", page_icon="🏔️", layout="wide")

# --- DATA FUNCTIONS ---
@st.cache_data(ttl=86400)
def get_historical_normals():
    normals = []
    for h in range(24):
        avg = 32 + (15 * (1 - abs((h-14)/10)))
        normals.append({'Hour': h, 'Normal_Avg': round(avg, 1), 'Normal_Low': round(avg-8, 1), 'Normal_High': round(avg+8, 1)})
    return pd.DataFrame(normals)

def get_all_day_data():
    try:
        response = requests.get(METEO_URL, timeout=10).json()
        times = response['hourly']['time']
        temps = response['hourly']['apparent_temperature']
        data_points = [{'Hour': datetime.fromisoformat(t).replace(tzinfo=pytz.UTC).astimezone(LOCAL_TZ).hour, 'Temperature': round(temp, 1)} 
                       for t, temp in zip(times, temps) if datetime.fromisoformat(t).replace(tzinfo=pytz.UTC).astimezone(LOCAL_TZ).date() == datetime.now(LOCAL_TZ).date()]
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
    if live_temp is not None:
        df.loc[df['Hour'] == current_hour, 'Temperature'] = live_temp

    normals_df = get_historical_normals()
    actual_df = df[df['Hour'] <= current_hour].copy()
    hi_actual, lo_actual = actual_df['Temperature'].max(), actual_df['Temperature'].min()

    # --- UI ---
    st.title("The Farm: Historical Deviations")
    m1, m2, m3 = st.columns(3)
    trend = round(live_temp - actual_df.iloc[-2]['Temperature'], 1) if live_temp and len(actual_df) > 1 else 0.0
    m1.metric("Current (Feels Like)", f"{live_temp}°F", delta=f"{trend}°F", delta_description=f"since {current_hour-1:02}:00")
    m2.metric("Actual High", f"{hi_actual}°F")
    m3.metric("Actual Low", f"{lo_actual}°F")

    # --- ALTAIR CHART ---
    x_axis = alt.X('Hour:Q', title='Time (24h)', scale=alt.Scale(domain=[0, 23]), axis=alt.Axis(labelExpr="datum.value + ':00'"))
    y_axis = alt.Y('Temperature:Q', scale=alt.Scale(zero=False, padding=40), title='Apparent Temp (°F)')

    # 1. Historical Corridor (Muted Orange)
    climate_band = alt.Chart(normals_df).mark_area(opacity=0.2, color='#FFA500').encode(x=x_axis, y='Normal_Low:Q', y2='Normal_High:Q')
    climate_avg = alt.Chart(normals_df).mark_line(strokeDash=[5,5], color='#FFA500', opacity=0.3).encode(x=x_axis, y='Normal_Avg:Q')

    # 2. Target Line (New Lime Green)
    target_line = alt.Chart(pd.DataFrame({'Hour': range(24), 'T': [threshold]*24})).mark_line(
        color='#32CD32', strokeDash=[8,4], strokeWidth=2).encode(x=x_axis, y='T:Q')

    # 3. Actual & Forecast
    df['Status'] = df['Hour'].apply(lambda x: 'Actual' if x <= current_hour else 'Forecast')
    plot_df = pd.concat([df, df[df['Hour'] == current_hour].assign(Status='Forecast')]).sort_values('Hour')
    
    main_line = alt.Chart(plot_df).mark_line(strokeWidth=4).encode(
        x=x_axis, y=y_axis,
        color=alt.Color('Status:N', scale=alt.Scale(domain=['Actual', 'Forecast'], range=['#00f2ff', '#ffffff']), legend=None),
        strokeDash=alt.condition(alt.datum.Status == 'Actual', alt.value([0]), alt.value([5, 5]))
    )

    ball = alt.Chart(df[df['Hour'] == current_hour]).mark_circle(size=250, color='#00f2ff').encode(x=x_axis, y=y_axis)

    st.altair_chart(climate_band + climate_avg + target_line + main_line + ball, use_container_width=True)

    # Features Section
    st.write("---")
    st.subheader("🚀 Features Coming Soon")
    c1, c2 = st.columns(2)
    with c1: st.markdown("* **Precipitation:** Real-time Rain/Snow tracking.")
    with c2: st.markdown("* **Summer AM/PM:** Window optimization alerts.")

show_dashboard()
