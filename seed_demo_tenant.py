import sys
import uuid
import random
from datetime import datetime, timezone, timedelta
from database import SessionLocal
from models import (
    Merchant, Customer, CustomerPreferences, EventLog, 
    CustomerEdge, CampaignQueue, User, TenantConfig
)

def seed_latest_tenant():
    from database import active_tenant_id, engine, SessionLocal
    from sqlalchemy import text
    try:
        # Get the most recently created merchant using pure engine connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, name FROM merchants ORDER BY id DESC LIMIT 1")).fetchone()
        
        if not result:
            print("No merchant found! Please sign up first.")
            return

        tenant_id = result[0]
        merchant_name = result[1]
        active_tenant_id.set(tenant_id)
        db = SessionLocal()
        
        print(f"Seeding demo data for Tenant: {merchant_name} (ID: {tenant_id})")

        # 1. Create Customers
        customers = []
        for i in range(1, 51):
            user_id = f"cust_{i:03d}"
            # Hardcode cust_123 so the user's specific test works
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
                churn_probability=random.uniform(0, 1.0),
                segment=random.choice(["Enterprise", "Mid-Market", "SMB", "Prosumer"])
            )
            customers.append(c)
        db.add_all(customers)
        db.commit()
        print(f"Created {len(customers)} customers.")

        # 2. Graph Nodes & Edges
        # We need to manually add to GraphNode since it's a separate domain table in some architectures,
        # but wait, tab_graph queries /api/v1/graph/contagion-risk. Let's just create GraphEdge rows.
        # Actually, let's just make sure GraphEdges exist for the tenant.
        edges = []
        for i in range(20):
            source = random.choice(customers)
            target = random.choice(customers)
            if source != target:
                edges.append(CustomerEdge(
                    tenant_id=tenant_id,
                    source_customer_id=source.user_id,
                    target_customer_id=target.user_id,
                    edge_type="referral",
                    weight=random.uniform(0.5, 1.0)
                ))
        db.add_all(edges)
        db.commit()
        print("Created Contagion Graph Edges.")

        # 3. Create Event Logs for Emotion timeline
        logs = []
        for c in customers[:5]:
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
        print("Created Event Logs.")

        print("Demo data seeding complete! Refresh your dashboard.")

    finally:
        db.close()

if __name__ == "__main__":
    seed_latest_tenant()
