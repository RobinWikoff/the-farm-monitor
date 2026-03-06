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

METEO_URL = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=apparent_temperature&temperature_unit=fahrenheit&timezone=auto"
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
        temps = response['hourly']['apparent_temperature']
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

    actual_df = df[df['Hour'] <= current_hour].copy()
    forecast_df = df[df['Hour'] >= current_hour].copy()
    
    hi_actual = actual_df['Temperature'].max()
    lo_actual = actual_df['Temperature'].min()
    
    # --- INFERENCE LOGIC ---
    inference_msg = ""
    if live_temp is not None:
        if "Winter" in mode:
            if live_temp >= threshold:
                inference_msg = f"✅ Above target ({threshold}°F). No warming needed."
            else:
                # Find first hour in forecast where temp >= threshold
                target_hit = forecast_df[forecast_df['Temperature'] >= threshold]
                if not target_hit.empty:
                    hit_time = target_hit.iloc[0]['Hour']
                    inference_msg = f"⏳ Below target. Expected to reach {threshold}°F at {hit_time:02}:00."
                else:
                    inference_msg = f"❄️ Remaining below {threshold}°F for the rest of today."
        else: # Summer Mode (Cooling)
            if live_temp <= threshold:
                inference_msg = f"✅ Below target ({threshold}°F). Open those windows!"
            else:
                target_hit = forecast_df[forecast_df['Temperature'] <= threshold]
                if not target_hit.empty:
                    hit_time = target_hit.iloc[0]['Hour']
                    inference_msg = f"🌡️ Too warm. Expected to cool to {threshold}°F at {hit_time:02}:00."
                else:
                    inference_msg = f"🔥 Staying above {threshold}°F for the rest of today."

    # Label Logic (High/Low/Now)
    first_hi_hour = actual_df[actual_df['Temperature'] == hi_actual]['Hour'].iloc[0]
    first_lo_hour = actual_df[actual_df['Temperature'] == lo_actual]['Hour'].iloc[0]
    
    def get_pos(row):
        if row['Hour'] == current_hour: return "Top"
        if row['Hour'] == first_hi_hour: return "Top"
        if row['Hour'] == first_lo_hour: return "Bottom"
        return "None"
    
    df['Label_Pos'] = df.apply(get_pos, axis=1)
    df['Label_Text'] = df['Temperature'].apply(lambda x: f"{x}°")
    df['Status'] = df['Hour'].apply(lambda x: 'Actual' if x <= current_hour else 'Forecast')

    # Chart Prep
    now_row = df[df['Hour'] == current_hour].copy()
    now_row['Status'] = 'Forecast'
    target_data = pd.DataFrame({'Hour': range(24), 'Temperature': [threshold] * 24, 'Status': ['Target'] * 24})
    plot_df = pd.concat([df, now_row, target_data]).sort_values('Hour')

    # --- UI ---
    st.title("The Farm: Apparent Temperature")
    st.markdown(f"**Loveland, CO** | `{now_mtn.strftime('%H:%M:%S')}`")
    
    m1, m2, m3 = st.columns(3)
    prev_temp = actual_df.iloc[-2]['Temperature'] if len(actual_df) > 1 else live_temp
    trend = round(live_temp - prev_temp, 1)
    
    m1.metric("Current (Feels Like)", f"{live_temp}°F", delta=f"{trend}°F", delta_description=f"since {current_hour-1:02}:00")
    m2.metric("Actual High", f"{hi_actual}°F")
    m3.metric("Actual Low", f"{lo_actual}°F")

    # Display Inference
    st.info(inference_msg)

    # --- ALTAIR CHART ---
    x_axis = alt.X('Hour:Q', title='Time (24h)', scale=alt.Scale(domain=[0, 23]), axis=alt.Axis(labelExpr="datum.value + ':00'", grid=True))
    y_axis = alt.Y('Temperature:Q', scale=alt.Scale(zero=False, padding=35), title='Apparent Temp (°F)')
    color_scale = alt.Scale(domain=['Actual', 'Forecast', 'Target'], range=['#00f2ff', '#ffffff', '#FFA500'])

    base = alt.Chart(plot_df).encode(x=x_axis, y=y_axis)
    lines = base.mark_line().encode(
        color=alt.Color('Status:N', scale=color_scale, legend=alt.Legend(title="Type")),
        strokeDash=alt.condition(alt.datum.Status == 'Actual', alt.value([0]), alt.value([5, 5])),
        strokeWidth=alt.condition(alt.datum.Status == 'Target', alt.value(2), alt.value(4))
    )
    ball = alt.Chart(df[df['Hour'] == current_hour]).mark_circle(size=250, color='#00f2ff').encode(x=x_axis, y=y_axis)
    labels_top = alt.Chart(df[df['Label_Pos'] == "Top"]).mark_text(align='center', baseline='bottom', dy=-15, fontSize=15, fontWeight='bold', color='white').encode(x=x_axis, y=y_axis, text='Label_Text')
    labels_bottom = alt.Chart(df[df['Label_Pos'] == "Bottom"]).mark_text(align='center', baseline='top', dy=15, fontSize=15, fontWeight='bold', color='white').encode(x=x_axis, y=y_axis, text='Label_Text')

    st.altair_chart(lines + ball + labels_top + labels_bottom, use_container_width=True)

    # Road Map
    st.write("---")
    st.subheader("🚀 Features Coming Soon")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("* **Precipitation:** Real-time Rain/Snow tracking.\n* **Historical Context:** Temperature vs. Historical averages.")
    with c2:
        st.markdown("* **Summer Optimization:** Window AM/PM alert system.")

show_dashboard()
