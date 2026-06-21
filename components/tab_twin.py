"""
components/tab_twin.py
"""
import streamlit as st
import pandas as pd
import requests
import os
import plotly.express as px
import numpy as np

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

def render(tenant_id: int):
    st.header("Digital Twin Simulator")
    st.markdown("Run 1000 Monte Carlo simulations on a customer's digital twin (LSTM/Markov Chain) to predict ROI for different intervention scenarios.")
    
    headers = {"Authorization": f"Bearer {st.session_state.get('token', '')}"}
    
    try:
        resp = requests.get(f"{API_BASE}/api/v1/users/high-risk?threshold=0.60", headers=headers)
        if resp.status_code == 200:
            customers = resp.json()
            if not customers:
                st.info("No high-risk customers found to simulate.")
                return
            
            customer_opts = {c["user_id"]: f"{c['email']} (Score: {c['churn_probability']})" for c in customers}
            selected_cid = st.selectbox("Select Customer to Simulate", options=list(customer_opts.keys()), format_func=lambda x: customer_opts[x])
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Run Monte Carlo Simulations", help="Spawns 500 parallel universe simulations branching from this customer's current state to probabilistically determine which sequence of future actions leads to the lowest churn risk."):
                with st.spinner("Running 1000 simulations per scenario..."):
                    payload = {
                        "customer_id": selected_cid,
                        "scenarios": ["no_intervention", "discount_15", "product_fix"]
                    }
                    t_resp = requests.post(f"{API_BASE}/api/v1/twin/simulate", json=payload, headers=headers)
                    
                    if t_resp.status_code == 200:
                        data = t_resp.json()
                        st.success(f"Simulations Complete using {data['model_type']} model.")
                        
                        st.subheader(f"Recommended Action: `{data['recommended_action']}`")
                        
                        sim_data = []
                        for sim in data["simulations"]:
                            # Generate mock distribution data for the violin plot based on returned mean/std
                            samples = np.random.normal(sim["p_churn_mean"], sim["p_churn_std"], 500)
                            samples = np.clip(samples, 0, 1)
                            for s in samples:
                                sim_data.append({"Scenario": sim["scenario"], "Simulated Churn Prob": s})
                            
                            st.write(f"**{sim['scenario']}**: Mean P(Churn)={sim['p_churn_mean']:.3f}, ROI={sim['expected_roi']:.2f}x")
                            
                        df_plot = pd.DataFrame(sim_data)
                        fig = px.violin(df_plot, y="Simulated Churn Prob", color="Scenario", box=True, points="all")
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.error(f"Simulation failed: {t_resp.text}")
        else:
            st.error("Failed to load customers.")
    except Exception as e:
        st.error(f"Error connecting to API: {e}")
