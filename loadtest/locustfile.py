import os
import uuid
from datetime import datetime, timezone

from locust import HttpUser, between, task


class MfsApiUser(HttpUser):
    wait_time = between(0.05, 0.2)

    def on_start(self):
        self.api_key = os.environ.get("MFS_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("MFS_API_KEY is required")
        self.headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def transaction(self, risky=False):
        identifier = uuid.uuid4()
        return {
            "event_id": str(identifier), "transaction_id": f"LOAD-{identifier}",
            "customer_id": f"CUS-{identifier.int % 10000:04d}",
            "merchant_id": f"MER-{identifier.int % 200:03d}",
            "amount": 95000 if risky else 1250, "historical_average_amount": 1800,
            "occurred_at": datetime.now(timezone.utc).isoformat(), "status": "SUCCESS",
            "source": "synthetic-load-test", "device_changed": risky, "location_changed": risky,
            "transactions_last_10_min": 18 if risky else 2, "new_beneficiaries": 5 if risky else 0,
        }

    @task(7)
    def ingest(self):
        with self.client.post("/api/v1/mfs/transactions/ingest/", json=self.transaction(), headers=self.headers,
                              name="POST /transactions/ingest", catch_response=True) as response:
            if response.status_code != 202:
                response.failure(f"expected 202, got {response.status_code}: {response.text[:120]}")

    @task(2)
    def synchronous_low_risk_prediction(self):
        with self.client.post("/api/v1/risk/predict/", json=self.transaction(), headers=self.headers,
                              name="POST /risk/predict low", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"expected 200, got {response.status_code}: {response.text[:120]}")

    @task(1)
    def synchronous_high_risk_prediction(self):
        with self.client.post("/api/v1/risk/predict/", json=self.transaction(risky=True), headers=self.headers,
                              name="POST /risk/predict high", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"expected 200, got {response.status_code}: {response.text[:120]}")
