import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from fastapi.testclient import TestClient
from app import app
from auth import create_user_token

if __name__ == "__main__":
    client = TestClient(app)
    token = create_user_token("admin@example.com", 1, "SUPER_ADMIN")

    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/predict/metrics", headers=headers)
    print("Status:", response.status_code)
    print("Response:", response.json())
