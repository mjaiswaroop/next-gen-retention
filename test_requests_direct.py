import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

import requests
from auth import create_user_token

if __name__ == "__main__":
    token = create_user_token("admin@example.com", 1, "SUPER_ADMIN")
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get("http://localhost:8000/api/v1/predict/metrics", headers=headers)
        print("Status:", response.status_code)
        print("Response text:", response.text)
    except Exception as e:
        print("Error:", e)
