import requests

try:
    resp = requests.get("http://localhost:8000/openapi.json")
    print("Status:", resp.status_code)
    print("Content keys:", resp.json().keys())
    print("Predict routes:", [path for path in resp.json().get("paths", {}).keys() if "predict" in path])
except Exception as e:
    print("Error:", e)
