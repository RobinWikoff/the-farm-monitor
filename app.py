import streamlit as st
import requests
import pandas as pd
import altair as alt
from datetime import datetime
import pytz

# --- CONFIG ---
try:
    API_KEY = st.secrets["WEATHER_API_KEY"]
except:
    # Fallback for local testing
    API_KEY = "6893fccbe935414644a37268660065a8"

LAT, LON = "40.3720", "-105.0579"
LOCAL_TZ = pytz.timezone("US/Mountain")

METEO_URL = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=apparent_temperature&temperature_unit=fahrenheit&timezone=auto"
OWM_URL = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=imperial"

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
        times, temps = response['hourly']['time'], response['hourly']['apparent_temperature']
        now_date = datetime.now(LOCAL_TZ).date()
        data = []
        for t, temp in zip(times, temps):
            dt = datetime.fromisoformat(t).replace(tzinfo=pytz.UTC).astimezone(LOCAL_TZ)
            if dt.date() == now_date:
                data.append({'Hour': dt.hour, 'Temperature': round(temp, 1)})
        return pd.DataFrame(data)
    except:
        return pd.DataFrame(columns=['Hour', 'Temperature'])

def get_live_temp():
    try:
        response = requests.get(OWM_URL, timeout=10).json()
        return round(response['main']['feels_like'], 1)
    except: return None

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
    
    st.title("The Farm: Historical Deviations")
    m1, m2, m3 = st.columns(3)
    trend = round(live_temp - actual_df.iloc[-2]['Temperature'], 1) if live_temp and len(actual_df) > 1 else 0.0
    m1.metric("Current (Feels Like)", f"{live_temp}°F", delta=f"{trend}°F")
    m2.metric("Actual High", f"{actual_df['Temperature'].max()}°F")
    m3.metric("Actual Low", f"{actual_df['Temperature'].min()}°F")

    # --- CHART CONFIG ---
    x_axis = alt.X('Hour:Q', title='Time (24h)', scale=alt.Scale(domain=[0, 23]), 
                   axis=alt.Axis(labelExpr="datum.value + ':00'", labelFontSize=12, titleFontSize=14))
    y_axis = alt.Y('Temperature:Q', scale=alt.Scale(zero=False, padding=40), title='Apparent Temp (°F)',
                   axis=alt.Axis(labelFontSize=12, titleFontSize=14))

    # 1. Historical Corridor
    band = alt.Chart(normals_df).mark_area(opacity=0.2, color='#FFA500').encode(x=x_axis, y='Normal_Low:Q', y2='Normal_High:Q')
    avg_line = alt.Chart(normals_df).mark_line(strokeDash=[5,5], color='#FFA500', opacity=0.3).encode(x=x_axis, y='Normal_Avg:Q')

    # 2. DATA PREP
    target_df = pd.DataFrame({'Hour': list(range(24)), 'Temperature': [threshold]*24, 'Status': ['Target']*24})
    df['Status'] = df['Hour'].apply(lambda x: 'Actual' if x <= current_hour else 'Forecast')
    bridge = df[df['Hour'] == current_hour].copy().assign(Status='Forecast')
    plot_df = pd.concat([df, bridge, target_df]).sort_values('Hour')

    # 3. MAPPING SCALES (Fixes the nesting error)
    color_scale = alt.Scale(
        domain=['Actual', 'Forecast', 'Target'],
        range=['#00f2ff', '#ffffff', '#32CD32']
    )
    
    # Define dash patterns for each status
    dash_scale = alt.Scale(
        domain=['Actual', 'Forecast', 'Target'],
        range=[[0], [5, 5], [8, 4]]  # [Solid, Dotted, Dashed]
    )

    main_chart = alt.Chart(plot_df).mark_line(strokeWidth=4).encode(
        x=x_axis,
        y=y_axis,
        color=alt.Color('Status:N', scale=color_scale, legend=alt.Legend(orient='bottom-left', labelFontSize=12, title=None)),
        strokeDash=alt.StrokeDash('Status:N', scale=dash_scale, legend=None) # Map dash pattern to status
    )

    ball = alt.Chart(df[df['Hour'] == current_hour]).mark_circle(size=300, color='#00f2ff').encode(x=x_axis, y=y_axis)

    # 4. FINAL RENDER
    st.altair_chart((band + avg_line + main_chart + ball).properties(height=450).configure_legend(
        fillColor='#1e1e1e', padding=10, cornerRadius=5, strokeColor='gray'
    ), use_container_width=True)

    st.write("---")
    st.subheader("🚀 Features Coming Soon")
    st.markdown("* **Precipitation:** Real-time Rain/Snow tracking.\n* **Summer AM/PM:** Window optimization alerts.")

show_dashboard()
