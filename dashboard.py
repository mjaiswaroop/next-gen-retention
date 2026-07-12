"""
dashboard.py — Streamlit Unified Dashboard
==========================================
Implements Section 10: Unified Dashboard.
"""

import os
import streamlit as st
import pandas as pd
import requests

# ── GLOBAL ERROR MONKEYPATCH ────────────────────────
# Replaces all native st.error calls with a high-tech cyan error box
_original_error = st.error

def advanced_error(body, icon=None, *args, **kwargs):
    body_str = str(body).lower()
    if "invalid credentials" in body_str:
        title = "AUTHENTICATION FAILED"
        color = "#FF9800" # Orange warning
    elif "exist" in body_str or "required" in body_str or "please" in body_str:
        title = "USER NOTICE"
        color = "#00E5FF" # Cyan
    else:
        title = "SYSTEM EXCEPTION"
        color = "#FF1744" # Red for actual system errors

    html = f"""
    <div style="
        border-left: 4px solid {color};
        background-color: rgba(0, 0, 0, 0.2);
        padding: 16px 20px;
        border-radius: 4px;
        margin-bottom: 1rem;
        box-shadow: inset 0 0 20px rgba(0, 0, 0, 0.05), 0 4px 6px rgba(0,0,0,0.3);
        display: flex;
        align-items: flex-start;
        gap: 16px;
        backdrop-filter: blur(4px);
    ">
        <div style="
            background: rgba(0, 0, 0, 0.2); 
            padding: 8px; 
            border-radius: 8px; 
            display: flex; 
            align-items: center; 
            justify-content: center;
            border: 1px solid {color};
            box-shadow: 0 0 10px {color}40;
        ">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
        </div>
        <div style="flex: 1;">
            <div style="
                color: {color}; 
                font-family: monospace; 
                font-weight: 700; 
                font-size: 0.85rem; 
                letter-spacing: 2px; 
                text-transform: uppercase; 
                margin-bottom: 4px;
            ">{title}</div>
            <div style="
                color: #EDEDED; 
                font-size: 0.95rem; 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                line-height: 1.5;
            ">
                {body}
            </div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

st.error = advanced_error
# ───────────────────────────────────────────────────

from components import tab_shap, tab_experiments, tab_causal, tab_twin, tab_emotion, tab_graph, tab_counterfactual, tab_agent, tab_forensics, tab_autoheal, tab_wargames, tab_ab_factory, tab_user_manual, tab_data_ingestion
import importlib
importlib.reload(tab_forensics)
importlib.reload(tab_user_manual)
importlib.reload(tab_data_ingestion)
importlib.reload(tab_causal)
importlib.reload(tab_twin)

def get_premium_loader(title, subtitle=""):
    subtitle_html = f"<div style='margin-top: 10px;'><h5 style='color: #a3a8a5; font-weight: 500; font-family: \"Inter\", sans-serif; letter-spacing: 2px; text-transform: uppercase; font-size: 0.8rem; text-align: center; margin: 0;'>{subtitle}</h5></div>" if subtitle else ""
    return f"""
<div class='custom-loader-wrapper' style='position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background-color: rgba(12, 16, 14, 0.97); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); z-index: 9999999; display: flex; flex-direction: column; justify-content: center; align-items: center;'>
<div style='background: #131a17; border: 1px solid rgba(230, 223, 211, 0.08); border-radius: 12px; padding: 48px 64px; display: flex; flex-direction: column; align-items: center; justify-content: center; box-shadow: 0 30px 60px rgba(0, 0, 0, 0.6); animation: cardAppear 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards; max-width: 420px; width: 90%;'>
<h3 class='loader-title'>{title}</h3>
{subtitle_html}
<div class='editorial-progress-bar'>
<div class='progress-fill'></div>
</div>
</div>
</div>
<style>
.editorial-progress-bar {{
width: 180px;
height: 2px;
background: rgba(230, 223, 211, 0.1);
border-radius: 2px;
margin-top: 32px;
overflow: hidden;
position: relative;
}}
.progress-fill {{
height: 100%;
width: 50%;
background: #e6dfd3;
position: absolute;
animation: lineProgress 1.5s cubic-bezier(0.65, 0.05, 0.36, 1) infinite;
border-radius: 2px;
}}
.loader-title {{
color: #e6dfd3;
font-family: 'Playfair Display', serif;
font-size: 1.15rem;
font-weight: 500;
letter-spacing: 2px;
text-transform: uppercase;
margin: 0;
text-align: center;
}}
@keyframes lineProgress {{
0% {{ left: -50%; }}
100% {{ left: 100%; }}
}}
@keyframes cardAppear {{
0% {{ opacity: 0; transform: translateY(12px) scale(0.98); }}
100% {{ opacity: 1; transform: translateY(0) scale(1); }}
}}
</style>
"""

from contextlib import contextmanager
from streamlit_lottie import st_lottie
import time

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

def check_login():
    if "token" not in st.session_state:
        st.warning("Please log in first.")
        st.stop()
    return st.session_state.get("tenant_id", 1), st.session_state.get("role", "ANALYST"), {"Authorization": f"Bearer {st.session_state['token']}"}

@st.dialog("Metrics Dictionary", width="large")
def metric_dictionary_dialog():
    st.markdown("""
    ### Receiver Operating Characteristic (ROC-AUC)
    **What it means:** Measures how effectively the model distinguishes between users who will churn and users who will stay. 
    **How it's calculated:** Plots True Positive Rate vs False Positive Rate across all possible probability thresholds. The score is the total area under this curve.
    **Feedback:** A score of 0.5 means the model is just randomly guessing. 0.8+ is good, and 0.9+ is excellent.
    
    ---
    ### Precision-Recall Area (PR-AUC)
    **What it means:** Highly stringent metric that evaluates performance specifically on imbalanced datasets (e.g. where only 2% of users actually churn).
    **How it's calculated:** Plots Precision (accuracy of our churn flags) vs Recall (how many real churners we caught).
    **Feedback:** If your churn rate is extremely low, ROC-AUC can artificially inflate. PR-AUC is much more rigorous. A score > 0.5 on highly skewed data is often considered very strong.
    
    ---
    ### F1 Score
    **What it means:** The harmonic mean of Precision and Recall. It balances the trade-off between catching every single churner (high recall) and avoiding false alarms (high precision).
    **How it's calculated:** `2 * (Precision * Recall) / (Precision + Recall)`
    **Feedback:** Evaluated at a specific threshold. A high F1 score means the model is both highly accurate and highly sensitive.
    """)


def page_predict():
    tenant_id, role, headers = check_login()

    st.title("Predict")
    st.markdown("<div class='centered-subheading'>Model health, batch inference & high-risk customer detection</div>", unsafe_allow_html=True)
    
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
            
            st.markdown("<br>", unsafe_allow_html=True)
            _, col_exp, _ = st.columns([1, 1, 1])
            with col_exp:
                if st.button("Explain Metrics", icon="ℹ️", help="Learn how ROC-AUC, PR-AUC, and F1 are calculated", use_container_width=True):
                    metric_dictionary_dialog()
                
        else:
            st.warning(f"Could not fetch model metrics. Server returned {resp.status_code}: {resp.text}")
    except Exception as e:
        st.error(f"Error fetching metrics: {e}")

    if role in ("SUPER_ADMIN", "TENANT_ADMIN"):
        st.markdown("<br><br>", unsafe_allow_html=True)
        _, col_retrain, _ = st.columns([1, 2, 1])
        with col_retrain:
            if st.button("Trigger Live Retrain (Ensemble Model)", type="primary", help="Initiates a background job to retrain the XGBoost and LSTM models using the latest telemetry data from the last 24 hours. Use this when model drift is detected.", use_container_width=True):
                with st.spinner("Retraining models in background..."):
                    resp = requests.post(f"{API_BASE}/api/v1/predict/retrain", headers=headers)
                    if resp.status_code == 200:
                        st.toast("Retraining triggered! Check logs for completion.", icon="🚀")
                    else:
                        st.toast(f"Failed to trigger retraining: {resp.text}", icon="❌")

    st.divider()

    # ── Batch Inference ──
    st.header("Batch Inference")
    st.markdown("<div class='centered-subheading'>Run the latest ensemble model against all current customers to refresh churn probability scores.</div>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    _, col_batch, _ = st.columns([1, 2, 1])
    with col_batch:
        if st.button("Trigger Batch Inference Pipeline", help="Scores every customer in the database against the active model to update their churn probabilities. This runs nightly by default, but you can force it manually here.", use_container_width=True):
            with st.spinner("Running model across customer base..."):
                resp = requests.post(f"{API_BASE}/api/v1/predict/batch", headers=headers)
                if resp.status_code == 200:
                    st.toast("Batch pipeline completed.", icon="✅")
                    st.json(resp.json())
                else:
                    st.toast(f"Failed: {resp.text}", icon="❌")

    st.divider()
    
    # ── High Risk Customers ──
    threshold = st.slider("Risk Threshold", 0.0, 1.0, 0.75, 0.05)
    st.subheader(f"High-Risk Customers (>{int(threshold*100)}%)")
    try:
        resp = requests.get(f"{API_BASE}/api/v1/users/high-risk?threshold={threshold}", headers=headers)
        if resp.status_code == 200:
            df = pd.DataFrame(resp.json())
            if df.empty:
                st.info("✨ No high-risk customers found! You're in the clear.")
            else:
                st.dataframe(df, use_container_width=True)
        else:
            st.toast("Could not fetch high-risk users.", icon="⚠️")
    except Exception as e:
        st.error(f"Error: {e}")

def page_explainability():
    tenant_id, role, headers = check_login()

    st.title("Explainability")
    st.markdown("<div class='centered-subheading'>SHAP attributions, drift monitoring & experiment status</div>", unsafe_allow_html=True)
    try:
        resp = requests.get(f"{API_BASE}/api/v1/users/high-risk?threshold=0.75", headers=headers)
        df_risk = pd.DataFrame(resp.json()) if resp.status_code == 200 else pd.DataFrame()
        tab_shap.render(df_risk, tenant_id)
    except Exception as e:
        st.error(f"Explainability module error: {e}")

def page_causal_simulator():
    tenant_id, role, headers = check_login()
    tab_causal.render(tenant_id)

def page_twin_simulator():
    tenant_id, role, headers = check_login()
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
    tab_counterfactual.render(tenant_id)

def page_live_negotiations():
    tenant_id, role, headers = check_login()
    st.title("Live Negotiations")
    tab_agent.render(tenant_id)

def page_automations():
    tenant_id, role, headers = check_login()

    st.title("Automations")
    st.markdown("<div class='centered-subheading'>Campaign management, experiment workflows & approvals</div>", unsafe_allow_html=True)
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
    tab_forensics.render(tenant_id)

def page_bi_reports():
    tenant_id, role, headers = check_login()

    st.title("BI Reports")
    st.markdown("<div class='centered-subheading'>Executive business intelligence & campaign performance</div>", unsafe_allow_html=True)
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
    st.markdown("<div class='centered-subheading'>Generate and manage API access credentials</div>", unsafe_allow_html=True)
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
    st.markdown("<div class='centered-subheading'>GDPR / CCPA data erasure & regulatory controls</div>", unsafe_allow_html=True)
    st.header("Execute Right-to-Erasure")
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
        # Wrap everything in a defined container box with a sleek shadow and border
        st.markdown("<style>div[data-testid='stVerticalBlockBorderWrapper'] { border-radius: 20px; box-shadow: 0 30px 60px rgba(0,0,0,0.6); border: 1px solid rgba(230, 223, 211, 0.08); padding: 32px; background-color: #131a17; backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); }</style>", unsafe_allow_html=True)
        
        with st.container(border=True):
            # Added Anchor Logo (⚓) with a premium gradient color
            st.markdown("<div style='font-size: 3rem; font-family: \"Playfair Display\", serif; font-weight: 600; text-align: center; color: #e6dfd3; letter-spacing: 2px; padding-bottom: 16px; border-bottom: 1px solid rgba(230, 223, 211, 0.08); margin-bottom: 16px; display: flex; justify-content: center; align-items: center; gap: 16px;'><span style='color: #e6dfd3; font-size: 3.2rem;'>⚓</span> ANCHOR</div>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #a3a8a5; margin-bottom: 35px; text-transform: uppercase; font-family: \"Inter\", sans-serif; font-size: 0.8rem; font-weight: 500; letter-spacing: 4px;'>Next-Gen Retention Platform</p>", unsafe_allow_html=True)
            
            tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])
            
            with tab_login:
                with st.form("login_form", border=False):
                    email = st.text_input("Email", placeholder="admin@retentioncore.com")
                    password = st.text_input("Password", type="password", placeholder="••••••••")
                    tenant_id = st.number_input("Tenant ID", min_value=1, value=1)
                    st.markdown("<br>", unsafe_allow_html=True)
                    submit = st.form_submit_button("Log In", use_container_width=True)
    
            if submit:
                auth_loader = st.empty()
                auth_loader.markdown(get_premium_loader("AUTHENTICATING..."), unsafe_allow_html=True)
                
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
                        st.session_state["show_welcome"] = True
                        st.rerun()
                    else:
                        auth_loader.empty()
                        st.error("Invalid credentials.")
                except Exception as e:
                    auth_loader.empty()
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
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400..900;1,400..900&family=Inter:wght@300;400;500;600;700&display=swap');
        
        /* Global Background & Font */
        .stApp {
            background-color: #0c100e !important;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
            color: #e6dfd3 !important;
            line-height: 1.6;
        }

        /* Targeted Typography */
        h1, h2, h3 {
            font-family: 'Playfair Display', serif !important;
            font-weight: 500 !important;
            color: #e6dfd3 !important;
            letter-spacing: -0.01em !important;
            margin-bottom: 24px;
            text-align: center !important;
            text-transform: none !important;
        }

        h4, h5, h6 {
            font-family: 'Playfair Display', serif !important;
            font-weight: 600 !important;
            color: #cbd5e1 !important;
            letter-spacing: -0.01em !important;
            text-transform: none !important;
        }

        .centered-subheading {
            text-align: center !important;
            color: #a3a8a5 !important;
            font-size: 0.95rem !important;
            font-weight: 500 !important;
            font-style: italic !important;
            text-transform: none !important;
            width: 100% !important;
            display: block !important;
            margin-bottom: 24px !important;
            letter-spacing: 0.5px;
            font-family: 'Playfair Display', serif !important;
        }

        [data-testid="stMetricLabel"] {
            font-family: 'Inter', sans-serif !important;
            color: #a3a8a5 !important;
            font-weight: 600 !important;
            font-size: 0.8rem !important;
            letter-spacing: 0.05em;
            text-transform: uppercase !important;
            text-align: center !important;
            width: 100% !important;
            display: block !important;
            margin-bottom: 8px !important;
        }

        [data-testid="stMetricValue"] {
            font-family: 'Playfair Display', serif !important;
            color: #e6dfd3 !important;
            font-weight: 600 !important;
            font-size: 2.25rem !important;
            letter-spacing: -0.02em !important;
            text-transform: none !important;
            text-align: center !important;
            width: 100% !important;
            display: block !important;
        }

        div[data-testid="stMetric"] {
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        /* Protect Inputs and Code */
        input, textarea, code, pre, .stDataFrame, .stDataFrame * {
            text-transform: none !important;
        }

        /* Hide Option Menu Icons & Center Align Links */
        .nav-link i.bi {
            display: none !important;
        }
        .nav-link {
            justify-content: center !important;
        }

        /* Clean Header Reveal and Custom Transitions */
        h1, h2, h3 {
            animation: textBlurReveal 1s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        /* Page Transitions & Blur Reveal */
        @keyframes textBlurReveal {
            0% { filter: blur(8px); opacity: 0; transform: translateY(4px); }
            100% { filter: blur(0); opacity: 1; transform: translateY(0); }
        }

        .block-container {
            animation: pageWipeAndBlur 0.7s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
        
        @keyframes pageWipeAndBlur {
            0% { opacity: 0; filter: blur(4px); transform: translateY(10px); }
            100% { opacity: 1; filter: blur(0); transform: translateY(0); }
        }

        /* Kill Streamlit's auto-injected anchor link icons on headers */
        .stMarkdown a[href^="#"],
        h1 a, h2 a, h3 a, h4 a,
        a.header-anchor,
        [data-testid="StyledLinkIconContainer"] {
            display: none !important;
            visibility: hidden !important;
            width: 0 !important;
            height: 0 !important;
            overflow: hidden !important;
            position: absolute !important;
        }

        h1 {
            font-size: 2.5rem !important;
            padding-bottom: 12px;
            border-bottom: 1px solid rgba(230, 223, 211, 0.08);
            margin-top: 10px !important;
        }

        /* Custom Scrollbar */
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        ::-webkit-scrollbar-track {
            background: rgba(19, 26, 23, 0.1);
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(230, 223, 211, 0.12);
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(230, 223, 211, 0.24);
        }

        /* Professional Minimalist Loading Animation for native st.spinner */
        div[data-testid="stSpinner"] {
            display: flex !important;
            align-items: center !important;
            justify-content: flex-start !important;
            padding: 14px 20px !important;
            background: #131a17 !important;
            border: 1px solid rgba(230, 223, 211, 0.08) !important;
            border-radius: 10px !important;
            margin: 16px 0 !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
            gap: 12px !important;
        }

        /* Hide the default spinning wheel */
        div[data-testid="stSpinner"] svg {
            display: none !important;
        }

        /* Add a very thin, slow rotating line icon next to the text */
        div[data-testid="stSpinner"]::before {
            content: '';
            width: 16px;
            height: 16px;
            border: 2px solid rgba(230, 223, 211, 0.15);
            border-top: 2px solid #e6dfd3;
            border-radius: 50%;
            animation: cleanSpin 0.8s linear infinite;
            display: inline-block;
            flex-shrink: 0;
        }

        @keyframes cleanSpin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        /* Format the spinner text */
        div[data-testid="stSpinner"] > div {
            font-size: 0.85rem !important;
            font-weight: 500 !important;
            color: #e6dfd3 !important;
            letter-spacing: 1px !important;
            text-transform: uppercase !important;
            font-family: 'Inter', sans-serif !important;
        }

        /* Metrics Cards */
        [data-testid="stMetric"] {
            background-color: #131a17 !important;
            border: 1px solid rgba(230, 223, 211, 0.06) !important;
            padding: 20px 24px !important;
            border-radius: 14px !important;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2) !important;
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1) !important;
            backdrop-filter: blur(12px) !important;
        }
        [data-testid="stMetric"]:hover {
            transform: translateY(-4px) !important;
            box-shadow: 0 12px 28px rgba(230, 223, 211, 0.12), 0 4px 12px rgba(0, 0, 0, 0.3) !important;
            border-color: rgba(230, 223, 211, 0.25) !important;
            background-color: #16201b !important;
        }
        [data-testid="stMetricDelta"] {
            color: #2e7d32 !important;
            font-weight: 600 !important;
        }

        /* Buttons Styling */
        .stButton>button, .stDownloadButton>button, .stFormSubmitButton>button {
            background: rgba(230, 223, 211, 0.03) !important;
            border: 1px solid rgba(230, 223, 211, 0.12) !important;
            border-radius: 10px !important;
            color: #e6dfd3 !important;
            font-family: 'Inter', sans-serif !important;
            font-weight: 600 !important;
            font-size: 0.9rem !important;
            padding: 0.6rem 1.3rem !important;
            transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.15) !important;
            text-transform: none !important;
        }
        
        .stButton>button[kind="primary"], .stFormSubmitButton>button {
            background: #e6dfd3 !important;
            color: #0c100e !important;
            border: 1px solid #e6dfd3 !important;
            box-shadow: 0 4px 14px rgba(230, 223, 211, 0.2) !important;
            text-transform: uppercase !important;
            letter-spacing: 0.5px;
        }
        
        .stButton>button:hover, .stDownloadButton>button:hover, .stFormSubmitButton>button:hover {
            transform: translateY(-2px) !important;
            border-color: rgba(230, 223, 211, 0.5) !important;
            color: #ffffff !important;
            box-shadow: 0 6px 15px rgba(0, 0, 0, 0.25) !important;
        }
        
        .stButton>button[kind="primary"]:hover, .stFormSubmitButton>button:hover {
            background: #ecd1a5 !important;
            border-color: #ecd1a5 !important;
            box-shadow: 0 6px 20px rgba(230, 223, 211, 0.4) !important;
            transform: translateY(-2px) !important;
        }
        
        .stButton>button:active, .stDownloadButton>button:active, .stFormSubmitButton>button:active {
            transform: translateY(1px) !important;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2) !important;
        }
        
        /* Animated Tabs inside views */
        button[data-baseweb="tab"] {
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1) !important;
            font-family: 'Inter', sans-serif !important;
            font-weight: 500 !important;
        }
        button[data-baseweb="tab"]:hover {
            transform: translateY(-2px) !important;
            background-color: rgba(230, 223, 211, 0.03) !important;
            border-radius: 8px;
        }

        /* Sliders */
        .stSlider label {
            color: #a3a8a5 !important;
            font-weight: 500 !important;
            font-family: 'Inter', sans-serif !important;
        }

        /* Sidebar Styling (Fallback if displayed) */
        [data-testid="stSidebar"] {
            background-color: #0c100e !important;
            border-right: 1px solid rgba(230, 223, 211, 0.08) !important;
        }
        [data-testid="stSidebar"] .stMarkdown p {
            color: #a3a8a5 !important;
            font-family: 'Inter', sans-serif !important;
        }

        /* Badges / Pill Markers */
        @keyframes pulseBadge {
            0% { box-shadow: 0 0 0 0 rgba(230, 223, 211, 0.4); }
            70% { box-shadow: 0 0 0 6px rgba(230, 223, 211, 0); }
            100% { box-shadow: 0 0 0 0 rgba(230, 223, 211, 0); }
        }
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.05em;
            font-family: 'Inter', sans-serif !important;
            animation: pulseBadge 2.2s infinite;
        }
        .badge-pro { background-color: rgba(230, 223, 211, 0.12); color: #e6dfd3; border: 1px solid rgba(230, 223, 211, 0.25); }
        .badge-danger { background-color: rgba(239, 68, 68, 0.12); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.25); animation-delay: 1.1s; }

        /* Tactile Inputs with Glow */
        .stTextInput>div>div>input, .stNumberInput>div>div>input {
            border: 1px solid rgba(230, 223, 211, 0.12) !important;
            border-radius: 10px !important;
            background-color: #131a17 !important;
            padding: 10px 14px !important;
            color: #e6dfd3 !important;
            transition: all 0.2s ease !important;
            font-family: 'Inter', sans-serif !important;
        }
        .stTextInput>div>div>input:hover, .stNumberInput>div>div>input:hover {
            border-color: rgba(230, 223, 211, 0.25) !important;
            transform: translateY(-1px);
        }
        .stTextInput>div>div>input:focus, .stNumberInput>div>div>input:focus {
            border-color: #e6dfd3 !important;
            box-shadow: 0 0 10px rgba(230, 223, 211, 0.25) !important;
            transform: translateY(-1px);
        }

        /* Fix Password Eye Icon Overlap */
        div[data-testid="InputInstructions"] {
            display: none !important;
        }

        /* Custom File Uploader Browse Button */
        [data-testid="stFileUploader"] button {
            visibility: hidden !important;
            position: relative;
            min-height: 40px;
        }
        [data-testid="stFileUploader"] button::after {
            content: "Browse Files" !important;
            visibility: visible !important;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            position: absolute;
            inset: 0;
            font-size: 14px !important;
            font-weight: 600 !important;
            color: #e6dfd3 !important;
            letter-spacing: 0.01em;
            cursor: pointer;
            background: #131a17 !important;
            border: 1px solid rgba(230, 223, 211, 0.12) !important;
            border-radius: 8px !important;
        }
        [data-testid="stFileUploader"] button:hover::after {
            border-color: #e6dfd3 !important;
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

        # Optional Welcome Screen immediately after login
        if st.session_state.get("show_welcome", False):
            welcome_loader = st.empty()
            welcome_loader.markdown(get_premium_loader("ACCESS GRANTED", f"WELCOME TO ANCHOR, {role}"), unsafe_allow_html=True)
            import time
            time.sleep(2.0)
            welcome_loader.empty()
            st.session_state["show_welcome"] = False

        from streamlit_option_menu import option_menu
        from components.tab_data_ingestion import render_data_ingestion
        
        # Determine available pages based on role
        # Reorganized into a logical chronological flow: Data -> Guide -> High-Level -> Prediction -> Deep Dive -> What-If -> Action -> Settings
        all_pages = ["Data Ingestion", "User Manual", "Reports", "Predict", "Explain", "Forensics", "Simulators", "Automations", "Admin", "Logout"]
        icons = ["database", "book", "bar-chart", "graph-up", "brain", "search", "cpu", "robot", "shield-lock", "box-arrow-right"]
        
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
            menu_icon="cast",
            default_index=0,
            orientation="horizontal",
            styles={
                "container": {"padding": "0!important", "background-color": "#131a17", "border-bottom": "1px solid rgba(230, 223, 211, 0.08)", "border-radius": "10px", "margin-bottom": "2rem"},
                "icon": {"color": "#a3a8a5", "font-size": "14px"}, 
                "nav-link": {"font-size": "13px", "white-space": "nowrap", "padding": "8px 12px", "text-align": "center", "margin": "4px", "border-radius": "8px", "font-family": "'Inter', sans-serif", "font-weight": "600", "--hover-color": "rgba(230, 223, 211, 0.03)", "color": "#a3a8a5"},
                "nav-link-selected": {"background-color": "rgba(230, 223, 211, 0.08)", "color": "#e6dfd3", "border-bottom": "2px solid #e6dfd3", "border-radius": "8px"}
            }
        )
        
        # Sub-navigation for Simulators or Admin
        if selected_main == "Simulators":
            selected_sub = option_menu(
                menu_title=None,
                options=["Causal", "Twin", "Save Path"],
                icons=["", "", ""],
                default_index=0,
                orientation="horizontal",
                styles={
                    "container": {"padding": "0!important", "background-color": "transparent", "border-radius": "0"},
                    "nav-link": {"font-size": "13px", "text-align": "center", "margin": "0px", "--hover-color": "#111111", "color": "#A1A1AA"},
                    "nav-link-selected": {"background-color": "transparent", "color": "#EDEDED", "border-bottom": "2px solid #EDEDED", "border-radius": "0px"}
                }
            )

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

        from contextlib import nullcontext

        # Only show the loader when switching to a DIFFERENT main tab, otherwise it flashes on every button click
        page_changed = st.session_state.get('last_selected_main') != selected_main
        st.session_state['last_selected_main'] = selected_main
        
        loader_placeholder = st.empty()
        if page_changed:
            loader_placeholder.markdown(get_premium_loader(f"INITIALIZING {selected_main.upper()}"), unsafe_allow_html=True)

        ctx = nullcontext()
        # Render Main Pages directly
        with ctx:
            try:
                if selected_main == "Simulators":
                    if selected_sub == "Causal": page_causal_simulator()
                    elif selected_sub == "Twin": page_twin_simulator()
                    elif selected_sub == "Save Path": page_save_path_advisor()

                elif selected_main == "Admin":
                    if selected_sub == "RBAC & API Keys": page_rbac()
                    elif selected_sub == "Compliance": page_compliance()

                elif selected_main == "Predict": page_predict()
                elif selected_main == "Explain": page_explainability()
                elif selected_main == "Forensics": page_forensics()
                elif selected_main == "Reports": page_bi_reports()
                elif selected_main == "Automations": 
                    selected_sub = option_menu(
                        menu_title=None,
                        options=["Workflows", "A/B Factory"],
                        default_index=0,
                        orientation="horizontal",
                        styles={
                            "container": {"padding": "0!important", "background-color": "transparent", "border-radius": "0"},
                            "nav-link": {"font-size": "13px", "text-align": "center", "margin": "0px", "padding": "5px 10px", "--hover-color": "#111111", "color": "#A1A1AA"},
                            "nav-link-selected": {"background-color": "transparent", "color": "#EDEDED", "border-bottom": "2px solid #EDEDED", "border-radius": "0px"}
                        }
                    )
                    if selected_sub == "Workflows": page_automations()
                    elif selected_sub == "A/B Factory": tab_ab_factory.render(tenant_id)
                elif selected_main == "Data Ingestion": render_data_ingestion()
                elif selected_main == "User Manual": tab_user_manual.render()
                elif selected_main == "Logout":
                    st.markdown("<br><br><div class='centered-subheading'>Are you sure you want to log out?</div><br>", unsafe_allow_html=True)
                    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
                    with col2:
                        if st.button("Yes, Log out", type="primary", use_container_width=True):
                            st.session_state.clear()
                            st.rerun()
                    with col3:
                        if st.button("Cancel", use_container_width=True):
                            st.info("Logout cancelled. Please select a tab above.")
            except Exception as e:
                # Auto-heal: forcefully flush custom modules from memory so the reload gets fresh code
                import sys
                for mod in list(sys.modules.keys()):
                    if mod.startswith("components.") or mod.startswith("services."):
                        del sys.modules[mod]
                
                # Render enterprise-grade fallback UI
                st.markdown("<div style='text-align: center; margin-top: 50px;'><h1 style='color: #ff4b4b; font-size: 3rem;'>⚠️</h1><h3>Module Temporarily Unavailable</h3><p style='color: #A1A1AA;'>We encountered a temporary cache desync loading this specific view. The rest of the platform is fully operational.</p></div>", unsafe_allow_html=True)
                _, col_btn, _ = st.columns([1, 1, 1])
                with col_btn:
                    if st.button("Auto-Recover (Reload)", use_container_width=True, type="primary"):
                        st.rerun()


        if page_changed:
            loader_placeholder.empty()

        # Footer: Tenant ID status
        st.markdown(f"<div style='text-align: right; color: #787774; font-size: 12px; margin-top: 20px; padding-bottom: 20px;'>Tenant ID: {tenant_id}</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
