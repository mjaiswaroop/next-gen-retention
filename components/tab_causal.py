"""
components/tab_causal.py — Causal Impact Simulator
==================================================
Streamlit UI for Module 1.
"""

import streamlit as st
import pandas as pd
import requests
import os
import plotly.express as px

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

def render(tenant_id: int):
    st.header("Causal Impact Simulator")
    st.markdown("<div class='centered-subheading'>Use DoWhy structural causal models to estimate the <b>true causal effect</b> of interventions on churn probability, rather than just correlations.</div>", unsafe_allow_html=True)
    
    headers = {"Authorization": f"Bearer {st.session_state.get('token', '')}"}
    
    # Step 1: Select a high-risk customer
    try:
        resp = requests.get(f"{API_BASE}/api/v1/users/high-risk?threshold=0.60", headers=headers)
        if resp.status_code == 200:
            customers = resp.json()
            if not customers:
                st.info("No high-risk customers found to simulate.")
                return
            
            customer_opts = {c["user_id"]: f"{c['email']} (Score: {c['churn_probability']})" for c in customers}
            selected_cid = st.selectbox("Select Customer to Simulate", options=list(customer_opts.keys()), format_func=lambda x: customer_opts[x])
            
            if selected_cid:
                col1, col2 = st.columns(2)
                intervention_var = col1.selectbox("Intervention Variable", ["payment_friction", "support_tickets", "session_failures"])
                
                target_val = 0.0
                if intervention_var == "payment_friction":
                    target_val = col2.slider("Target Payment Friction (0.0 to 1.0)", 0.0, 1.0, 0.0, 0.1)
                else:
                    target_val = col2.number_input(f"Target {intervention_var}", min_value=0.0, value=0.0)
                    
                st.markdown("<br>", unsafe_allow_html=True)
                _, btn_col, _ = st.columns([1, 2, 1])
                with btn_col:
                    simulate_pressed = st.button("Simulate Causal Effect", help="Uses double machine learning (EconML) to predict how much this specific intervention will decrease churn risk for this particular customer.", use_container_width=True)
                    
                if simulate_pressed:
                    with st.spinner("Running do-calculus estimation..."):
                        payload = {
                            "customer_id": selected_cid,
                            "interventions": [
                                {"variable": intervention_var, "value": target_val}
                            ]
                        }
                        c_resp = requests.post(f"{API_BASE}/api/v1/causal/estimate", json=payload, headers=headers)
                        
                        if c_resp.status_code == 200:
                            data = c_resp.json()
                            if "uplift" in data:
                                eff = data
                                st.success(f"Simulation Complete for {intervention_var} -> {target_val}")
                                
                                # Display metrics
                                m1, m2, m3 = st.columns(3)
                                m1.metric("Original Churn Prob.", f"{eff['base_churn_prob']:.2f}")
                                
                                uplift = eff.get('uplift', 0)
                                m2.metric("New Churn Prob.", f"{eff['new_churn_prob']:.2f}", f"{-uplift:.2f}")
                                
                                lower = eff['new_churn_prob'] - (eff['confidence_interval_width']/2)
                                upper = eff['new_churn_prob'] + (eff['confidence_interval_width']/2)
                                m3.metric("95% CI Bounds", f"[{lower:.2f}, {upper:.2f}]")
                                
                                # Plot
                                plot_data = pd.DataFrame([
                                    {"Scenario": "Before Intervention", "Churn Probability": eff['base_churn_prob']},
                                    {"Scenario": f"After do({intervention_var}={target_val})", "Churn Probability": eff['new_churn_prob']}
                                ])
                                fig = px.bar(plot_data, x="Scenario", y="Churn Probability", color="Scenario", range_y=[0, 1])
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.markdown("<div style='text-align: center; padding: 15px; border-radius: 8px; background-color: rgba(255, 204, 0, 0.1); border: 1px solid rgba(255, 204, 0, 0.3); color: #eab308; font-weight: bold;'>No effect estimated. EconML could not find a statistically significant causal link.</div>", unsafe_allow_html=True)
                        else:
                            st.error(f"Estimation failed: {c_resp.text}")
        else:
            st.error("Failed to load customers.")
    except Exception as e:
        st.error(f"Error connecting to API: {e}")
