"""
Data & Integrations Tab
"""
import streamlit as st
import requests
import pandas as pd
import io
import os

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")

def render_data_ingestion():
    st.markdown("<h2>Data Ingestion</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#A1A1AA;'>Upload your customer datasets to the platform.</p>", unsafe_allow_html=True)
    
    st.markdown("### Upload Customer Data")
    st.info("Upload **any** CSV file containing your customer records. The only strictly required column is `user_id`. Any additional columns (e.g., `delivery_time`, `store_visits`) will be automatically detected and mapped dynamically!")
    
    # Provide template download
    df_template = pd.DataFrame({
        "user_id": ["CUST-001", "CUST-002"],
        "prime_member": [True, False],
        "last_delivery_days": [2, 14],
        "loyalty_points": [1500, 200],
        "favorite_category": ["Electronics", "Groceries"],
        "recency_days": [12.5, 4.0],
        "monetary_value": [150.75, 450.00]
    })
    csv_buffer = io.StringIO()
    df_template.to_csv(csv_buffer, index=False)
    st.download_button(
        label="Download CSV Template",
        data=csv_buffer.getvalue(),
        file_name="customer_data_template.csv",
        mime="text/csv"
    )
    
    st.markdown("<hr>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    
    if uploaded_file is not None:
        if st.button("Ingest Data", type="primary"):
            with st.spinner("Uploading and processing data..."):
                token = st.session_state.get("token")
                headers = {"Authorization": f"Bearer {token}"}
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "text/csv")}
                
                try:
                    resp = requests.post(f"{API_BASE}/api/v1/data/upload_csv", headers=headers, files=files)
                    if resp.status_code == 200:
                        data = resp.json()
                        st.success(f"{data['message']}")
                        st.balloons()
                    else:
                        st.error(f"Upload failed: {resp.json().get('detail', 'Unknown error')}")
                except Exception as e:
                    st.error(f"Connection failed: {e}")
