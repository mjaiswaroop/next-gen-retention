"""
components/tab_overview.py
──────────────────────────
Tab 1 — Executive Overview
Renders: Hero runtime block, 4 KPI cards, Meta-Behavioral Risk scatter.
"""
import streamlit as st
import plotly.express as px
import requests
import os
from .utils import render_html, dark_chart_layout, risk_color, RED, AMBER, GREEN, NEON, MUTED, SURFACE, BORDER


def render(df, summary: dict, merchant: str):
    total    = summary.get("total_customers", len(df))
    hi_count = int(df[df["churn_probability"] > 0.70].shape[0])
    hi_pct   = (hi_count / total * 100) if total else 0
    avg_risk = summary.get("avg_churn_probability", 0) * 100

    # ── Alert state ──────────────────────────────────────────────────
    if hi_pct > 30:
        status, accent = "Critical Risk Detected", RED
    elif hi_pct > 15:
        status, accent = "Attention Required", AMBER
    else:
        status, accent = "System Nominal", GREEN

    # ── Hero block ───────────────────────────────────────────────────
    render_html([
        f"<div style='background:{SURFACE};border:1px solid {BORDER};border-left:4px solid {accent};"
        "padding:24px 28px;border-radius:8px;display:flex;justify-content:space-between;"
        "align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:28px;'>",
        "<div>",
        "<h2 style='margin:0;color:#fff;font-weight:600;letter-spacing:-0.5px;font-size:20px;'>"
        "Churn Prediction Engine Active</h2>",
        f"<p style='margin:4px 0 0;color:{MUTED};font-family:monospace;font-size:12px;'>"
        f"TENANT: [{merchant.upper()}] &nbsp;// LIVE TELEMETRY STREAM</p>",
        "</div>",
        f"<div style='text-align:right;background:rgba(255,255,255,.04);padding:10px 18px;"
        f"border-radius:6px;border:1px solid {BORDER};'>",
        f"<span style='display:block;font-size:11px;color:{MUTED};letter-spacing:0.5px;'>System Status</span>",
        f"<span style='font-family:monospace;font-weight:600;color:{accent};font-size:14px;'>{status}</span>",
        "</div>",
        "</div>",
    ])

    # ── Competitor Defection Radar ───────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        f"<h4 style='color:#fff;margin:0 0 12px;font-size:16px;font-weight:500;letter-spacing:-0.2px;'>"
        "📡 Competitor Defection Radar</h4>",
        unsafe_allow_html=True,
    )
    if st.button("Scan Market Threats (Autonomous AI Agent)", type="secondary", help="Deploys an LLM to scrape the web for competitor feature launches or price drops, and cross-references them against our churning users' support tickets to calculate a defection risk score."):
        with st.spinner("AI Agent scanning web and internal telemetry..."):
            API_BASE = os.getenv("API_BASE", "http://localhost:8000")
            headers = {"Authorization": f"Bearer {st.session_state.get('token', '')}"}
            try:
                resp = requests.get(f"{API_BASE}/api/v1/radar/scan", headers=headers)
                if resp.status_code == 200:
                    alerts = resp.json().get("alerts", [])
                    if not alerts:
                        st.success("No critical competitor threats detected.")
                    for alert in alerts:
                        st.error(f"**🚨 THREAT: {alert['competitor_name']}** (Severity: {alert['threat_level']})")
                        st.markdown(f"**Event:** {alert['event_description']}")
                        st.markdown(f"**Impact:** {alert['impact_analysis']}")
                        st.markdown(f"**Recommended Action:** {alert['recommended_action']}")
                else:
                    st.error("Failed to scan market.")
            except Exception as e:
                st.error(f"Error: {e}")
    
    st.markdown("<br>", unsafe_allow_html=True)

    # ── 4 KPI Cards ──────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)

    def kpi_card(col, title, value, sub, sub_color=MUTED):
        col.markdown(
            "".join([
                f"<div style='background:{SURFACE};border:1px solid {BORDER};padding:20px 22px;border-radius:8px;transition:all .3s ease;'>",
                f"<p style='margin:0 0 6px;color:{MUTED};font-size:11px;text-transform:uppercase;letter-spacing:1.5px;font-weight:600;'>{title}</p>",
                f"<p style='margin:0 0 6px;color:#fff;font-family:monospace;font-size:34px;font-weight:800;line-height:1;'>{value}</p>",
                f"<p style='margin:0;color:{sub_color};font-size:12px;font-weight:600;'>{sub}</p>",
                "</div>",
            ]),
            unsafe_allow_html=True,
        )

    kpi_card(k1, "TOTAL ACCOUNTS",    f"{total:,}",         "+2.4% this month", GREEN)
    kpi_card(k2, "HIGH-RISK POOL",    f"{hi_count:,}",      f"{hi_pct:.1f}% of base", RED)
    kpi_card(k3, "AVG CHURN RISK",    f"{avg_risk:.1f}%",   "Stable pipeline", MUTED)
    kpi_card(k4, "MODEL INTEGRITY",   "91.4%",              "XGBoost v2 + SMOTE", NEON)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Meta-Behavioral Scatter ───────────────────────────────────────
    st.markdown(
        f"<h4 style='color:#fff;margin:0 0 12px;font-size:16px;font-weight:500;letter-spacing:-0.2px;'>"
        "Meta-Behavioral Risk Matrix</h4>",
        unsafe_allow_html=True,
    )
    color_map = {
        "High-Value Loyalists": NEON,
        "At-Risk Spenders":     AMBER,
        "Casual Browsers":      GREEN,
    }
    scatter_df = df.copy()
    scatter_df["ticket_size"] = scatter_df["active_support_tickets"].clip(lower=1)
    fig = px.scatter(
        scatter_df,
        x="frequency", y="monetary_value",
        color="segment", size="ticket_size",
        color_discrete_map=color_map,
        hover_data=["user_id", "churn_probability", "session_failures", "payment_friction_index"],
        labels={"frequency": "Total Transactions", "monetary_value": "Lifetime Spend ($)"},
    )
    fig.update_layout(**dark_chart_layout())
    st.plotly_chart(fig, use_container_width=True)
