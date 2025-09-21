import time
import os
import numpy as np
import pandas as pd
from collections import deque
import streamlit as st
from statsmodels.tsa.holtwinters import Holt
from statsmodels.tsa.statespace.sarimax import SARIMAX
import data_collector
import forecast_analysis

# --- CONFIG ---
WINDOW_SIZE = st.sidebar.slider("Window Size", 50, 300, 120)
SAMPLING_INTERVAL = st.sidebar.slider("Sampling Interval (sec)", 1, 30, 15)
FORECAST_MINUTES = st.sidebar.slider("Forecast Horizon (minutes)", 1, 10, 5)
FORECAST_STEPS = int((FORECAST_MINUTES * 60) / SAMPLING_INTERVAL)

SMOOTHING_LEVEL = st.sidebar.slider("Holt's smoothing level (%)", 0, 100, 50) / 100
SMOOTHING_TREND = st.sidebar.slider("Holt's smoothing trend (%)", 0, 100, 15) / 100

ARIMA_P = st.sidebar.slider("ARIMA p", 0, 5, 2)
ARIMA_D = st.sidebar.slider("ARIMA d", 0, 2, 1)
ARIMA_Q = st.sidebar.slider("ARIMA q", 0, 5, 2)
RETRAIN_INTERVAL = 5

metrics = ["cpu", "memory"]#, "disk", "network"]
metrics_info = {
        "cpu": {
            "caption": "Total usage of the CPU in %",
            "unit": "%"
        },
        "memory": {
            "caption": "Total usage of the main memory in %",
            "unit": "%"
        }
    }

# --- STATE ---
if "metrics_data" not in st.session_state:
    st.session_state.counter = 3
    st.session_state.metrics_data = {}
    st.session_state.timestamps = {}
    st.session_state.forecast = {}
    st.session_state.step_counter = {}
    st.session_state.model_fit = {}
    st.session_state.last_forecast = {}
    for metric in metrics:
        st.session_state.metrics_data[metric] = deque(maxlen=WINDOW_SIZE)
        st.session_state.timestamps[metric] = deque(maxlen=WINDOW_SIZE)
        st.session_state.forecast[metric] = []
        st.session_state.step_counter[metric] = 0
        st.session_state.model_fit[metric] = None
        st.session_state.last_forecast[metric] = []

        initial_data = data_collector.load_initial_data(
            metric,
            node=os.getenv('NODE_NAME'),
            w_size=WINDOW_SIZE,
            s_interval=SAMPLING_INTERVAL
        )

        for entry in initial_data[0]['values']:
            st.session_state.metrics_data[metric].append(float(entry[1]))
            st.session_state.timestamps[metric].append(
                pd.to_datetime(entry[0], unit='s', utc=True)
            )

# --- TITLE ---
st.title("Real-Time metrics forecasting")
st.session_state.counter += 1

for metric in metrics:
    # --- DATA COLLECTION ---
    data = data_collector.get_data(metric, node=os.getenv('NODE_NAME'))
    if not data:
        st.warning(f"No {metric} data available. Please check your Prometheus setup.")
        time.sleep(SAMPLING_INTERVAL)
        st.rerun()

    value = float(data[0]['value'][1])

    # check if value is a valid number
    if not isinstance(value, (int, float)) or np.isnan(value) or value < 0 or value > 100:
        st.warning(f"Invalid {metric} data received. Please check your Prometheus setup.")
        time.sleep(SAMPLING_INTERVAL)
        st.rerun()

    timestamp = pd.Timestamp.now(tz='UTC')

    st.session_state.metrics_data[metric].append(value)
    st.session_state.timestamps[metric].append(timestamp)
    st.session_state.step_counter[metric] += 1


    # --- FORECAST ---
    forecast_times = []
    forecast_holt = []
    forecast_karima = []

    if len(st.session_state.metrics_data[metric]) >= 5:
        try:
            model = Holt(list(st.session_state.metrics_data[metric]), initialization_method="estimated")
            fit = model.fit(smoothing_level=SMOOTHING_LEVEL, smoothing_trend=SMOOTHING_TREND, optimized=True)
            forecast_h = fit.forecast(FORECAST_STEPS)
            forecast_h = np.clip(forecast_h, 0, 100)

            # Set the first forecast value to the last actual value
            forecast_holt = [st.session_state.metrics_data[metric][-1]] + list(forecast_h[1:])

            # If holt detects a large increase, force retrain karima
            if forecast_holt[-1] - forecast_holt[0] > 15:
                st.session_state.step_counter[metric] = RETRAIN_INTERVAL

            # Generate forecast timestamps
            last_time = st.session_state.timestamps[metric][-1]
            forecast_times = [last_time + pd.Timedelta(seconds=SAMPLING_INTERVAL * (i)) for i in range(FORECAST_STEPS)]
        except Exception as e:
            st.warning(f"Holt forecast error: {e}")

    if len(st.session_state.metrics_data[metric]) > ARIMA_P + ARIMA_Q + ARIMA_D + 5:
        try:
            # Only retrain every N steps
            if st.session_state.step_counter[metric] % RETRAIN_INTERVAL == 0 or st.session_state.model_fit[metric] is None:
                model = SARIMAX(
                    list(st.session_state.metrics_data[metric]),
                    order=(ARIMA_P, ARIMA_D, ARIMA_Q),
                    enforce_stationarity=False,
                    enforce_invertibility=False
                )
                st.session_state.model_fit[metric] = model.fit(disp=False)

            forecast_ka = st.session_state.model_fit[metric].forecast(steps=FORECAST_STEPS)
            forecast_ka = np.clip(forecast_ka, 0, 100)

            forecast_karima = [st.session_state.metrics_data[metric][-1]] + list(forecast_ka[1:])
            last_time = st.session_state.timestamps[metric][-1]
            forecast_times = [
                last_time + pd.Timedelta(seconds=SAMPLING_INTERVAL * i)
                for i in range(FORECAST_STEPS)
            ]
            st.session_state.last_forecast = (forecast_times, forecast_karima)
        except Exception as e:
            st.warning(f"Karima forecast error: {e}")
            st.session_state.last_forecast[metric] = ([], [])

    # Analyze forecast errors
    errors = forecast_analysis.analyze_forecast(forecast_holt, forecast_karima, step_seconds=SAMPLING_INTERVAL)
    for err in errors:
        if err["level"] == "error":
            st.error(err["msg"])
            print(f"{timestamp.strftime('%Y-%m-%d %H:%M')} [ERROR] {metric} -> {err['msg']}")
        elif err["level"] == "warning":
            st.warning(err["msg"])
            print(f"{timestamp.strftime('%Y-%m-%d %H:%M')} [WARNING] {metric} -> {err['msg']}")
        elif err["level"] == "info":
            st.info(err["msg"])
            print(f"{timestamp.strftime('%Y-%m-%d %H:%M')} [INFO] {metric} -> {err['msg']}")

    # --- PLOT ---
    history_df = pd.DataFrame({
        "timestamp": list(st.session_state.timestamps[metric]),
        f"{metric} ({metrics_info[metric]['unit']})": list(st.session_state.metrics_data[metric])
    })

    forecast_df_holt = pd.DataFrame({
        "timestamp": forecast_times,
        f"Holt Forecast ({metrics_info[metric]['unit']})": forecast_holt
    })

    forecast_df_karima = pd.DataFrame({
        "timestamp": forecast_times[:len(forecast_karima)],
        f"Karima Forecast ({metrics_info[metric]['unit']})": forecast_karima
    })

    if st.session_state.counter == 4:
        print(f"{metric} history ->\n{history_df.to_csv(index=False)}")
        print(f"{metric} holt ->\n{forecast_df_holt.to_csv(index=False)}")
        print(f"{metric} karima ->\n{forecast_df_karima.to_csv(index=False)}")

    combined_df = history_df.merge(forecast_df_holt, on="timestamp", how="outer")
    combined_df = combined_df.merge(forecast_df_karima, on="timestamp", how="outer")
    combined_df = combined_df.sort_values("timestamp")

    # Display in Berlin time
    st.caption(metrics_info[metric]['caption'])

    display_df = combined_df.copy()
    display_df['timestamp'] = display_df['timestamp'].dt.tz_convert('Europe/Berlin')

    st.line_chart(display_df.set_index("timestamp"))

# --- AUTO REFRESH ---
if SAMPLING_INTERVAL > 0:
    if st.session_state.counter == 4:
        st.session_state.counter = 0
    time.sleep(SAMPLING_INTERVAL)
    st.rerun()
