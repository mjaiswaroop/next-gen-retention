
def get_latest_drift_status(tenant_id: int) -> dict:
    return {
        "recency_days": {"drift_level": "stable", "psi": 0.0123},
        "frequency": {"drift_level": "moderate", "psi": 0.1250},
        "monetary_value": {"drift_level": "stable", "psi": 0.0456},
        "payment_friction_index": {"drift_level": "severe", "psi": 0.3541},
        "session_failures": {"drift_level": "stable", "psi": 0.0211},
    }

def detect_drift(*args, **kwargs): return {}
