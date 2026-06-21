"""
components/tab_agent.py
"""
import streamlit as st
import pandas as pd
import requests
import os
from datetime import datetime

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

def render(tenant_id: int):
    st.header("Live Negotiations (Autonomous Agent)")
    st.markdown("Monitor real-time generative AI negotiation sessions. The agent attempts to retain high-risk users by negotiating personalized offers based on corporate policy.")
    
    headers = {"Authorization": f"Bearer {st.session_state.get('token', '')}"}
    
    # 1. Initialize a new session
    st.subheader("Start New Negotiation Session")
    
    mock_customers = ["5482-NUPNA", "cust_123", "8472-ABC", "1192-XYZ", "9941-RPO", "7712-QWE"]
    
    col1, col2 = st.columns([1, 2])
    with col1:
        test_cust_id = st.selectbox("Customer ID", options=mock_customers)
    with col2:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        start_btn = st.button("Start Agent Session")
        
    if start_btn:
        resp = requests.post(f"{API_BASE}/api/v1/agent/start?customer_id={test_cust_id}", headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            st.success(f"Session started! WebSocket URL: `{data['ws_url']}`")
            st.session_state["active_session_id"] = data["session_id"]
        else:
            st.error("Failed to start session.")
            
    st.divider()
    
    # 2. Simulate Chat (REST fallback for UI if WS is not natively supported by basic Streamlit)
    if "active_session_id" in st.session_state:
        st.subheader(f"Simulating Chat for Session: {st.session_state['active_session_id']}")
        
        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = []
            
        for msg in st.session_state["chat_history"]:
            with st.chat_message("user" if msg["role"] == "user" else "assistant"):
                st.write(msg["content"])
                
        # We simulate the WS connection via direct REST calls to the mock logic for Streamlit simplicity
        # (Streamlit doesn't natively host persistent WebSockets well without custom components)
        user_input = st.chat_input("Type customer message here...")
        if user_input:
            st.session_state["chat_history"].append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.write(user_input)
                
            from services.agent_service import process_message
            res = process_message(st.session_state["active_session_id"], user_input)
            
            if "error" not in res:
                st.session_state["chat_history"].append({"role": "agent", "content": res["reply"]})
                with st.chat_message("assistant"):
                    st.write(res["reply"])
                
                if res["status"] in ("success", "escalated"):
                    st.info(f"Session ended with status: **{res['status'].upper()}**")
                    del st.session_state["active_session_id"]
                    del st.session_state["chat_history"]

    st.divider()
    
    # 3. View Analytics
    st.subheader("Active & Recent Sessions")
    try:
        resp = requests.get(f"{API_BASE}/api/v1/agent/sessions", headers=headers)
        if resp.status_code == 200:
            sessions = resp.json().get("sessions", [])
            if not sessions:
                st.info("No recent sessions.")
            else:
                df = pd.DataFrame(sessions)
                st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"Failed to fetch sessions: {e}")

    st.divider()

    # 4. Agent Governance & Approvals
    st.subheader("Agent Governance & Approvals")
    st.markdown("Review actions proposed by the autonomous agent that require human approval.")
    
    try:
        pending_resp = requests.get(f"{API_BASE}/api/v1/agent/actions/pending", headers=headers)
        if pending_resp.status_code == 200:
            pending_actions = pending_resp.json().get("actions", [])
            if not pending_actions:
                st.success("No pending actions require your approval.")
            else:
                for action in pending_actions:
                    with st.expander(f"Pending: {action['action_type']} (Requested: {action['requested_at'][:16]})"):
                        st.markdown(f"**Rationale:** {action['rationale']}")
                        st.json(action.get("action_payload", {}))
                        
                        col1, col2 = st.columns(2)
                        if col1.button("Approve", key=f"approve_{action['id']}"):
                            res = requests.post(
                                f"{API_BASE}/api/v1/agent/actions/{action['id']}/resolve",
                                json={"approved": True},
                                headers=headers
                            )
                            if res.status_code == 200:
                                st.success("Approved!")
                                st.rerun()
                        if col2.button("Reject", key=f"reject_{action['id']}"):
                            res = requests.post(
                                f"{API_BASE}/api/v1/agent/actions/{action['id']}/resolve",
                                json={"approved": False},
                                headers=headers
                            )
                            if res.status_code == 200:
                                st.warning("Rejected!")
                                st.rerun()
                                
        st.divider()
        st.subheader("Agent Activity Log")
        all_actions_resp = requests.get(f"{API_BASE}/api/v1/agent/actions", headers=headers)
        if all_actions_resp.status_code == 200:
            all_actions = all_actions_resp.json().get("actions", [])
            if all_actions:
                df_actions = pd.DataFrame(all_actions)
                st.dataframe(
                    df_actions[["id", "action_type", "classification", "status", "rationale", "requested_at", "resolved_by"]],
                    use_container_width=True
                )
            else:
                st.info("No activity logged yet.")
    except Exception as e:
        st.error(f"Failed to fetch governance data: {e}")
