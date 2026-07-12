"""
components/tab_counterfactual.py
"""
import streamlit as st
import pandas as pd
import requests
import os

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

def render(tenant_id: int):
    st.header("Save Path Advisor (Counterfactuals)")
    st.markdown("Uses DiCE-ML to generate actionable paths to reduce a customer's churn risk. Instead of just showing *why* they are leaving (SHAP), this shows *what to do* to keep them.")
    
    headers = {"Authorization": f"Bearer {st.session_state.get('token', '')}"}
    
    try:
        resp = requests.get(f"{API_BASE}/api/v1/users/high-risk?threshold=0.60", headers=headers)
        if resp.status_code == 200:
            customers = resp.json()
            if not customers:
                st.info("No high-risk customers found.")
                return
            
            customer_opts = {c["user_id"]: f"{c['email']} (Score: {c['churn_probability']})" for c in customers}
            selected_cid = st.selectbox("Select Customer to Advise", options=list(customer_opts.keys()), format_func=lambda x: customer_opts[x])
            
            st.markdown("<br>", unsafe_allow_html=True)
            _, btn_col, _ = st.columns([1, 2, 1])
            with btn_col:
                generate_pressed = st.button("Generate Save Paths", use_container_width=True)
                
            if generate_pressed:
                with st.spinner("Running DiCE Genetic Search algorithm..."):
                    payload = {"customer_id": selected_cid, "max_counterfactuals": 5}
                    cf_resp = requests.post(f"{API_BASE}/api/v1/counterfactual/generate", json=payload, headers=headers)
                    
                    if cf_resp.status_code == 200:
                        data = cf_resp.json()
                        cfs = data.get("counterfactuals", [])
                        
                        if not cfs:
                            st.markdown("<div style='text-align: center; padding: 15px; border-radius: 8px; background-color: rgba(255, 204, 0, 0.1); border: 1px solid rgba(255, 204, 0, 0.3); color: #eab308; font-weight: bold;'>DiCE could not find feasible counterfactuals under the current constraints.</div>", unsafe_allow_html=True)
                        else:
                            st.success(f"Generated {len(cfs)} diverse counterfactual save paths.")
                            
                            for idx, cf in enumerate(cfs):
                                with st.expander(f"Path #{idx+1} — {cf['recommended_action']} (Est. Cost: ${cf['cost_usd']})", expanded=(idx==0)):
                                    st.markdown("### Action Plan Overview")
                                    st.markdown("<div class='centered-subheading'>This path outlines the optimal changes needed to retain this customer and where this intervention should be routed.</div>", unsafe_allow_html=True)
                                    
                                    col1, col2, col3 = st.columns(3)
                                    col1.metric(
                                        "Feasibility Score", 
                                        f"{cf['feasibility']:.2f}", 
                                        help="A score from 0.0 to 1.0 indicating how realistic it is to achieve these changes based on historical data."
                                    )
                                    col2.metric(
                                        "Resulting Churn Prob", 
                                        f"{cf['resulting_score']:.2f}", 
                                        f"{cf['resulting_score'] - 0.85:.2f}",
                                        help="The estimated probability that the customer will churn if we successfully apply these changes."
                                    )
                                    
                                    # Format the routing queue nicely
                                    route_name = str(cf['routed_to']).replace("_", " ").title()
                                    with col3:
                                        st.markdown("**Routed To**", help="The internal team or system queue that will handle this intervention.")
                                        st.markdown(f"🔀 `{route_name}`")
                                    
                                    st.divider()
                                    st.markdown("#### Required Feature Target Changes", help="These are the exact metric targets the recommended action aims to achieve for this customer.")
                                    
                                    # Format feature changes neatly instead of raw JSON
                                    changes = cf.get("features_to_change", {})
                                    if changes:
                                        for key, val in changes.items():
                                            clean_key = key.replace("_", " ").title()
                                            st.markdown(f"- **{clean_key}**: Change to `{float(val):.2f}`")
                                    else:
                                        st.info("No specific feature targets required for this action.")
                                        
                                    st.write("")
                                    if st.button("🚀 Execute this path", key=cf['cf_id']):
                                        st.success(f"Path executed! Task successfully routed to `{cf['routed_to']}`.")

                    else:
                        st.error(f"Generation failed: {cf_resp.text}")
        else:
            st.error("Failed to load customers.")
    except Exception as e:
        st.error(f"Error connecting to API: {e}")
