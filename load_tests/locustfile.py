from locust import HttpUser, task, between
import random

class RetentionCoreUser(HttpUser):
    wait_time = between(0.5, 2.0)
    # Obtain a valid JWT in on_start
    token: str = ""

    def on_start(self):
        resp = self.client.post("/auth/token",
                                json={"api_key": "key-merchant-a-dev"})
        if resp.status_code == 200:
            self.token = resp.json()["access_token"]
        else:
            print("Failed to authenticate load test user")

    @task(5)
    def get_customer(self):
        if not self.token: return
        uid = f"U{random.randint(1, 1_000_000):07d}"
        self.client.get(
            f"/users/{uid}",
            headers={"Authorization": f"Bearer {self.token}"},
            name="/users/[user_id]",
        )

    @task(2)
    def dashboard_summary(self):
        if not self.token: return
        self.client.get(
            "/dashboard/summary",
            headers={"Authorization": f"Bearer {self.token}"},
        )

    @task(1)
    def trigger_winback(self):
        if not self.token: return
        self.client.post(
            "/campaigns/winback",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"targets": [{"user_id": f"U{random.randint(1,1000):07d}",
                               "telemetry": {"recency_days": 45, "frequency": 2,
                                             "monetary_value": 120}}
                              for _ in range(10)]},
        )
