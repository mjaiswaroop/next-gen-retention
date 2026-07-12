import requests
import json

base_url = "http://localhost:8000"

if __name__ == "__main__":
    try:
        resp = requests.post(f"{base_url}/api/v1/auth/login", data={"username":"admin@example.com", "password":"password", "client_id":"1"})
        token = resp.json().get("access_token")
        if not token:
            print("Login failed:", resp.json())
            exit(1)
            
        headers = {"Authorization": f"Bearer {token}"}
        resp2 = requests.get(f"{base_url}/api/v1/predict/metrics", headers=headers)
        print("Metrics Status:", resp2.status_code)
        print("Metrics Response:", resp2.text)
    except Exception as e:
        print("Error:", e)
