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

@st.fragment(run_every=2)
def poll_task_status(task_id: str, headers: dict):
    if not task_id:
        return
        
    response = requests.get(f"{API_BASE}/api/v1/twin/simulate/status/{task_id}", headers=headers)
    if response.status_code != 200:
        st.error("Error checking task status.")
        st.session_state.active_twin_task_id = None
        st.rerun()
        return
        
    data = response.json()
    state = data.get("status")
    
    if state == "PENDING":
        st.spinner("Running 1000 Monte Carlo simulations per scenario... (Async)")
    elif state == "SUCCESS":
        st.success("Analysis complete! Synchronizing dashboard...")
        st.session_state.active_twin_task_id = None
        st.session_state.twin_simulation_result = data.get("result")
        st.rerun()
    elif state in ["FAILURE", "REVOKED"]:
        st.error(f"Task tracking failed with state: {state}")
        st.session_state.active_twin_task_id = None
        st.rerun()

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
            
            _, btn_col, _ = st.columns([1, 2, 1])
            with btn_col:
                run_pressed = st.button("Run Monte Carlo Simulations", help="Spawns 500 parallel universe simulations branching from this customer's current state to probabilistically determine which sequence of future actions leads to the lowest churn risk.", use_container_width=True)
                
            if run_pressed:
                payload = {
                    "customer_id": selected_cid,
                    "scenarios": ["no_intervention", "discount_15", "product_fix"]
                }
                t_resp = requests.post(f"{API_BASE}/api/v1/twin/simulate", json=payload, headers=headers)
                
                if t_resp.status_code == 200:
                    data = t_resp.json()
                    if data.get("status") == "completed":
                        # Backend ran synchronously (no Redis/Celery)
                        st.session_state.active_twin_task_id = None
                        st.session_state.twin_simulation_result = data.get("result")
                        st.rerun()
                    else:
                        st.session_state.active_twin_task_id = data["task_id"]
                        st.session_state.twin_simulation_result = None
                else:
                    st.error(f"Simulation failed to start: {t_resp.text}")
                    
            if st.session_state.get("active_twin_task_id"):
                poll_task_status(st.session_state.active_twin_task_id, headers)
                
            if st.session_state.get("twin_simulation_result"):
                data = st.session_state.twin_simulation_result
                st.success(f"Simulations Complete using {data.get('model_type', 'LSTM')} model.")
                st.subheader(f"Recommended Action: `{data.get('recommended_action', 'Unknown')}`")
                
                simulations = data.get("simulations", [])
                sim_data = []
                
                st.markdown("<br>", unsafe_allow_html=True)
                cols = st.columns(len(simulations) if simulations else 1)
                
                for i, sim in enumerate(simulations):
                    samples = np.random.normal(sim["p_churn_mean"], sim["p_churn_std"], 500)
                    samples = np.clip(samples, 0, 1)
                    for s in samples:
                        sim_data.append({"Scenario": sim["scenario"], "Simulated Churn Prob": s})
                        
                    roi_color = "#4ade80" if sim['expected_roi'] > 1.5 else "#facc15" if sim['expected_roi'] > 0.8 else "#f87171"
                    cols[i].markdown(f"""
                    <div style='background-color: #111; border: 1px solid #333; padding: 20px; border-radius: 12px; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);'>
                        <p style='color: #A1A1AA; text-transform: uppercase; font-size: 0.85rem; letter-spacing: 1.5px; margin-bottom: 8px;'>{sim['scenario'].replace("_", " ")}</p>
                        <div style='color: #EDEDED; font-size: 2.2rem; font-weight: 700; margin-bottom: 4px;'>{sim['p_churn_mean']:.3f}</div>
                        <div style='color: {roi_color}; font-size: 0.95rem; font-weight: 600; text-transform: uppercase;'>{sim['expected_roi']:.2f}x ROI</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                df_plot = pd.DataFrame(sim_data)
                fig = px.violin(df_plot, y="Simulated Churn Prob", color="Scenario", box=True, points="all")
                st.plotly_chart(fig, use_container_width=True)
                
        else:
            st.error("Failed to load customers.")
    except Exception as e:
        st.error(f"Error connecting to API: {e}")
