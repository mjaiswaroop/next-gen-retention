import logging

logger = logging.getLogger("retention_core.clv_estimator")

class CLVEstimator:
    def __init__(self, db_session):
        self.db = db_session

    def estimate(self, merchant_id: int, customer_id: str) -> float:
        """
        Mock CLV estimation.
        In reality, this would query historical transactions and predict future value.
        For now, we just fetch the customer's current monetary_value and multiply by an expected lifetime multiplier.
        """
        try:
            from models import Customer
            customer = self.db.query(Customer).filter_by(
                merchant_id=merchant_id, user_id=customer_id
            ).first()
            if customer and customer.monetary_value:
                return float(customer.monetary_value) * 1.5
        except Exception:
            pass
        return 1000.0  # Fallback
