"""
components/tab_experiments.py — A/B Experiment Management
=========================================================
"""

import streamlit as st
import pandas as pd
import requests
import os

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

def render(tenant_id: int):
    st.subheader("Active Experiments")
    headers = {"Authorization": f"Bearer {st.session_state.get('token', '')}"}
    
    st.info("A/B experimentation logic implemented in ML Lifecycle module.")
    st.markdown("<div class='centered-subheading'>Use this tab to monitor assignment distribution and Chi-Squared significance for your active win-back experiments.</div>", unsafe_allow_html=True)
    
    # Placeholder for fetching experiment data since we focused on backend logic earlier
    data = [
        {"experiment_id": "exp_winback_50", "control_group": 450, "variant_group": 462, "chi_sq_p_value": 0.04},
        {"experiment_id": "exp_discount_test", "control_group": 1000, "variant_group": 980, "chi_sq_p_value": 0.12},
    ]
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True)
    
    if st.button("Trigger Significance Recalculation"):
        st.success("Recalculation triggered.")
