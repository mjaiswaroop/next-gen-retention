"""
components/tab_emotion.py
"""
import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
import plotly.express as px
from datetime import datetime, timezone, timedelta

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

def render(tenant_id: int):
    st.header("Emotion-Aware Risk Timeline")
    st.markdown("<div class='centered-subheading'>Monitor rolling EWMA emotional deterioration from support tickets using Transformer-based NLP.</div>", unsafe_allow_html=True)
    
    headers = {"Authorization": f"Bearer {st.session_state.get('token', '')}"}
    
    # 1. Simulate an incoming ticket to test the emotion engine
    with st.expander("Simulate Incoming Ticket"):
        mock_customers = ["5482-NUPNA", "cust_123", "8472-ABC", "1192-XYZ", "9941-RPO", "7712-QWE"]
        col1, col2 = st.columns([1, 3])
        cust_id = col1.selectbox("Customer ID", options=mock_customers)
        ticket_text = col2.text_area("Ticket Body", value="This software is completely unacceptable. We wasted hours trying to configure it and support is not responding. I want a refund now.")
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Analyze Ticket Emotion", help="Passes the ticket text through a local HuggingFace sentiment/emotion model (e.g. RoBERTa) to detect anger, frustration, or sadness."):
            with st.spinner("Running HuggingFace pipeline..."):
                payload = {
                    "customer_id": cust_id,
                    "ticket_id": f"TKT-{int(datetime.now().timestamp())}",
                    "ticket_text": ticket_text
                }
                resp = requests.post(f"{API_BASE}/api/v1/emotion/analyze", json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    st.success(f"Detected Emotion: **{data['emotion'].upper()}** (Confidence: {data['confidence']:.2f})")
                    st.info(f"Emotion Risk Score: {data['emotion_risk_score']:.2f} | Rolling EWMA: {data['rolling_signal']:.2f}")
                    if data["alert_triggered"]:
                        st.error("🚨 ALERT: Rapid Emotional Deterioration Detected (>0.3 spike in 7 days). Priority Campaign Queued.")
                else:
                    st.error(f"Analysis failed: {resp.text}")

    st.divider()
    
    # 2. View Timeline
    st.subheader("Customer Timeline (Mock Data for UI)")
    st.markdown("<div class='centered-subheading'>This timeline tracks the <i>emotion_churn_signal</i> (7-day EWMA) over the past 90 days.</div>", unsafe_allow_html=True)
    
    # Generate mock EWMA timeline data
    dates = pd.date_range(end=datetime.now(timezone.utc), periods=90, freq='D')
    # Create a random walk that spikes towards the end
    base_scores = np.random.normal(0, 0.05, 90).cumsum()
    # Normalize between 0 and 0.3
    base_scores = (base_scores - base_scores.min()) / (base_scores.max() - base_scores.min()) * 0.3
    # Spike the last 10 days
    base_scores[-10:] += np.linspace(0, 0.5, 10)
    
    df_plot = pd.DataFrame({
        "Date": dates,
        "Rolling Emotion Signal": base_scores
    })
    
    fig = px.line(df_plot, x="Date", y="Rolling Emotion Signal", title="90-Day Emotional Deterioration Signal")
    fig.add_hline(y=0.6, line_dash="dash", line_color="red", annotation_text="High Risk Threshold")
    st.plotly_chart(fig, use_container_width=True)
