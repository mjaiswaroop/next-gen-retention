"""
dashboard.py — Streamlit Unified Dashboard
==========================================
Implements Section 10: Unified Dashboard.
"""

import os
import streamlit as st
import pandas as pd
import requests

from components import tab_shap, tab_experiments, tab_causal, tab_twin, tab_emotion, tab_graph, tab_counterfactual, tab_agent, tab_forensics, tab_autoheal, tab_wargames, tab_ab_factory

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

def check_login():
    if "token" not in st.session_state:
        st.warning("Please log in first.")
        st.stop()
    return st.session_state.get("tenant_id", 1), st.session_state.get("role", "ANALYST"), {"Authorization": f"Bearer {st.session_state['token']}"}

def page_predict():
    tenant_id, role, headers = check_login()
    st.title("Predict")
    
    # ── Model Health Section ──
    st.header("Model Health & Retraining")
    try:
        resp = requests.get(f"{API_BASE}/api/v1/predict/metrics", headers=headers)
        if resp.status_code == 200:
            metrics = resp.json()
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("ROC-AUC", f"{metrics.get('roc_auc', 0):.4f}")
            col2.metric("PR-AUC", f"{metrics.get('pr_auc', 0):.4f}")
            col3.metric("F1 Score", f"{metrics.get('f1_score', 0):.4f}")
            col4.metric("Active Version", metrics.get('version', 'Unknown'))
        else:
            st.warning(f"Could not fetch model metrics. Server returned {resp.status_code}: {resp.text}")
    except Exception as e:
        st.error(f"Error fetching metrics: {e}")

    if role in ("SUPER_ADMIN", "TENANT_ADMIN"):
        st.markdown("<br><br>", unsafe_allow_html=True)
        col_btn, col_empty = st.columns([1, 2])
        with col_btn:
            if st.button("Trigger Live Retrain (Ensemble Model)", type="primary", help="Initiates a background job to retrain the XGBoost and LSTM models using the latest telemetry data from the last 24 hours. Use this when model drift is detected."):
                with st.spinner("Retraining model in background..."):
                    resp = requests.post(f"{API_BASE}/api/v1/predict/retrain", headers=headers)
                    if resp.status_code == 200:
                        st.success("Retraining triggered! Check logs for completion.")
                    else:
                        st.error(f"Failed to trigger retraining: {resp.text}")

    st.divider()

    # ── Batch Inference ──
    st.header("Batch Inference")
    st.markdown("Run the latest ensemble model against all current customers to refresh churn probability scores.")
    st.markdown("<br>", unsafe_allow_html=True)
    col_btn2, col_empty2 = st.columns([1, 2])
    with col_btn2:
        if st.button("Trigger Batch Inference Pipeline", help="Scores every customer in the database against the active model to update their churn probabilities. This runs nightly by default, but you can force it manually here."):
            with st.spinner("Running model..."):
                resp = requests.post(f"{API_BASE}/api/v1/predict/batch", headers=headers)
                if resp.status_code == 200:
                    st.success("Batch pipeline completed.")
                    st.json(resp.json())
                else:
                    st.error(f"Failed: {resp.text}")

    st.divider()
    
    # ── High Risk Customers ──
    st.subheader("High-Risk Customers (>75%)")
    threshold = st.slider("Threshold", 0.0, 1.0, 0.75, 0.05)
    try:
        resp = requests.get(f"{API_BASE}/api/v1/users/high-risk?threshold={threshold}", headers=headers)
        if resp.status_code == 200:
            df = pd.DataFrame(resp.json())
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("Could not fetch high-risk users.")
    except Exception as e:
        st.error(f"Error: {e}")

def page_explainability():
    tenant_id, role, headers = check_login()
    st.title("Explainability")
    try:
        resp = requests.get(f"{API_BASE}/api/v1/users/high-risk?threshold=0.75", headers=headers)
        df_risk = pd.DataFrame(resp.json()) if resp.status_code == 200 else pd.DataFrame()
        tab_shap.render(df_risk, tenant_id)
    except Exception as e:
        st.error(f"Explainability module error: {e}")

def page_causal_simulator():
    tenant_id, role, headers = check_login()
    st.title("Causal Simulator")
    tab_causal.render(tenant_id)

def page_twin_simulator():
    tenant_id, role, headers = check_login()
    st.title("Twin Simulator")
    tab_twin.render(tenant_id)

def page_emotion_timeline():
    tenant_id, role, headers = check_login()
    st.title("Emotion Timeline")
    tab_emotion.render(tenant_id)

def page_contagion_network():
    tenant_id, role, headers = check_login()
    st.title("Contagion Network")
    tab_graph.render(tenant_id)

def page_save_path_advisor():
    tenant_id, role, headers = check_login()
    st.title("Save Path Advisor")
    tab_counterfactual.render(tenant_id)

def page_live_negotiations():
    tenant_id, role, headers = check_login()
    st.title("Live Negotiations")
    tab_agent.render(tenant_id)

def page_automations():
    tenant_id, role, headers = check_login()
    st.title("Automations")
    if role in ("ANALYST", "PII_VIEWER"):
        st.warning("You do not have permission to manage campaigns.")
        return

    st.header("Campaign & Experiment Management")
    tab_experiments.render(tenant_id)
    
    st.divider()
    st.subheader("Pending Campaign Approvals")
    try:
        resp = requests.get(f"{API_BASE}/api/v1/campaigns/pending", headers=headers)
        if resp.status_code == 200:
            pending = resp.json()
            if not pending:
                st.info("No campaigns pending approval.")
            for c in pending:
                with st.expander(f"Campaign to {c['customer_id']} (Score: {c['churn_score']})"):
                    st.markdown(f"**Subject:** {c['generated_email_subject']}")
                    st.text_area("Body", c['generated_email_body'], height=150, disabled=True)
                    col1, col2 = st.columns(2)
                    if col1.button("Approve & Send", key=f"approve_{c['queue_id']}"):
                        requests.post(f"{API_BASE}/api/v1/campaigns/{c['queue_id']}/approve", headers=headers)
                        st.rerun()
                    if col2.button("Reject", key=f"reject_{c['queue_id']}"):
                        requests.post(f"{API_BASE}/api/v1/campaigns/{c['queue_id']}/reject", headers=headers)
                        st.rerun()
    except Exception as e:
        st.error(f"Error fetching queue: {e}")

def page_forensics():
    tenant_id, role, headers = check_login()
    st.title("Churn Forensics")
    tab_forensics.render(tenant_id)

def page_bi_reports():
    tenant_id, role, headers = check_login()
    st.title("BI Reports")
    st.header("Executive Business Intelligence")
    try:
        resp = requests.get(f"{API_BASE}/api/v1/bi/digest", headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            roi = data.get("campaign_roi", {})
            revenue = data.get("revenue_at_risk", {})

            col1, col2, col3 = st.columns(3)
            col1.metric("Current Churn Rate", f"{data.get('churn_rate_this_week', 0)}%", f"{data.get('churn_rate_delta', 0)}%")
            col2.metric("Revenue at Risk", f"${revenue.get('total_at_risk', 0):,.2f}")
            col3.metric("Campaign ROI (est)", f"{roi.get('estimated_roi_pct', 0)}%")
            
            if data.get("trend_weeks"):
                st.subheader("4-Week Churn Trend")
                st.line_chart(pd.DataFrame(data["trend_weeks"]).set_index("week_start")["churn_rate_pct"])
        else:
            st.error("Could not load BI digest.")
    except Exception as e:
        st.error(f"BI Error: {e}")

def page_rbac():
    tenant_id, role, headers = check_login()
    st.title("RBAC & API Keys")
    st.header("Access Management")
    st.subheader("Generate API Key")
    with st.form("api_key_form"):
        key_name = st.text_input("Key Description")
        scopes = st.multiselect("Scopes", ["data_ingest", "analytics_read", "campaign_trigger"])
        if st.form_submit_button("Generate Key"):
            resp = requests.post(f"{API_BASE}/api/v1/auth/keys", json={"name": key_name, "scopes": scopes}, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                st.success("Key generated successfully!")
                st.warning(f"**SAVE THIS KEY NOW.** It will not be shown again: `{data['api_key']}`")
            else:
                st.error("Failed to generate key.")

def page_compliance():
    tenant_id, role, headers = check_login()
    st.title("Compliance")
    st.header("GDPR / CCPA Compliance")
    st.subheader("Execute Right-to-Erasure")
    st.warning("⚠️ This action is irreversible and cascading. It deletes the user from all operational and analytical stores.")
    customer_to_delete = st.text_input("Enter Customer ID to Erase")
    if st.button("Delete Customer"):
        if customer_to_delete:
            resp = requests.delete(f"{API_BASE}/api/v1/compliance/erasure/{customer_to_delete}", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                st.success(f"Customer erased successfully. Certificate: {data['erasure_id']}")
                st.json(data["tables_cleared"])
            else:
                st.error(f"Erasure failed: {resp.text}")
        else:
            st.error("Customer ID required.")

def page_login():
    st.markdown("<br><br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col2:
        st.markdown("<h1 style='text-align: center;'>Anchor</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #A1A1AA; margin-bottom: 30px;'>Next-Gen Retention Platform</p>", unsafe_allow_html=True)
        
        tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])
        
        with tab_login:
            with st.form("login_form", border=False):
                email = st.text_input("Email", placeholder="admin@example.com")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                tenant_id = st.number_input("Tenant ID", min_value=1, value=1)
                st.markdown("<br>", unsafe_allow_html=True)
                submit = st.form_submit_button("Log In", use_container_width=True)
    
            if submit:
                try:
                    resp = requests.post(
                        f"{API_BASE}/api/v1/auth/login",
                        data={"username": email, "password": password, "client_id": str(tenant_id)},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        st.session_state["token"] = data["access_token"]
                        st.session_state["role"] = data["role"]
                        st.session_state["tenant_id"] = tenant_id
                        st.success("Logged in successfully!")
                        st.rerun()
                    else:
                        st.error("Invalid credentials.")
                except Exception as e:
                    st.error(f"Connection failed: {e}")

        with tab_signup:
            with st.form("signup_form", border=False):
                company = st.text_input("Company Name", placeholder="Acme Corp")
                signup_email = st.text_input("Work Email", placeholder="founder@acme.com")
                signup_password = st.text_input("Password", type="password", placeholder="••••••••")
                st.markdown("<br>", unsafe_allow_html=True)
                signup_submit = st.form_submit_button("Create Account", use_container_width=True)

            if signup_submit:
                if not company or not signup_email or not signup_password:
                    st.error("Please fill all fields.")
                else:
                    try:
                        resp = requests.post(
                            f"{API_BASE}/api/v1/auth/signup",
                            data={"email": signup_email, "password": signup_password, "company_name": company},
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            st.success(f"Account created! Your Tenant ID is **{data['tenant_id']}**. Please log in from the Log In tab.")
                        else:
                            st.error(f"Failed to sign up: {resp.json().get('detail', 'Unknown error')}")
                    except Exception as e:
                        st.error(f"Connection failed: {e}")

def main():
    st.set_page_config(page_title="Anchor Dashboard", layout="wide", page_icon="📈")
    
    # Inject Custom CSS for Premium Minimalist Dark Theme
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto+Condensed:wght@400;500;600;700&display=swap');
        
        /* Global Background & Font */
        .stApp {
            background-color: #0A0A0A !important;
            font-family: 'Roboto Condensed', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif !important;
            color: #EDEDED !important;
            line-height: 1.6;
        }

        /* Uppercase styling */
        .stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp span, .stApp label, .stApp button, .stApp div, .stMarkdown {
            text-transform: uppercase !important;
        }
        
        /* Protect Inputs and Code */
        input, textarea, code, pre, .stDataFrame {
            text-transform: none !important;
        }

        /* Smooth Entrance Animations */
        @keyframes smoothFadeIn {
            0% { opacity: 0; transform: translateY(20px); filter: blur(2px); }
            100% { opacity: 1; transform: translateY(0); filter: blur(0); }
        }
        
        .block-container > div {
            animation: smoothFadeIn 0.8s cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        .block-container > div:nth-child(1) { animation-delay: 0.0s; }
        .block-container > div:nth-child(2) { animation-delay: 0.1s; }
        .block-container > div:nth-child(3) { animation-delay: 0.2s; }
        .block-container > div:nth-child(4) { animation-delay: 0.3s; }


        /* Headings - Editorial Serif for Headers */
        h1, h2, h3 {
            font-family: 'Roboto Condensed', sans-serif !important;
            font-weight: 600 !important;
            color: #EDEDED !important;
            letter-spacing: -0.02em !important;
            margin-bottom: 24px;
        }
        
        h1 {
            font-size: 2.5rem !important;
            padding-bottom: 8px;
            border-bottom: 1px solid #333333;
        }

        /* Metrics & Cards - Minimalist Style (No Rectangles) */
        [data-testid="stMetric"] {
            background-color: transparent !important;
            border: none !important;
            padding: 10px 0px !important;
            box-shadow: none !important;
        }
        
        .stDataFrame {
            border: none !important;
            box-shadow: none !important;
        }

        /* Metric Values */
        [data-testid="stMetricValue"] {
            color: #EDEDED !important;
            font-family: 'Roboto Condensed', sans-serif !important;
            font-weight: 600 !important;
            font-size: 2.25rem !important;
            letter-spacing: -0.02em !important;
        }
        [data-testid="stMetricLabel"] {
            color: #A1A1AA !important;
            font-weight: 500 !important;
            font-size: 0.85rem !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        [data-testid="stMetricDelta"] {
            color: #34D399 !important; /* Muted Green for positive */
        }

        /* Primary Call-To-Action Buttons */
        .stButton>button {
            background-color: #EDEDED !important;
            border: none !important;
            border-radius: 6px !important;
            color: #0A0A0A !important;
            font-family: 'Roboto Condensed', sans-serif !important;
            font-weight: 500 !important;
            font-size: 0.95rem !important;
            padding: 0.6rem 1.2rem !important;
            transition: transform 0.1s ease, background-color 0.1s ease !important;
            box-shadow: none !important;
        }
        .stButton>button:hover {
            background-color: #FFFFFF !important;
            transform: scale(0.98) !important;
        }
        
        /* Secondary / Secondary-like Elements */
        .stSlider label {
            color: #A1A1AA !important;
            font-weight: 500 !important;
        }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: #050505 !important;
            border-right: 1px solid #333333 !important;
        }
        [data-testid="stSidebar"] .stMarkdown p {
            color: #A1A1AA !important;
            font-size: 0.9rem !important;
        }

        /* Dividers */
        hr {
            border-top: 1px solid #333333 !important;
            margin: 2.5rem 0 !important;
        }

        /* Fix Password Eye Icon Overlap */
        div[data-testid="InputInstructions"] {
            display: none !important;
        }
        </style>
    """, unsafe_allow_html=True)

    if "token" not in st.session_state:
        pg = st.navigation([st.Page(page_login, title="Login", icon="🔐", default=True)])
        pg.run()
    else:
        role = st.session_state.get("role", "ANALYST")
        tenant_id = st.session_state.get("tenant_id", 1)

        # Hide the sidebar toggle button completely
        st.markdown("""
            <style>
            [data-testid="collapsedControl"] { display: none !important; }
            [data-testid="stSidebar"] { display: none !important; }
            </style>
        """, unsafe_allow_html=True)

        from streamlit_option_menu import option_menu
        from components.tab_data_ingestion import render_data_ingestion
        
        # Determine available pages based on role
        all_pages = ["Predict", "Explainability", "Forensics", "BI Reports", "Automations", "Simulators", "Auto-Heal", "Admin", "Data Ingestion"]
        icons = ["graph-up", "brain", "search", "bar-chart", "robot", "cpu", "wrench", "shield-lock", "database"]
        if role not in ("SUPER_ADMIN", "TENANT_ADMIN"):
            all_pages.remove("Admin")
            icons.remove("shield-lock")
            all_pages.remove("Data Ingestion")
            icons.remove("database")

        # Top Horizontal Navigation Bar
        selected_main = option_menu(
            menu_title=None,
            options=all_pages,
            icons=icons,
            default_index=0,
            orientation="horizontal",
            styles={
                "container": {"padding": "0!important", "background-color": "#0A0A0A", "border-radius": "0", "border-bottom": "1px solid #333333"},
                "icon": {"color": "#A1A1AA", "font-size": "14px"},
                "nav-link": {"font-size": "14px", "text-align": "center", "margin": "0px", "--hover-color": "#111111", "color": "#A1A1AA"},
                "nav-link-selected": {"background-color": "transparent", "color": "#EDEDED", "border-bottom": "2px solid #EDEDED", "border-radius": "0px"}
            }
        )
        
        # Sub-navigation for Simulators or Admin
        if selected_main == "Simulators":
            selected_sub = option_menu(
                menu_title=None,
                options=["Causal", "Twin", "Emotion", "Contagion", "Save Path", "Live", "War Games"],
                default_index=0,
                orientation="horizontal",
                styles={
                    "container": {"padding": "0!important", "background-color": "transparent", "border-radius": "0"},
                    "nav-link": {"font-size": "13px", "text-align": "center", "margin": "0px", "--hover-color": "#111111", "color": "#A1A1AA"},
                    "nav-link-selected": {"background-color": "transparent", "color": "#EDEDED", "border-bottom": "2px solid #EDEDED", "border-radius": "0px"}
                }
            )
            if selected_sub == "Causal": page_causal_simulator()
            elif selected_sub == "Twin": page_twin_simulator()
            elif selected_sub == "Emotion": page_emotion_timeline()
            elif selected_sub == "Contagion": page_contagion_network()
            elif selected_sub == "Save Path": page_save_path_advisor()
            elif selected_sub == "Live": page_live_negotiations()
            elif selected_sub == "War Games": tab_wargames.render(tenant_id)

        elif selected_main == "Admin":
            selected_sub = option_menu(
                menu_title=None,
                options=["RBAC & API Keys", "Compliance"],
                default_index=0,
                orientation="horizontal",
                styles={
                    "container": {"padding": "0!important", "background-color": "transparent", "border-radius": "0"},
                    "nav-link": {"font-size": "13px", "text-align": "center", "margin": "0px", "--hover-color": "#111111", "color": "#A1A1AA"},
                    "nav-link-selected": {"background-color": "transparent", "color": "#EDEDED", "border-bottom": "2px solid #EDEDED", "border-radius": "0px"}
                }
            )
            if selected_sub == "RBAC & API Keys": page_rbac()
            elif selected_sub == "Compliance": page_compliance()

        # Render Main Pages directly
        elif selected_main == "Predict": page_predict()
        elif selected_main == "Explainability": page_explainability()
        elif selected_main == "Forensics": page_forensics()
        elif selected_main == "BI Reports": page_bi_reports()
        elif selected_main == "Automations": 
            selected_sub = option_menu(
                menu_title=None,
                options=["Workflows", "A/B Factory"],
                default_index=0,
                orientation="horizontal",
                styles={
                    "container": {"padding": "0!important", "background-color": "transparent", "border-radius": "0"},
                    "nav-link": {"font-size": "13px", "text-align": "center", "margin": "0px", "--hover-color": "#111111", "color": "#A1A1AA"},
                    "nav-link-selected": {"background-color": "transparent", "color": "#EDEDED", "border-bottom": "2px solid #EDEDED", "border-radius": "0px"}
                }
            )
            if selected_sub == "Workflows": page_automations()
            elif selected_sub == "A/B Factory": tab_ab_factory.render(tenant_id)
        elif selected_main == "Auto-Heal": tab_autoheal.render(tenant_id)
        elif selected_main == "Data Ingestion": render_data_ingestion()

        # Top Right corner status (Tenant ID and Logout)
        col1, col2, col3 = st.columns([8, 1, 1])
        with col2:
            st.markdown(f"<div style='text-align: right; color: #787774; font-size: 12px; margin-top: 10px;'>Tenant: {tenant_id}</div>", unsafe_allow_html=True)
        with col3:
            if st.button("Log Out"):
                st.session_state.pop("token", None)
                st.session_state.pop("role", None)
                st.session_state.pop("tenant_id", None)
                st.rerun()

if __name__ == "__main__":
    main()
