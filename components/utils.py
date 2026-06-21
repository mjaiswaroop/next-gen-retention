"""
components/utils.py
───────────────────
Shared utilities for all dashboard component modules.
- render_html(): safe HTML injector that never uses multi-line f-strings
- dark_chart_layout(): Plotly dark-theme layout defaults
- risk_color(): probability → CSS color
"""
import streamlit as st


# ── Color tokens (Enterprise Dark Mode) ────────────────────────
NEON   = "#00f6ff"  # Cyan Neon
PURPLE = "#a855f7"  # Purple 500
GREEN  = "#10b981"  # Emerald 500
AMBER  = "#f59e0b"  # Amber 500
RED    = "#ef4444"  # Red 500
MUTED  = "#64748b"  # Slate 500
SURFACE = "#0f172a" # Slate 900
BORDER  = "#1e293b" # Slate 800

COLOR_MAP = {
    "High-Value Loyalists": NEON,
    "At-Risk Spenders":     AMBER,
    "Casual Browsers":      GREEN,
}


def risk_color(prob: float) -> str:
    """Map a churn probability (0-1) to a CSS colour string."""
    if prob > 0.70:
        return RED
    if prob > 0.30:
        return AMBER
    return GREEN


def render_html(parts: list) -> None:
    """
    Join a list of HTML string fragments and pass to st.markdown.

    Using a list instead of a multi-line f-string prevents Streamlit's
    Markdown parser from treating indented lines as code blocks.
    """
    st.markdown("".join(str(p) for p in parts), unsafe_allow_html=True)


def dark_chart_layout(**overrides) -> dict:
    """Return a Plotly layout dict pre-configured for the minimalist UI dark theme."""
    base = dict(
        paper_bgcolor="#0A0A0A",
        plot_bgcolor="#0A0A0A",
        font=dict(color="#EDEDED", family="'Inter', sans-serif", size=13),
        xaxis=dict(zeroline=False, linecolor="#333333", showgrid=True, gridwidth=1, gridcolor="#333333"),
        yaxis=dict(zeroline=False, linecolor="#333333", showgrid=True, gridwidth=1, gridcolor="#333333"),
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", y=1.1, x=0, bgcolor="#0A0A0A", bordercolor="#333333", borderwidth=1, font=dict(color="#A1A1AA")),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#111111", font_size=13, font_family="'Inter', sans-serif", bordercolor="#333333"),
    )
    base.update(overrides)
    return base
