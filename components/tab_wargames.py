import streamlit as st
import requests
import os

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

def render(tenant_id: int):
    st.header("War Games: Multi-Agent Campaign Simulation")
    st.markdown("<div class='centered-subheading'>Test your retention campaigns against AI personas built from real customer telemetry before you hit send.</div>", unsafe_allow_html=True)
    
    headers = {"Authorization": f"Bearer {st.session_state.get('token', '')}"}
    
    col1, col2 = st.columns([1, 2])
    with col1:
        segment = st.text_input("Target Segment (Optional)", placeholder="e.g. Price_Sensitive")
        sample_size = st.slider("Number of AI Agents to Spin Up", 1, 20, 5)
        
    with col2:
        email_draft = st.text_area("Email Draft", height=200, placeholder="Hi there,\n\nWe noticed you haven't been active. Here is a 20% discount to come back!")
        
    if st.button("Run Simulation", type="primary", help="Spawns AI replicas (agents) of your selected customer segment and tests your draft email on them to predict Open Rate, Click Rate, and their generated emotional replies."):
        if not email_draft:
            st.error("Please provide an email draft to test.")
            return
            
        with st.spinner(f"Spinning up {sample_size} AI customer personas..."):
            resp = requests.post(
                f"{API_BASE}/api/v1/wargames/simulate",
                json={"segment": segment if segment else None, "email_draft": email_draft, "sample_size": sample_size},
                headers=headers
            )
            
            if resp.status_code == 200:
                data = resp.json()
                summary = data["summary"]
                
                st.divider()
                st.subheader("Simulation Results")
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Open Rate", f"{summary['open_rate']*100:.1f}%")
                m2.metric("Click Rate", f"{summary['click_rate']*100:.1f}%")
                m3.metric("Churn Rate", f"{summary['churn_rate']*100:.1f}%")
                m4.metric("Avg Anger (1-10)", f"{summary['avg_anger']:.1f}")
                
                st.subheader("Individual Agent Reactions")
                for agent in data["individual_reactions"]:
                    reaction = agent["reaction"]
                    with st.expander(f"Agent {agent['user_id']} | Anger: {reaction['anger_level']} | Churned: {reaction['churned']}"):
                        st.json(agent["telemetry"])
                        if reaction["reply"]:
                            st.info(f"**Simulated Reply:** {reaction['reply']}")
            else:
                st.error(f"Simulation failed: {resp.text}")
