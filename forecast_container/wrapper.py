import time
import os
import numpy as np
import pandas as pd
from collections import deque
import streamlit as st
from statsmodels.tsa.holtwinters import Holt
from statsmodels.tsa.statespace.sarimax import SARIMAX
import data_collector

# --- CONFIG ---
WINDOW_SIZE = st.sidebar.slider("Window Size", 50, 300, 100)
SAMPLING_INTERVAL = st.sidebar.slider("Sampling Interval (sec)", 1, 30, 15)
FORECAST_MINUTES = st.sidebar.slider("Forecast Horizon (minutes)", 1, 10, 5)
FORECAST_STEPS = int((FORECAST_MINUTES * 60) / SAMPLING_INTERVAL)

SMOOTHING_LEVEL = st.sidebar.slider("Holt's smoothing level (%)", 0, 100, 80) / 100
SMOOTHING_TREND = st.sidebar.slider("Holt's smoothing trend (%)", 0, 100, 20) / 100

ARIMA_P = st.sidebar.slider("ARIMA p", 0, 5, 2)
ARIMA_D = st.sidebar.slider("ARIMA d", 0, 2, 1)
ARIMA_Q = st.sidebar.slider("ARIMA q", 0, 5, 2)
RETRAIN_INTERVAL = 5

# --- STATE ---
if "cpu_data" not in st.session_state:
    st.session_state.cpu_data = deque(maxlen=WINDOW_SIZE)
    st.session_state.timestamps = deque(maxlen=WINDOW_SIZE)

    initial_data = data_collector.load_initial_data(
        "cpu",
        node=os.getenv('NODE_NAME'),
        w_size=WINDOW_SIZE,
        s_interval=SAMPLING_INTERVAL
    )

    for entry in initial_data[0]['values']:
        st.session_state.cpu_data.append(float(entry[1]))
        st.session_state.timestamps.append(
            pd.to_datetime(entry[0], unit='s', utc=True)
        )

    st.session_state.forecast = []

    st.session_state.step_counter = 0
    st.session_state.model_fit = None
    st.session_state.last_forecast = []

# --- TITLE ---
st.title("Real-Time CPU Monitoring & Forecasting")
st.caption("Using Holt’s Exponential Smoothing and Kalman ARIMA (SARIMA) models")

# --- DATA COLLECTION ---
cpu = data_collector.get_data("cpu", node=os.getenv('NODE_NAME'))
if not cpu:
    st.warning("No CPU data available. Please check your Prometheus setup.")
    time.sleep(SAMPLING_INTERVAL)
    st.rerun()

cpu = float(cpu[0]['value'][1])

# check if cpu is a valid number
if not isinstance(cpu, (int, float)) or np.isnan(cpu) or cpu < 0 or cpu > 100:
    st.warning("Invalid CPU data received. Please check your Prometheus setup.")
    time.sleep(SAMPLING_INTERVAL)
    st.rerun()

timestamp = pd.Timestamp.now(tz='UTC')

st.session_state.cpu_data.append(cpu)
st.session_state.timestamps.append(timestamp)
st.session_state.step_counter += 1


# --- FORECAST ---
forecast_times = []
forecast_holt = []
forecast_karima = []

if len(st.session_state.cpu_data) >= 5:
    try:
        model = Holt(list(st.session_state.cpu_data), initialization_method="estimated")
        fit = model.fit(smoothing_level=SMOOTHING_LEVEL, smoothing_trend=SMOOTHING_TREND, optimized=True)
        forecast_h = fit.forecast(FORECAST_STEPS)
        forecast_h = np.clip(forecast_h, 0, 100)

        # Set the first forecast value to the last actual value
        forecast_holt = [st.session_state.cpu_data[-1]] + list(forecast_h[1:])
        
        # Generate forecast timestamps
        last_time = st.session_state.timestamps[-1]
        forecast_times = [last_time + pd.Timedelta(seconds=SAMPLING_INTERVAL * (i)) for i in range(FORECAST_STEPS)]
    except Exception as e:
        st.warning(f"Holt forecast error: {e}")

if len(st.session_state.cpu_data) > ARIMA_P + ARIMA_Q + ARIMA_D + 5:
    try:
        # Only retrain every N steps
        if st.session_state.step_counter % RETRAIN_INTERVAL == 0 or st.session_state.model_fit is None:
            model = SARIMAX(
                list(st.session_state.cpu_data),
                order=(ARIMA_P, ARIMA_D, ARIMA_Q),
                enforce_stationarity=False,
                enforce_invertibility=False
            )
            st.session_state.model_fit = model.fit(disp=False)

        forecast_ka = st.session_state.model_fit.forecast(steps=FORECAST_STEPS)
        forecast_ka = np.clip(forecast_ka, 0, 100)

        forecast_karima = [st.session_state.cpu_data[-1]] + list(forecast_ka[1:])
        last_time = st.session_state.timestamps[-1]
        forecast_times = [
            last_time + pd.Timedelta(seconds=SAMPLING_INTERVAL * i)
            for i in range(FORECAST_STEPS)
        ]
        st.session_state.last_forecast = (forecast_times, forecast_karima)
    except Exception as e:
        st.warning(f"Karima forecast error: {e}")
        st.session_state.last_forecast = ([], [])

# --- PLOT ---
history_df = pd.DataFrame({
    "timestamp": list(st.session_state.timestamps),
    "CPU (%)": list(st.session_state.cpu_data)
})

forecast_df_holt = pd.DataFrame({
    "timestamp": forecast_times,
    "Holt Forecast (%)": forecast_holt
})

forecast_df_karima = pd.DataFrame({
    "timestamp": forecast_times[:len(forecast_karima)],
    "Karima Forecast (%)": forecast_karima
})

combined_df = history_df.merge(forecast_df_holt, on="timestamp", how="outer")
combined_df = combined_df.merge(forecast_df_karima, on="timestamp", how="outer")
combined_df = combined_df.sort_values("timestamp")

# Display in Berlin time
display_df = combined_df.copy()
display_df['timestamp'] = display_df['timestamp'].dt.tz_convert('Europe/Berlin')

st.line_chart(display_df.set_index("timestamp"))

# --- AUTO REFRESH ---
if SAMPLING_INTERVAL > 0:
    time.sleep(SAMPLING_INTERVAL)
    st.rerun()
