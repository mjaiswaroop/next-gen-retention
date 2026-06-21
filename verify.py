import requests
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def run_verification():
    print("=== Manual Verification ===")
    
    # 1. Obtain token for Merchant A (ID: 1)
    print("\n[1] Obtaining token for Merchant A...")
    resp = client.post("/auth/token", json={"api_key": "key-merchant-a-dev"})
    assert resp.status_code == 200, f"Token fetch failed: {resp.text}"
    token_a = resp.json()["access_token"]
    print("    Token obtained successfully.")

    # 2. Obtain token for Merchant B (ID: 2)
    print("\n[2] Obtaining token for Merchant B...")
    resp = client.post("/auth/token", json={"api_key": "key-merchant-b-dev"})
    assert resp.status_code == 200, f"Token fetch failed: {resp.text}"
    token_b = resp.json()["access_token"]
    print("    Token obtained successfully.")

    # 3. Get Dashboard Summary
    print("\n[3] Fetching dashboard summary for Merchant A...")
    resp = client.get("/dashboard/summary", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200
    summary = resp.json()
    print(f"    Summary: {summary['total_customers']} total customers, {summary['avg_churn_probability']*100:.1f}% avg churn")

    # 4. Find a user belonging to Merchant B and try to access it via Merchant A
    # First, let's just use the isolation test knowledge. M1 has users, M2 has users.
    # The pipeline generated 500 users for each. We don't know the exact IDs because they are generated randomly.
    # Let's check isolation by getting a random ID from the DB or just assuming U00001 exists for M2 but if M1 tries to read it, what happens?
    # Wait, the pipeline uses random user_ids or sequential?
    # In `generate_raw_logs(n_users=500)`, it generates `U00001` to `U00500`. So both merchants have exactly the SAME user ids!
    # Let's verify they get different data for the same user ID!

    print("\n[4] Verifying cross-tenant isolation...")
    resp_a = client.get("/users/U00042", headers={"Authorization": f"Bearer {token_a}"})
    resp_b = client.get("/users/U00042", headers={"Authorization": f"Bearer {token_b}"})
    
    assert resp_a.status_code == 200, "M1 failed"
    assert resp_b.status_code == 200, "M2 failed"
    
    data_a = resp_a.json()
    data_b = resp_b.json()
    print(f"    Merchant A's U00042 Monetary Value: ${data_a['monetary_value']:.2f}")
    print(f"    Merchant B's U00042 Monetary Value: ${data_b['monetary_value']:.2f}")
    
    if data_a['monetary_value'] != data_b['monetary_value']:
        print("    [SUCCESS] Independent data for identical user IDs enforced by tenant_id.")
    else:
        print("    [WARNING] Note: Random generation yielded identical monetary values by chance (unlikely) or isolation failed.")

    # 5. Rate Limiting Test
    print("\n[5] Verifying rate limiting (200 requests/min)...")
    # Wait, in app.py the rate limit is only on `/users/{user_id}` not on dashboard_summary!
    # Let's hit `/users/U00042` 201 times
    success_count = 0
    blocked_count = 0
    for _ in range(205):
        resp = client.get("/users/U00042", headers={"Authorization": f"Bearer {token_a}"})
        if resp.status_code == 200:
            success_count += 1
        elif resp.status_code == 429:
            blocked_count += 1
            
    print(f"    Requests successful: {success_count}")
    print(f"    Requests blocked (429): {blocked_count}")
    if blocked_count > 0:
        print("    [SUCCESS] Rate limiting is working.")
    else:
        print("    [FAILED] Rate limiting did not block excess requests.")

if __name__ == "__main__":
    run_verification()
