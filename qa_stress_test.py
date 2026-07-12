import requests
import json
import time

API_BASE = 'http://localhost:8000/api/v1'
token = ''
tenant_id = 1

def login():
    global token, tenant_id
    try:
        r = requests.post(f'{API_BASE}/auth/login', data={'username': 'admin@retentioncore.com', 'password': 'admin123', 'client_id': '1'})
        if r.status_code == 200:
            token = r.json()['access_token']
            print('Login successful')
        else:
            print('Login failed:', r.text)
    except Exception as e:
        print('Login exception:', e)

login()

if token:
    headers = {'Authorization': f'Bearer {token}'}
    
    # 1. Data Avalanche
    print("\n--- 1. Data Avalanche ---")
    bad_csv = "customer_id,recency_days,frequency,monetary_value\n1,-9999,ABC,9999999999999.99\n"
    files = {'file': ('bad.csv', bad_csv, 'text/csv')}
    r = requests.post(f'{API_BASE}/data/upload_csv', headers=headers, files=files)
    print("Upload bad CSV:", r.status_code, r.text)
    
    # 2. Panicking Owner (Simulators)
    print("\n--- 2. Panicking Owner (Simulators) ---")
    payload = {
        "customer_id": "nonexistent_cust",
        "interventions": [{"variable": "payment_friction", "value": 0.0}]
    }
    r = requests.post(f'{API_BASE}/causal/estimate', headers=headers, json=payload)
    print("Causal Simulator invalid cust:", r.status_code, r.text[:200])

    r = requests.post(f'{API_BASE}/twin/simulate', headers=headers, json={"customer_id": "nonexistent_cust", "scenarios": ["price_increase"]})
    print("Twin Simulator invalid cust:", r.status_code, r.text)

    # 3. Desperate Marketer (A/B Factory)
    print("\n--- 3. Desperate Marketer (A/B Factory) ---")
    ab_payload = {
        "target_audience": "Loyalists",
        "base_prompt": "100% DISCOUNT EXTREME"
    }
    r = requests.post(f'{API_BASE}/ab/generate', headers=headers, json=ab_payload)
    print("Start extreme A/B generate:", r.status_code, r.text[:200])
    
    r = requests.post(f'{API_BASE}/ab/simulate_test', headers=headers, json={"variants": []})
    print("Start extreme A/B simulate (empty variants):", r.status_code, r.text[:200])

    # 4. Paranoid Admin (Compliance)
    print("\n--- 4. Paranoid Admin (Compliance) ---")
    r = requests.delete(f'{API_BASE}/compliance/erasure/nonexistent_cust', headers=headers)
    print("Erasure nonexistent cust:", r.status_code, r.text[:200])

else:
    print("Could not get token to run tests.")
