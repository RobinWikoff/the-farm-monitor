import streamlit as st
import requests
import pandas as pd
import altair as alt
from datetime import datetime
import pytz

# --- CONFIG & SECURITY ---
try:
    API_KEY = st.secrets["WEATHER_API_KEY"]
except:
    API_KEY = "6893fccbe935414644a37268660065a8"

LAT, LON = "40.3720", "-105.0579"
LOCAL_TZ = pytz.timezone("US/Mountain")

METEO_URL = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=apparent_temperature&temperature_unit=fahrenheit&timezone=auto"
OWM_URL = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=imperial"

st.set_page_config(page_title="The Farm", page_icon="🏔️", layout="wide")

# --- DATA FUNCTIONS ---
@st.cache_data(ttl=300)
def get_weather_data():
    try:
        f_resp = requests.get(METEO_URL, timeout=10).json()
        times, temps = f_resp['hourly']['time'], f_resp['hourly']['apparent_temperature']
        now_date = datetime.now(LOCAL_TZ).date()
        
        forecast_list = []
        for t, temp in zip(times, temps):
            dt = datetime.fromisoformat(t).replace(tzinfo=pytz.UTC).astimezone(LOCAL_TZ)
            if dt.date() == now_date:
                forecast_list.append({'Hour': dt.hour, 'Temperature': round(temp, 1)})
        
        l_resp = requests.get(OWM_URL, timeout=10).json()
        live = round(l_resp['main']['feels_like'], 1)
        return pd.DataFrame(forecast_list), live
    except:
        return pd.DataFrame(), None

# --- SIDEBAR ---
st.sidebar.title("Settings")
mode = st.sidebar.selectbox("Monitoring Mode", ["Winter (Warming Focus)", "Summer (Cooling Focus)"])
threshold = 65.0 if "Winter" in mode else 70.0

# --- MAIN DASHBOARD ---
st.title("The Farm: How's the Weather?")
now_mtn = datetime.now(LOCAL_TZ)
st.markdown(f"**Loveland, CO** | `{now_mtn.strftime('%H:%M:%S')}`")

df, live_temp = get_weather_data()

if not df.empty and live_temp is not None:
    current_hour = now_mtn.hour
    df.loc[df['Hour'] == current_hour, 'Temperature'] = live_temp
    
    # 1. Metrics
    m1, m2, m3 = st.columns(3)
    actuals = df[df['Hour'] <= current_hour].copy()
    hi, lo = actuals['Temperature'].max(), actuals['Temperature'].min()
    m1.metric("Current (Feels)", f"{live_temp}°F")
    m2.metric("Today's High", f"{hi}°F")
    m3.metric("Today's Low", f"{lo}°F")

    # 2. Assistant Inference
    forecast_future = df[df['Hour'] >= current_hour]
    if "Winter" in mode:
        if live_temp >= threshold: st.success(f"✅ Above target ({threshold}°F). House warming active.")
        else:
            hits = forecast_future[forecast_future['Temperature'] >= threshold]
            if not hits.empty: st.info(f"⏳ Warming: Reaching {threshold}°F at {hits.iloc[0]['Hour']}:00")
            else: st.warning(f"❄️ Alert: Remaining below {threshold}°F today.")
    else:
        if live_temp <= threshold: st.success(f"✅ Below target ({threshold}°F). Open windows.")
        else:
            hits = forecast_future[forecast_future['Temperature'] <= threshold]
            if not hits.empty: st.info(f"🌡️ Cooling: Dropping to {threshold}°F at {hits.iloc[0]['Hour']}:00")
            else: st.warning(f"🔥 Alert: Staying above {threshold}°F today.")

    # 3. Chart Logic
    first_hi_h = actuals[actuals['Temperature'] == hi]['Hour'].iloc[0]
    first_lo_h = actuals[actuals['Temperature'] == lo]['Hour'].iloc[0]
    
    def get_label_cfg(row):
        unit_text = f"{row['Temperature']}°F"
        if row['Hour'] == current_hour: return ("Top", unit_text)
        if row['Hour'] == first_hi_h: return ("Top", unit_text)
        if row['Hour'] == first_lo_h: return ("Bottom", unit_text)
        return ("None", "")

    df[['Lab_Pos', 'Lab_Txt']] = df.apply(lambda r: pd.Series(get_label_cfg(r)), axis=1)
    df['Status'] = df['Hour'].apply(lambda x: 'Actual' if x <= current_hour else 'Forecast')
    
    bridge = df[df['Hour'] == current_hour].copy().assign(Status='Forecast')
    target_df = pd.DataFrame({'Hour': range(24), 'Temperature': [threshold]*24, 'Status': ['Target']*24})
    plot_df = pd.concat([df, bridge, target_df])

    # Scales & Units
    x_ax = alt.X('Hour:Q', axis=alt.Axis(labelFontSize=16, titleFontSize=18, labelExpr="datum.value + ':00'"))
    y_ax = alt.Y('Temperature:Q', scale=alt.Scale(zero=False, padding=60), 
                 axis=alt.Axis(labelFontSize=16, titleFontSize=18, labelExpr="datum.value + '°F'"))
    
    c_scale = alt.Scale(domain=['Actual', 'Forecast', 'Target'], range=['#00f2ff', '#ffffff', '#32CD32'])
    d_scale = alt.Scale(domain=['Actual', 'Forecast', 'Target'], range=[[0], [5, 5], [8, 4]])

    base = alt.Chart(plot_df).encode(x=x_ax, y=y_ax)
    lines = base.mark_line(strokeWidth=4).encode(
        color=alt.Color('Status:N', scale=c_scale, legend=alt.Legend(orient='bottom-left', labelFontSize=14, title=None)),
        strokeDash=alt.StrokeDash('Status:N', scale=d_scale)
    )
    ball = alt.Chart(df[df['Hour'] == current_hour]).mark_circle(size=450, color='#00f2ff').encode(x=x_ax, y=y_ax)
    txt_top = alt.Chart(df[df['Lab_Pos'] == "Top"]).mark_text(dy=-25, fontSize=16, fontWeight='bold', color='white').encode(x=x_ax, y=y_ax, text='Lab_Txt')
    txt_bot = alt.Chart(df[df['Lab_Pos'] == "Bottom"]).mark_text(dy=25, fontSize=16, fontWeight='bold', color='white', baseline='top').encode(x=x_ax, y=y_ax, text='Lab_Txt')

    st.altair_chart((lines + ball + txt_top + txt_bot).properties(height=500).configure_legend(fillColor='#1e1e1e', padding=10), use_container_width=True)

    # 4. Updated Roadmap Section
    st.write("---")
    st.subheader("🚀 Features Coming Soon")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **🌨️ Precipitation Tracker**
        * Real-time Rain/Snow probability.
        * Hourly accumulation forecasts.
        """)
    with col2:
        st.markdown("""
        **🌬️ Summer Optimization**
        * **AM:** Too Warm, Time to Close the Windows.
        * **PM:** Cool Enough, Time to Open the Windows.
        """)
else:
    st.warning("Securely connecting to data feed...")
