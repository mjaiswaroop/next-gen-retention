from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Customer

class CustomerRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_high_risk_customers(
        self,
        merchant_id: int,
        churn_threshold: float = 0.7,
        segment: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[dict]:
        query = self.db.query(Customer).filter(
            Customer.merchant_id == merchant_id,
            Customer.churn_probability >= churn_threshold,
            Customer.is_deleted == False
        )
        if segment:
            query = query.filter(Customer.segment == segment)
            
        customers = query.order_by(Customer.monetary_value.desc(), Customer.churn_probability.desc()).offset(offset).limit(limit).all()
        
        return [{
            "user_id": c.user_id,
            "churn_probability": c.churn_probability,
            "segment": c.segment,
            "recency_days": c.recency_days,
            "frequency": c.frequency,
            "monetary_value": c.monetary_value,
            "session_failures": c.session_failures,
            "payment_friction_index": c.payment_friction_index,
            "active_support_tickets": c.active_support_tickets
        } for c in customers]

    def get_churn_summary(self, merchant_id: int) -> dict:
        total = self.db.query(func.count(Customer.id)).filter(Customer.merchant_id == merchant_id, Customer.is_deleted == False).scalar() or 0
        avg_churn = self.db.query(func.avg(Customer.churn_probability)).filter(Customer.merchant_id == merchant_id, Customer.is_deleted == False).scalar() or 0.0
        high_risk = self.db.query(func.count(Customer.id)).filter(Customer.merchant_id == merchant_id, Customer.churn_probability > 0.7, Customer.is_deleted == False).scalar() or 0
        low_risk = self.db.query(func.count(Customer.id)).filter(Customer.merchant_id == merchant_id, Customer.churn_probability < 0.3, Customer.is_deleted == False).scalar() or 0

        return {
            "avg_churn": round(avg_churn, 4),
            "total_customers": total,
            "high_risk_count": high_risk,
            "low_risk_count": low_risk,
        }

    def get_all_for_merchant(self, merchant_id: int, limit: int = 1000) -> List[dict]:
        customers = self.db.query(Customer).filter(Customer.merchant_id == merchant_id, Customer.is_deleted == False).limit(limit).all()
        return [{
            "user_id": c.user_id,
            "churn_probability": c.churn_probability,
            "segment": c.segment,
            "recency_days": c.recency_days,
            "frequency": c.frequency,
            "monetary_value": c.monetary_value,
            "session_failures": c.session_failures,
            "payment_friction_index": c.payment_friction_index,
            "active_support_tickets": c.active_support_tickets
        } for c in customers]

    def get_by_user_id(self, merchant_id: int, user_id: str) -> Optional[dict]:
        c = self.db.query(Customer).filter(Customer.merchant_id == merchant_id, Customer.user_id == user_id, Customer.is_deleted == False).first()
        if not c:
            return None
        return {
            "user_id": c.user_id,
            "churn_probability": c.churn_probability,
            "segment": c.segment,
            "recency_days": c.recency_days,
            "frequency": c.frequency,
            "monetary_value": c.monetary_value,
            "session_failures": c.session_failures,
            "payment_friction_index": c.payment_friction_index,
            "active_support_tickets": c.active_support_tickets
        }

    def soft_delete(self, merchant_id: int, user_id: str) -> bool:
        c = self.db.query(Customer).filter(Customer.merchant_id == merchant_id, Customer.user_id == user_id).first()
        if c:
            c.is_deleted = True
            self.db.commit()
        return True

    def get_as_dataframe(self, merchant_id: int):
        import pandas as pd
        import json
        query = self.db.query(Customer).filter(Customer.merchant_id == merchant_id)
        df = pd.read_sql(query.statement, query.session.bind)
        
        # Unpack the dynamic extra_features JSON block into native DataFrame columns
        if not df.empty and 'extra_features' in df.columns:
            # Safely parse JSON if it's a string (SQLite often returns strings)
            def parse_json(x):
                if isinstance(x, str):
                    try: return json.loads(x)
                    except: return {}
                return x if isinstance(x, dict) else {}
                
            features_series = df['extra_features'].apply(parse_json)
            features_df = pd.json_normalize(features_series)
            
            # Merge back and drop the raw JSON column
            df = pd.concat([df.drop(columns=['extra_features']), features_df], axis=1)
            
        return df

    def bulk_upsert(self, merchant_id: int, records: List[dict]):
        for r in records:
            c = self.db.query(Customer).filter(Customer.merchant_id == merchant_id, Customer.user_id == r['user_id']).first()
            if c:
                if 'churn_probability' in r:
                    c.churn_probability = r['churn_probability']
                if 'segment' in r:
                    c.segment = r['segment']
        self.db.commit()

    def get_telemetry_snapshot(self, merchant_id: int, user_id: str) -> dict:
        return self.get_by_user_id(merchant_id, user_id) or {}

    def get_shap_explanation(self, merchant_id: int, user_id: str) -> list:
        from services.explainability_service import get_shap_dataframe_for_customer
        df = get_shap_dataframe_for_customer(merchant_id, user_id)
        if df.empty:
            return []
        # Return top 3 drivers
        top_drivers = df.sort_values(by="shap_value", key=abs, ascending=False).head(3)
        return top_drivers.to_dict(orient="records")
