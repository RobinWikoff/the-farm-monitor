import streamlit as st
import requests
import pandas as pd
import altair as alt
from datetime import datetime
import pytz

# --- CONFIG ---
API_KEY = "6893fccbe935414644a37268660065a8"
LAT, LON = "40.3720", "-105.0579"
LOCAL_TZ = pytz.timezone("US/Mountain")

METEO_URL = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=apparent_temperature&temperature_unit=fahrenheit&timezone=auto"
OWM_URL = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=imperial"

st.set_page_config(page_title="The Farm", page_icon="🏔️", layout="wide")

# --- DATA FUNCTIONS ---
@st.cache_data(ttl=3600)
def get_weather_data():
    try:
        # Get Forecast
        f_resp = requests.get(METEO_URL, timeout=10).json()
        times = f_resp['hourly']['time']
        temps = f_resp['hourly']['apparent_temperature']
        now_date = datetime.now(LOCAL_TZ).date()
        
        forecast_list = []
        for t, temp in zip(times, temps):
            dt = datetime.fromisoformat(t).replace(tzinfo=pytz.UTC).astimezone(LOCAL_TZ)
            if dt.date() == now_date:
                forecast_list.append({'Hour': dt.hour, 'Temperature': round(temp, 1)})
        
        # Get Live
        l_resp = requests.get(OWM_URL, timeout=10).json()
        live = round(l_resp['main']['feels_like'], 1)
        
        return pd.DataFrame(forecast_list), live
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return pd.DataFrame(), None

# --- UI SETUP ---
st.sidebar.title("Settings")
mode = st.sidebar.selectbox("Monitoring Mode", ["Winter (Warming Focus)", "Summer (Cooling Focus)"])
threshold = 65.0 if "Winter" in mode else 70.0

# --- MAIN DASHBOARD ---
st.title("How's the Weather?")
now_mtn = datetime.now(LOCAL_TZ)
st.markdown(f"**Loveland, CO** | `{now_mtn.strftime('%H:%M:%S')}`")

df, live_temp = get_weather_data()

if not df.empty:
    current_hour = now_mtn.hour
    
    # 1. Metrics
    m1, m2, m3 = st.columns(3)
    actuals = df[df['Hour'] <= current_hour]
    m1.metric("Current (Feels)", f"{live_temp}°F")
    m2.metric("Today's High", f"{df['Temperature'].max()}°F")
    m3.metric("Today's Low", f"{df['Temperature'].min()}°F")

    # 2. Assistant Logic (Safe Check)
    forecast_future = df[df['Hour'] >= current_hour]
    if "Winter" in mode:
        if live_temp >= threshold:
            st.success(f"✅ Above target ({threshold}°F). House should be warming up!")
        else:
            hits = forecast_future[forecast_future['Temperature'] >= threshold]
            if not hits.empty:
                st.info(f"⏳ Warming: Reaching {threshold}°F at {hits.iloc[0]['Hour']}:00")
            else:
                st.warning(f"❄️ Stay bundled: Staying below {threshold}°F today.")
    else:
        if live_temp <= threshold:
            st.success(f"✅ Below target ({threshold}°F). Open those windows!")
        else:
            hits = forecast_future[forecast_future['Temperature'] <= threshold]
            if not hits.empty:
                st.info(f"🌡️ Cooling: Dropping to {threshold}°F at {hits.iloc[0]['Hour']}:00")
            else:
                st.warning(f"🔥 Heads up: Staying above {threshold}°F today.")

    # 3. Chart with Large Text
    x_axis = alt.X('Hour:Q', axis=alt.Axis(labelFontSize=16, titleFontSize=18, labelExpr="datum.value + ':00'"))
    y_axis = alt.Y('Temperature:Q', scale=alt.Scale(zero=False, padding=40), axis=alt.Axis(labelFontSize=16, titleFontSize=18))

    # Prep Plotting Data
    target_df = pd.DataFrame({'Hour': range(24), 'Temperature': [threshold]*24, 'Status': ['Target']*24})
    df['Status'] = df['Hour'].apply(lambda x: 'Actual' if x <= current_hour else 'Forecast')
    plot_df = pd.concat([df, target_df])

    color_scale = alt.Scale(domain=['Actual', 'Forecast', 'Target'], range=['#00f2ff', '#ffffff', '#32CD32'])
    dash_scale = alt.Scale(domain=['Actual', 'Forecast', 'Target'], range=[[0], [5, 5], [8, 4]])

    chart = alt.Chart(plot_df).mark_line(strokeWidth=4).encode(
        x=x_axis, y=y_axis,
        color=alt.Color('Status:N', scale=color_scale, legend=alt.Legend(orient='bottom-left', labelFontSize=14)),
        strokeDash=alt.StrokeDash('Status:N', scale=dash_scale)
    ).properties(height=450)

    ball = alt.Chart(pd.DataFrame({'Hour': [current_hour], 'Temperature': [live_temp]})).mark_circle(size=400, color='#00f2ff').encode(x=x_axis, y=y_axis)

    st.altair_chart((chart + ball).configure_legend(fillColor='#1e1e1e', padding=10), use_container_width=True)
else:
    st.warning("Waiting for weather data to refresh...")
