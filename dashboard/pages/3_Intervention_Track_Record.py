import streamlit as st
import pandas as pd
import requests

from dashboard import check_auth, get_api_headers

st.set_page_config(page_title="Intervention Track Record", page_icon="📈", layout="wide")

if not check_auth():
    st.stop()

st.title("Closed-Loop Outcome Tracking")
st.markdown("Validates causal inference model predictions against 30-day actual churn outcomes.")

@st.cache_data(ttl=60)
def fetch_validation_report():
    resp = requests.get("http://localhost:8000/api/v1/causal/validation-report", headers=get_api_headers())
    if resp.status_code == 200:
        return resp.json()
    st.error(f"Failed to fetch validation report: {resp.text}")
    return {}

report = fetch_validation_report()

if report:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Interventions", report.get("total_interventions", 0))
    col2.metric("Pending (Under 30 days)", report.get("pending", 0))
    col3.metric("Successful Saves", report.get("success", 0))
    col4.metric("Actual Success Rate", f"{report.get('actual_success_rate', 0):.1%}")

    st.subheader("Performance vs Model Expectations")
    predicted = report.get("average_predicted_uplift", 0)
    actual = report.get("actual_success_rate", 0)
    
    delta = actual - predicted
    st.metric("Model Calibration Error (Actual vs Predicted)", f"{delta:+.1%}")
    
    if delta < -0.05:
        st.warning("Model is overconfident. Causal uplift predictions are higher than actual outcomes.")
    elif delta > 0.05:
        st.success("Model is conservative. Interventions are performing better than expected.")
    else:
        st.info("Model is well-calibrated.")
