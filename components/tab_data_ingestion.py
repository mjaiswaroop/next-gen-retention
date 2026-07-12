"""
Data & Integrations Tab
"""
import streamlit as st
import requests
import pandas as pd
import io
import os

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")

# Fuzzy matching lists
SYNONYMS = {
    "user_id": ["customer_id", "userid", "user_id", "client_id", "id", "customer", "cust_id", "uuid", "uid"],
    "recency_days": ["recency", "recency_days", "last_active", "days_since_active", "days_since_last_active", "last_login", "days_since_login", "inactive_days"],
    "frequency": ["frequency", "orders", "purchases", "purchases_count", "total_orders", "sessions", "visits", "order_count"],
    "monetary_value": ["monetary", "monetary_value", "revenue", "spend", "total_spend", "value", "ltv", "lifetime_value", "amount", "total_amount"],
    "session_failures": ["session_failures", "failures", "errors", "crashes", "crashes_count", "failed_sessions", "session_errors"],
    "payment_friction_index": ["payment_friction", "payment_friction_index", "friction", "payment_failures", "checkout_friction", "friction_index"],
    "active_support_tickets": ["active_support_tickets", "tickets", "support_tickets", "open_tickets", "cases", "active_cases", "support_cases"],
    "segment": ["segment", "tier", "group", "class", "customer_segment", "customer_tier"]
}

CORE_FIELDS = {
    "user_id": ("User / Customer ID", True),  # (label, is_required)
    "recency_days": ("Days since Last Activity", False),
    "frequency": ("Total Orders / Purchases", False),
    "monetary_value": ("Total Spend / Lifetime Value", False),
    "session_failures": ("App/Website Session Failures", False),
    "payment_friction_index": ("Payment Friction Index", False),
    "active_support_tickets": ("Active Support Tickets", False),
    "segment": ("Customer Segment", False)
}

def find_matching_column(csv_columns, field_name):
    syns = SYNONYMS.get(field_name, [])
    # 1. Exact or direct normalized match
    for col in csv_columns:
        normalized = str(col).lower().strip().replace(" ", "_").replace("-", "_")
        if normalized in syns:
            return col
    # 2. Substring matching fallback
    for col in csv_columns:
        normalized = str(col).lower().strip().replace(" ", "_").replace("-", "_")
        for syn in syns:
            if syn in normalized or normalized in syn:
                return col
    return None

def seed_demo_data(tenant_id):
    """Generates robust tenant seed data directly in-process for sandbox testing."""
    from database import SessionLocal, active_tenant_id
    from models import Customer, CustomerPreferences, EventLog, CustomerEdge
    import random
    from datetime import datetime, timezone, timedelta
    
    active_tenant_id.set(tenant_id)
    db = SessionLocal()
    try:
        # Check if they already have customers to avoid double seeding
        exists = db.query(Customer).filter_by(merchant_id=tenant_id).first()
        if exists:
            return False, "Your sandbox space already contains customer records."
            
        customers = []
        for i in range(1, 51):
            user_id = f"cust_{i:03d}"
            if i == 1:
                user_id = "cust_123"
            
            c = Customer(
                merchant_id=tenant_id,
                user_id=user_id,
                recency_days=random.uniform(0.5, 30.0),
                frequency=random.randint(1, 50),
                monetary_value=random.uniform(10.0, 5000.0),
                session_failures=random.randint(0, 5),
                payment_friction_index=random.uniform(0, 1.0),
                active_support_tickets=random.randint(0, 2),
                churn_probability=random.uniform(0.1, 0.99),
                segment=random.choice(["Enterprise", "Mid-Market", "SMB", "Prosumer"]),
                extra_features={"name": f"Demo Customer {i}", "email": f"customer_{i}@example.com"}
            )
            customers.append(c)
        db.add_all(customers)
        db.commit()

        # Referral Edges for contagion risk graphing
        edges = []
        for _ in range(25):
            source = random.choice(customers)
            target = random.choice(customers)
            if source != target:
                edges.append(CustomerEdge(
                    tenant_id=tenant_id,
                    source_customer_id=source.user_id,
                    target_customer_id=target.user_id,
                    edge_type="referral",
                    weight=random.uniform(0.4, 0.95)
                ))
        db.add_all(edges)
        db.commit()

        # Event logs for sentiment timelines
        logs = []
        for c in customers[:8]:
            for day in range(30):
                logs.append(EventLog(
                    merchant_id=tenant_id,
                    customer_id=c.id,
                    timestamp=datetime.now(timezone.utc) - timedelta(days=day),
                    event_type=random.choice(["login", "purchase", "support_ticket", "error"]),
                    sentiment_score=random.uniform(-1.0, 1.0)
                ))
        db.add_all(logs)
        db.commit()
        
        return True, "Demo sandbox populated with 50 customers, social networks, and event timelines! Refresh the page."
    except Exception as e:
        db.rollback()
        return False, f"Seeding failed: {e}"
    finally:
        db.close()

def render_data_ingestion():
    st.markdown("<style>div[data-testid='stButton'] { justify-content: flex-start !important; } .stApp h1, .stApp h2, .stApp h3, .stApp .centered-subheading { text-align: left !important; }</style>", unsafe_allow_html=True)
    st.markdown("<div style='font-size: 2rem; font-weight: 600; text-align: left; text-transform: uppercase; color: #EDEDED; padding-bottom: 8px;'>Data Ingestion & Integrations</div>", unsafe_allow_html=True)
    st.markdown("<p style='color:#94a3b8; text-align: left; margin-bottom: 20px;'>Upload datasets or connect directly to your data warehouse.</p>", unsafe_allow_html=True)
    
    tab_csv, tab_db = st.tabs(["CSV Upload", "PostgreSQL Connection"])
    
    with tab_csv:
        st.markdown("### Upload Customer Data")
        st.info("Upload **any** CSV file containing your customer records. The mapping tool below will help align your columns to our system fields.")
        
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
            label="Download Reference Template",
            data=csv_buffer.getvalue(),
            file_name="customer_data_reference.csv",
            mime="text/csv"
        )
        
        st.markdown("<hr>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
        
        if uploaded_file is not None:
            # Parse CSV headers
            try:
                sample_df = pd.read_csv(uploaded_file, nrows=5)
                csv_cols = list(sample_df.columns)
            except Exception as e:
                st.error(f"Failed to read CSV headers: {e}")
                st.stop()
                
            st.markdown("#### ⚓ Smart Column Alignment")
            st.markdown("<p style='color:#94a3b8; font-size:0.9rem;'>We have auto-detected matches from your CSV headers. Review or adjust them below.</p>", unsafe_allow_html=True)
            
            mappings = {}
            col_sel1, col_sel2 = st.columns(2)
            
            # Map core fields
            for i, (field_key, (field_label, is_required)) in enumerate(CORE_FIELDS.items()):
                default_match = find_matching_column(csv_cols, field_key)
                
                options = ["-- Ignore / Don't Import --"] if not is_required else ["-- Select Column --"]
                options = options + csv_cols
                
                default_idx = 0
                if default_match and default_match in csv_cols:
                    default_idx = options.index(default_match)
                
                label_text = f"{field_label} ({'Required' if is_required else 'Optional'})"
                
                with (col_sel1 if i % 2 == 0 else col_sel2):
                    selected_col = st.selectbox(
                        label_text,
                        options=options,
                        index=default_idx,
                        key=f"map_{field_key}"
                    )
                    if selected_col not in ("-- Ignore / Don't Import --", "-- Select Column --"):
                        mappings[field_key] = selected_col
            
            st.markdown("<br>", unsafe_allow_html=True)
            keep_unmapped = st.checkbox("Import unmapped columns as custom analytics features", value=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Ingest Data", type="primary"):
                # Validate required fields
                if "user_id" not in mappings:
                    st.error("Please map a CSV column to the required **User / Customer ID** field.")
                else:
                    with st.spinner("Processing mapping and uploading data..."):
                        try:
                            # Reset pointer and read full CSV
                            uploaded_file.seek(0)
                            full_df = pd.read_csv(uploaded_file)
                            
                            # Construct the renamed DataFrame
                            rename_dict = {v: k for k, v in mappings.items()}
                            
                            cols_to_keep = list(mappings.values())
                            if keep_unmapped:
                                # Keep all, rename mapped
                                full_df = full_df.rename(columns=rename_dict)
                            else:
                                # Filter to mapped only and rename
                                full_df = full_df[cols_to_keep].rename(columns=rename_dict)
                            
                            # Convert to CSV in memory
                            out_buffer = io.StringIO()
                            full_df.to_csv(out_buffer, index=False)
                            
                            token = st.session_state.get("token")
                            headers = {"Authorization": f"Bearer {token}"}
                            files = {"file": (uploaded_file.name, out_buffer.getvalue(), "text/csv")}
                            
                            resp = requests.post(f"{API_BASE}/api/v1/data/upload_csv", headers=headers, files=files)
                            if resp.status_code == 200:
                                data = resp.json()
                                st.success(f"🎉 Success! {data['message']}")
                            else:
                                st.error(f"Upload failed: {resp.json().get('detail', 'Unknown error')}")
                        except Exception as e:
                            st.error(f"Ingestion processing failed: {e}")

        # Quick Sandbox Seeding Button
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("### 🧪 Sandbox Seeding")
        st.markdown("<p style='color:#94a3b8; font-size:0.95rem;'>Don't have customer datasets ready? Populate your tenant sandbox with 50 mock users, event timelines, and referral networks to explore all dashboards instantly.</p>", unsafe_allow_html=True)
        if st.button("Load Mock Demo Data"):
            success, msg = seed_demo_data(st.session_state.get("tenant_id", 1))
            if success:
                st.success(msg)
            else:
                st.info(msg)

    with tab_db:
        st.markdown("### Connect to PostgreSQL")
        st.info("Securely connect Anchor to your data warehouse. We will dynamically pull customer records on demand.")
        
        with st.form("db_connection_form"):
            col1, col2 = st.columns(2)
            with col1:
                host = st.text_input("Host (e.g. localhost or 192.168.1.10)")
                port = st.text_input("Port", value="5432")
                db_name = st.text_input("Database Name")
            with col2:
                user = st.text_input("Username")
                password = st.text_input("Password", type="password", help="Database password")
                table_name = st.text_input("Table / View Name")
                
            submitted = st.form_submit_button("Save Connection Config", type="primary")
            
            if submitted:
                if host and db_name and table_name:
                    token = st.session_state.get("token")
                    headers = {"Authorization": f"Bearer {token}"}
                    payload = {
                        "db_type": "postgresql",
                        "host": host,
                        "port": port,
                        "user": user,
                        "password": password,
                        "db_name": db_name,
                        "table_name": table_name
                    }
                    try:
                        resp = requests.post(f"{API_BASE}/api/v1/data/integration/db", headers=headers, json=payload)
                        if resp.status_code == 200:
                            st.success("Database credentials saved securely!")
                        else:
                            st.error(f"Failed to save credentials: {resp.text}")
                    except Exception as e:
                        st.error(f"API Connection error: {e}")
                else:
                    st.warning("Please fill in all required fields.")
                    
        st.markdown("<hr>", unsafe_allow_html=True)
        if st.button("Sync Data Now"):
            with st.spinner("Connecting to database and processing data..."):
                token = st.session_state.get("token")
                headers = {"Authorization": f"Bearer {token}"}
                try:
                    resp = requests.post(f"{API_BASE}/api/v1/data/integration/db/sync", headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        st.success(f"Sync Complete! {data.get('message', '')}")
                    else:
                        st.error(f"Database sync failed: {resp.text}")
                except Exception as e:
                    st.error(f"Connection failed: {e}")
