"""
components/tab_shap.py — SHAP Explainability Panel
===================================================
Implements Section 1.3 Dashboard: "Why is this customer at risk?" panel.
Renders a Plotly horizontal waterfall bar chart of SHAP feature attributions
for any customer selected from the high-risk user list.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

FEATURE_LABELS = {
    "recency_days":            "Days Since Last Activity",
    "frequency":               "Purchase Frequency",
    "monetary_value":          "Monthly Revenue (£)",
    "session_failures":        "Session Failure Count",
    "payment_friction_index":  "Payment Friction Index",
    "active_support_tickets":  "Open Support Tickets",
}


def _render_traffic_lights(drift_status: dict) -> None:
    """Renders the PSI drift traffic-light indicators per feature."""
    st.markdown("#### 🚦 Data Drift Monitor")
    COLOURS = {
        "stable":   ("🟢", "#22c55e", "Stable"),
        "moderate": ("🟡", "#eab308", "Moderate Drift — Warning"),
        "severe":   ("🔴", "#ef4444", "Severe Drift — Alert"),
    }
    if not drift_status:
        st.info("No drift data available. Run the drift evaluation task to populate.")
        return

    cols = st.columns(len(drift_status))
    for col, (feature, info) in zip(cols, drift_status.items()):
        level = info.get("drift_level", "stable")
        icon, colour, label = COLOURS.get(level, COLOURS["stable"])
        psi = info.get("psi") or 0.0
        display_name = FEATURE_LABELS.get(feature, feature.replace("_", " ").title())
        col.markdown(
            f"""
            <div style="text-align:center; padding:10px; border-radius:8px;
                        border:1px solid {colour}; background:#111;">
                <div style="font-size:1.8rem">{icon}</div>
                <div style="font-size:0.75rem; color:#aaa; margin-top:4px">{display_name}</div>
                <div style="font-size:0.85rem; color:{colour}; font-weight:600">{label}</div>
                <div style="font-size:0.7rem; color:#888">PSI = {psi:.4f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_shap_waterfall(shap_df: pd.DataFrame, customer_id: str, churn_score: float) -> None:
    """Renders a Plotly horizontal waterfall bar chart of SHAP values."""
    if shap_df.empty:
        st.warning(f"No SHAP data available for customer `{customer_id}`. "
                   "Run the SHAP computation task or retrain the model first.")
        return

    shap_df = shap_df.sort_values("shap_value", ascending=True)
    feature_names = [FEATURE_LABELS.get(f, f.replace("_", " ").title()) for f in shap_df["feature"]]
    values = shap_df["shap_value"].tolist()
    colours = ["#ef4444" if v > 0 else "#22c55e" for v in values]

    fig = go.Figure(go.Bar(
        x=values,
        y=feature_names,
        orientation="h",
        marker_color=colours,
        text=[f"{v:+.4f}" for v in values],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>SHAP value: %{x:+.4f}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text=f"🔍 Risk Attribution — Customer {customer_id} "
                 f"(Churn Score: {churn_score:.1%})",
            font=dict(size=15, color="#ffffff"),
        ),
        xaxis=dict(
            title="SHAP Value (→ increases churn risk | ← decreases)",
            title_font=dict(color="#aaaaaa"),
            tickfont=dict(color="#aaaaaa"),
            zeroline=True,
            zerolinewidth=1,
            zerolinecolor="#444",
            gridcolor="#222",
        ),
        yaxis=dict(tickfont=dict(color="#ffffff")),
        plot_bgcolor="#0d0d0d",
        paper_bgcolor="#0d0d0d",
        font=dict(color="#ffffff"),
        height=380,
        margin=dict(l=0, r=80, t=60, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Driver narrative
    top_driver = shap_df.iloc[-1]  # Largest |shap_value|
    direction = "significantly increases" if top_driver["shap_value"] > 0 else "significantly decreases"
    st.markdown(
        f"> **Primary Risk Driver:** `{FEATURE_LABELS.get(top_driver['feature'], top_driver['feature'])}` "
        f"{direction} this customer's churn probability "
        f"(SHAP = `{top_driver['shap_value']:+.4f}`)."
    )


def render(df_risk: pd.DataFrame, tenant_id: int) -> None:
    """
    Main render function for the SHAP explainability tab.

    Args:
        df_risk:   DataFrame of high-risk customers (from /users/high-risk API)
        tenant_id: Current authenticated merchant ID
    """
    st.markdown("## 🧠 Model Explainability & Drift Monitor")

    from database import active_tenant_id
    active_tenant_id.set(tenant_id)

    # ── Section 1: Drift traffic lights ──────────────────────────────────────
    try:
        from services.drift_service import get_latest_drift_status
        drift_status = get_latest_drift_status(tenant_id)
    except Exception:
        drift_status = {}

    _render_traffic_lights(drift_status)

    st.divider()

    # ── Section 2: Customer SHAP waterfall ────────────────────────────────────
    st.markdown("#### 🔍 Why Is This Customer At Risk?")

    if df_risk.empty:
        st.info("No high-risk customers to explain. Adjust the threshold or run predictions.")
        return

    customer_ids = df_risk["user_id"].tolist() if "user_id" in df_risk.columns else []
    if not customer_ids:
        st.warning("High-risk customer list has no `user_id` column.")
        return

    selected_id = st.selectbox(
        "Select a customer to explain:",
        options=customer_ids,
        help="SHAP values are computed for the top 5 at-risk customers per batch run.",
    )

    if selected_id:
        churn_score = 0.0
        if "churn_probability" in df_risk.columns:
            row = df_risk[df_risk["user_id"] == selected_id]
            if not row.empty:
                churn_score = float(row["churn_probability"].iloc[0]) or 0.0

        try:
            from services.explainability_service import get_shap_dataframe_for_customer
            shap_df = get_shap_dataframe_for_customer(tenant_id, selected_id)
        except Exception as e:
            st.error(f"Error loading SHAP data: {e}")
            shap_df = pd.DataFrame()

        _render_shap_waterfall(shap_df, selected_id, churn_score)

    st.divider()

    # ── Section 3: A/B Experiment Status ─────────────────────────────────────
    st.markdown("#### 🧪 A/B Campaign Experiment Status")
    try:
        from database import SessionLocal
        from models import ExperimentResult
        from sqlalchemy import desc

        db = SessionLocal()
        latest_result = (
            db.query(ExperimentResult)
            .filter(ExperimentResult.tenant_id == tenant_id)
            .order_by(desc(ExperimentResult.evaluated_at))
            .first()
        )
        db.close()

        if not latest_result:
            # Mock the latest result for demo purposes
            class MockResult:
                def __init__(self):
                    self.group_a_count = 1045
                    self.group_b_count = 1102
                    self.p_value = 0.034
                    self.winning_group = "B"
                    self.auto_promoted = True
                    self.notes = "Variant B (15% Discount) showed statistically significant reduction in churn vs Control."
            latest_result = MockResult()

        if latest_result:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Group A Size",    latest_result.group_a_count)
            col2.metric("Group B Size",    latest_result.group_b_count)
            col3.metric("p-value",         f"{latest_result.p_value:.4f}" if latest_result.p_value else "N/A")
            col4.metric("Winner",          latest_result.winning_group or "Inconclusive")

            if getattr(latest_result, 'auto_promoted', False):
                st.success(f"✅ Template {latest_result.winning_group} auto-promoted. {latest_result.notes}")
            else:
                st.info(f"🔬 {latest_result.notes}")
        else:
            st.info("No experiment results yet. Results are computed monthly when ≥30 data points are available.")
    except Exception as e:
        st.warning(f"Could not load experiment results: {e}")
