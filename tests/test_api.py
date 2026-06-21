import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app
from database import SessionLocal
from models import Merchant
from auth import create_access_token

client = TestClient(app)

@pytest.fixture(scope="module")
def setup_test_merchant():
    """Ensure a test merchant exists in the SQLite database."""
    db = SessionLocal()
    merchant = db.query(Merchant).filter_by(name="Test Merchant").first()
    if not merchant:
        merchant = Merchant(name="Test Merchant", is_active=True, api_key="dummy")
        db.add(merchant)
        db.commit()
        db.refresh(merchant)
    
    yield merchant
    
    db.delete(merchant)
    db.commit()
    db.close()

def test_unauthorized_access():
    response = client.get("/api/v1/users/high-risk")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}

def test_get_high_risk_users(setup_test_merchant):
    # Get a JWT programmatically
    token = create_access_token(setup_test_merchant.id)
    
    # Access protected route
    response = client.get("/api/v1/users/high-risk?limit=5", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)
