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
    st.markdown("Use DoWhy structural causal models to estimate the **true causal effect** of interventions on churn probability, rather than just correlations.")
    
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
                    
                if st.button("Simulate Causal Effect", help="Uses double machine learning (EconML) to predict how much this specific intervention will decrease churn risk for this particular customer."):
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
                            effects = data.get("causal_effects", [])
                            if effects:
                                eff = effects[0]
                                st.success(f"Simulation Complete for {intervention_var} -> {target_val}")
                                
                                # Display metrics
                                m1, m2, m3 = st.columns(3)
                                m1.metric("Original Churn Prob.", f"{eff['estimated_churn_without']:.2f}")
                                m2.metric("New Churn Prob.", f"{eff['estimated_churn_with_intervention']:.2f}", f"{eff['causal_effect_size']:.2f}")
                                m3.metric("95% CI Bounds", f"[{eff['confidence_lower']:.2f}, {eff['confidence_upper']:.2f}]")
                                
                                # Plot
                                plot_data = pd.DataFrame([
                                    {"Scenario": "Before Intervention", "Churn Probability": eff['estimated_churn_without']},
                                    {"Scenario": f"After do({intervention_var}={target_val})", "Churn Probability": eff['estimated_churn_with_intervention']}
                                ])
                                fig = px.bar(plot_data, x="Scenario", y="Churn Probability", color="Scenario", range_y=[0, 1])
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.warning("No effect estimated.")
                        else:
                            st.error(f"Estimation failed: {c_resp.text}")
        else:
            st.error("Failed to load customers.")
    except Exception as e:
        st.error(f"Error connecting to API: {e}")
