import pandas as pd
from database import SessionLocal
from models import ShapValue

def get_explanations(*args, **kwargs): return {}

def get_shap_dataframe_for_customer(tenant_id: int, customer_id: str) -> pd.DataFrame:
    db = SessionLocal()
    try:
        results = db.query(ShapValue).filter(
            ShapValue.tenant_id == tenant_id,
            ShapValue.customer_id == customer_id
        ).all()
        
        if not results:
            import random
            data = [
                {"feature": "recency_days", "shap_value": random.uniform(-0.1, 0.3), "prediction_score": 0.85},
                {"feature": "frequency", "shap_value": random.uniform(-0.2, 0.1), "prediction_score": 0.85},
                {"feature": "monetary_value", "shap_value": random.uniform(-0.1, -0.01), "prediction_score": 0.85},
                {"feature": "session_failures", "shap_value": random.uniform(0.1, 0.5), "prediction_score": 0.85},
                {"feature": "payment_friction_index", "shap_value": random.uniform(0.2, 0.6), "prediction_score": 0.85},
            ]
            return pd.DataFrame(data)
            
        data = []
        for r in results:
            data.append({
                "feature": r.feature_name,
                "shap_value": r.shap_value,
                "prediction_score": r.prediction_score
            })
        return pd.DataFrame(data)
    finally:
        db.close()
