"""
components/tab_customer360.py
──────────────────────────────
Tab 4 — Customer 360 & What-If Sandbox
Renders: UID search, 6-metric telemetry bar, live What-If simulator with probability output.
"""
import streamlit as st
import requests
from .utils import render_html, risk_color, RED, GREEN, AMBER, MUTED, SURFACE, BORDER, NEON

API_BASE = "http://127.0.0.1:8000"


def _simulate(token: str, payload: dict):
    try:
        resp = requests.post(
            f"{API_BASE}/simulate",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def render(df, token: str):
    render_html([
        "<h2 style='margin:0 0 16px;color:#fff;font-size:16px;font-weight:500;letter-spacing:-0.2px;'>"
        "Customer 360 Profile</h2>",
        f"<p style='color:{MUTED};font-size:13px;margin:0 0 20px;'>"
        "Select a user account to inspect live telemetry and run What-If risk simulations.</p>",
    ])

    # ── UID Search ────────────────────────────────────────────────────
    uid = st.selectbox(
        "Search / Select Target UID",
        options=df["user_id"].tolist(),
        help="Pick any customer to load their full 360 profile",
    )
    if not uid:
        return

    row = df[df["user_id"] == uid].iloc[0]
    orig_prob  = float(row.get("churn_probability", 0))
    orig_color = risk_color(orig_prob)

    # ── Current Telemetry ─────────────────────────────────────────────
    st.markdown(
        "<h3 style='margin:0 0 16px;color:#fff;font-size:16px;font-weight:500;letter-spacing:-0.2px;'>"
        "Live Telemetry Snapshot</h3>",
        unsafe_allow_html=True,
    )
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Days Inactive",     f"{int(row['recency_days'])} d")
    m2.metric("Total Orders",      f"{int(row['frequency'])}")
    m3.metric("Lifetime Spend",    f"${row['monetary_value']:,.2f}")
    m4.metric("Session Crashes",   f"{int(row['session_failures'])}")
    m5.metric("Friction Index",    f"{row['payment_friction_index']:.1f}")
    m6.metric("Support Tickets",   f"{int(row['active_support_tickets'])}")

    # Risk badge
    render_html([
        f"<div style='margin:14px 0;padding:14px 20px;background:{SURFACE};"
        f"border:1px solid {BORDER};border-left:4px solid {orig_color};border-radius:6px;"
        "display:flex;justify-content:space-between;align-items:center;'>",
        f"<span style='color:{MUTED};font-size:12px;text-transform:uppercase;letter-spacing:1px;'>"
        "Current Churn Risk</span>",
        f"<span style='font-family:monospace;font-size:28px;font-weight:800;color:{orig_color};'>"
        f"{orig_prob*100:.1f}%</span>",
        f"<span style='color:{MUTED};font-size:12px;'>Segment: "
        f"<b style='color:#fff;'>{row.get('segment','—')}</b></span>",
        "</div>",
    ])

    st.markdown(
        f"<hr style='border:none;border-top:1px solid {BORDER};margin:22px 0;'>",
        unsafe_allow_html=True,
    )

    # ── What-If Simulator ─────────────────────────────────────────────
    st.markdown(
        "<h3 style='margin:0 0 16px;color:#fff;font-size:16px;font-weight:500;letter-spacing:-0.2px;'>"
        "Live What-If Simulator</h3>",
        unsafe_allow_html=True,
    )
    left, right = st.columns([1, 1], gap="large")

    with left:
        st.markdown(
            f"<p style='color:{MUTED};font-size:12px;margin:0 0 14px;text-transform:uppercase;"
            "letter-spacing:1px;'>Adjust Variables</p>",
            unsafe_allow_html=True,
        )
        s_recency   = st.slider("Days Inactive",          0,   120, int(row["recency_days"]),       key=f"s_rec_{uid}")
        s_freq      = st.slider("Total Orders",           0,    50, int(row["frequency"]),           key=f"s_frq_{uid}")
        s_monetary  = st.slider("Lifetime Spend ($)",    0.0, 5000.0, float(row["monetary_value"]), key=f"s_mon_{uid}")
        s_failures  = st.slider("Session Crashes",        0,    10, int(row["session_failures"]),    key=f"s_fal_{uid}")
        s_friction  = st.slider("Payment Friction Index", 0.0, 10.0, float(row["payment_friction_index"]), key=f"s_fri_{uid}")
        s_tickets   = st.slider("Support Tickets",        0,     5, int(row["active_support_tickets"]),    key=f"s_tix_{uid}")

    with right:
        result = _simulate(token, {
            "recency_days": s_recency, "frequency": s_freq, "monetary_value": s_monetary,
            "session_failures": s_failures, "payment_friction_index": s_friction,
            "active_support_tickets": s_tickets,
        })

        if result:
            new_prob   = float(result.get("churn_probability", 0))
            new_color  = risk_color(new_prob)
            diff       = new_prob - orig_prob
            diff_sign  = "+" if diff > 0 else ""
            diff_color = RED if diff > 0 else GREEN

            render_html([
                f"<div style='background:{SURFACE};border:1px solid {BORDER};padding:28px 24px;"
                "border-radius:8px;text-align:center;height:100%;'>",

                # Original
                f"<p style='color:{MUTED};font-size:11px;letter-spacing:2px;text-transform:uppercase;margin:0;'>Original Risk</p>",
                f"<p style='font-family:monospace;font-size:32px;color:{orig_color};"
                f"font-weight:800;margin:4px 0 18px;'>{orig_prob*100:.1f}%</p>",

                f"<hr style='border:none;border-top:1px solid {BORDER};margin:0 0 18px;'>",

                # Simulated
                f"<p style='color:{MUTED};font-size:11px;letter-spacing:2px;text-transform:uppercase;margin:0;'>Simulated Risk</p>",
                f"<p style='font-family:monospace;font-size:68px;color:{new_color};"
                f"font-weight:900;margin:4px 0;line-height:1;'>{new_prob*100:.1f}%</p>",

                # Delta
                f"<p style='font-family:monospace;font-size:18px;color:{diff_color};"
                f"font-weight:700;margin:10px 0 0;'>&#916; {diff_sign}{diff*100:.1f}%</p>",

                # Verdict
                f"<p style='font-size:11px;color:{MUTED};margin:16px 0 0;'>",
                ("Immediate intervention required." if new_prob > 0.70
                 else "Monitor closely." if new_prob > 0.30
                 else "Account recovering. Keep conditions stable."),
                "</p></div>",
            ])
        else:
            render_html([
                f"<div style='background:{SURFACE};border:1px solid {BORDER};padding:28px;"
                f"border-radius:8px;text-align:center;color:{MUTED};font-size:13px;'>",
                "Simulator offline — check that the FastAPI server is running.",
                "</div>",
            ])
