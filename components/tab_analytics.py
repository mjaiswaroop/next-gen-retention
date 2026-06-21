"""
components/tab_analytics.py
───────────────────────────
Tab 2 — Revenue & Cohort Analytics
Renders: Revenue leakage bar chart + Cohort retention heatmap.
"""
import streamlit as st
import plotly.express as px
import pandas as pd
import numpy as np
from .utils import dark_chart_layout, BORDER, MUTED


def render(df):
    c1, c2 = st.columns(2)

    # ── Revenue Leakage Bar ───────────────────────────────────────────
    with c1:
        st.markdown(
            "<h2 style='margin:0 0 16px;color:#fff;font-size:16px;font-weight:500;letter-spacing:-0.2px;'>"
            "Revenue Capture vs. Leakage</h2>",
            unsafe_allow_html=True,
        )
        # Calculate from real data where possible
        saved    = float(df[df["churn_probability"] < 0.30]["monetary_value"].sum())
        lost     = float(df[df["churn_probability"] > 0.70]["monetary_value"].sum() * 0.25)
        at_risk  = float(df[(df["churn_probability"] >= 0.30) & (df["churn_probability"] <= 0.70)]["monetary_value"].sum())

        rev_df = pd.DataFrame({
            "Category": ["Saved by Margin-Shield", "Lost to Churn", "At-Risk Runway"],
            "Value":    [saved, lost, at_risk],
            "Color":    ["#00b954", "#ff5449", "#f59e0b"],
        })
        fig_rev = px.bar(rev_df, x="Category", y="Value", text="Value")
        fig_rev.update_traces(
            marker_color=rev_df["Color"],
            texttemplate="$%{text:,.0f}",
            textposition="outside",
            textfont=dict(color="#fff"),
        )
        layout = dark_chart_layout()
        layout["yaxis"]["title"] = "Capital ($)"
        layout["xaxis"]["title"] = ""
        layout["showlegend"] = False
        fig_rev.update_layout(**layout)
        st.plotly_chart(fig_rev, use_container_width=True)

    # ── Cohort Retention Heatmap ──────────────────────────────────────
    with c2:
        st.markdown(
            "<h2 style='margin:0 0 16px;color:#fff;font-size:16px;font-weight:500;letter-spacing:-0.2px;'>"
            "Retention Cohorts</h2>",
            unsafe_allow_html=True,
        )
        cohort = np.array([
            [100, 85, 70, 65, 55, 50],
            [100, 88, 75, 68, 60, 52],
            [100, 90, 80, 72, 65, 58],
            [100, 92, 85, 78, 70, 62],
        ])
        fig_heat = px.imshow(
            cohort,
            labels=dict(x="Month", y="Cohort", color="Retention %"),
            x=["M1", "M2", "M3", "M4", "M5", "M6"],
            y=["Q1-Jan", "Q1-Feb", "Q1-Mar", "Q1-Apr"],
            color_continuous_scale=["#000000", "#6366f1"],
            zmin=45, zmax=100,
        )
        heat_layout = dark_chart_layout()
        heat_layout.pop("xaxis", None)
        heat_layout.pop("yaxis", None)
        heat_layout["coloraxis_colorbar"] = dict(
            tickfont=dict(color="#94a3b8"),
            title=dict(text="Ret %", font=dict(color="#94a3b8")),
        )
        fig_heat.update_layout(**heat_layout)
        st.plotly_chart(fig_heat, use_container_width=True)

    # ── Segment Distribution ──────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        "<h4 style='color:#fff;margin:0 0 12px;font-size:15px;letter-spacing:.5px;'>"
        "🧩 SEGMENT VALUE DISTRIBUTION</h4>",
        unsafe_allow_html=True,
    )
    seg_df = df.groupby("segment")["monetary_value"].sum().reset_index()
    seg_df.columns = ["Segment", "Revenue"]
    fig_seg = px.pie(
        seg_df, names="Segment", values="Revenue",
        hole=0.55,
        color="Segment",
        color_discrete_map={
            "High-Value Loyalists": "#6366f1",
            "At-Risk Spenders":     "#f59e0b",
            "Casual Browsers":      "#00b954",
        },
    )
    fig_seg.update_traces(textposition="outside", textinfo="label+percent")
    fig_seg.update_layout(**dark_chart_layout(showlegend=True, margin=dict(l=40, r=40, t=20, b=40)))
    st.plotly_chart(fig_seg, use_container_width=True)
