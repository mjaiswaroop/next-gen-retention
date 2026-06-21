import streamlit as st
import pandas as pd
import plotly.express as px
import requests

from dashboard import check_auth, get_api_headers

st.set_page_config(page_title="Priority Queue", page_icon="🎯", layout="wide")

if not check_auth():
    st.stop()

st.title("Economic Prioritization Engine")
st.markdown("Identifies and ranks active customers based on Expected Value Score (EVS).")
st.latex(r"EVS = \text{Churn Probability} \times \text{Customer Lifetime Value (CLV)} \times \text{Causal Uplift}")

@st.cache_data(ttl=60)
def fetch_priority_queue():
    resp = requests.get("http://localhost:8000/api/v1/priority/queue", headers=get_api_headers())
    if resp.status_code == 200:
        return resp.json()
    st.error(f"Failed to fetch priority queue: {resp.text}")
    return []

data = fetch_priority_queue()

if not data:
    st.info("No high-risk customers found in the priority queue.")
    st.stop()

df = pd.DataFrame(data)

# 4D Scatter Plot (X=Churn, Y=CLV, Size=Uplift, Color=Value)
st.subheader("4D Priority Matrix")

fig = px.scatter(
    df,
    x="churn_probability",
    y="clv",
    size="causal_uplift",
    color="expected_value_score",
    hover_name="name",
    hover_data=["customer_id", "segment"],
    color_continuous_scale="Viridis",
    labels={
        "churn_probability": "Churn Risk (0-1)",
        "clv": "Lifetime Value ($)",
        "causal_uplift": "Uplift Potential",
        "expected_value_score": "EVS"
    },
    title="Customer Prioritization Scatter"
)

fig.update_layout(
    xaxis_title="Churn Probability",
    yaxis_title="CLV ($)",
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)"
)
st.plotly_chart(fig, use_container_width=True)

# Data Table
st.subheader("Top Priority Targets")
st.dataframe(
    df[["name", "segment", "churn_probability", "clv", "causal_uplift", "expected_value_score"]].style.format({
        "churn_probability": "{:.1%}",
        "clv": "${:,.2f}",
        "causal_uplift": "{:.1%}",
        "expected_value_score": "{:.2f}"
    }),
    use_container_width=True
)
