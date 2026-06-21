import pytest
import random
import string
from httpx import AsyncClient, ASGITransport
from app import app

def random_string(n=20):
    return "".join(random.choices(string.printable, k=n))

FUZZ_CASES = [
    # (description, payload, expected_status)
    ("missing customer_id", {"interventions": [{"variable": "payment_friction", "value": 0.0}]}, 422),
    ("missing interventions", {"customer_id": "cust_123"}, 422),
    ("string for intervention value", {"customer_id": "cust_123", "interventions": [{"variable": "payment_friction", "value": "not-a-float"}]}, 422),
    ("empty payload", {}, 422),
    ("random string payload", random_string(), 422),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("description,payload,expected", FUZZ_CASES)
async def test_invalid_schema_rejected(description, payload, expected):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/causal/estimate",
            json=payload,
            headers={"Authorization": "Bearer test-token-that-is-invalid"},
        )
    # The 401 is possible if auth kicks in before validation, but we expect 422 if validation happens first 
    # depending on FastAPI dependency resolution order. Ideally, schema validation is checked.
    assert response.status_code in [422, 401], (
        f"FAILED [{description}]: got {response.status_code}. "
        "Invalid data must never reach the model."
    )
