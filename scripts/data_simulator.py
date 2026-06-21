import time
import random
import uuid
from pathlib import Path
import os
import sys

# Ensure we can import from the root directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings
from database import SessionLocal
from models import Customer

MERCHANTS = [1, 2] # Map to Merchant A and Merchant B in the DB

def generate_batch(merchant_id: int, size: int = 10) -> list:
    data = []
    for _ in range(size):
        user_id = f"sim_{str(uuid.uuid4())[:8]}"
        is_high_risk = random.random() < 0.1
        
        if is_high_risk:
            # Simulate a struggling user
            recency = random.uniform(15.0, 45.0)
            freq = random.randint(1, 5)
            monetary = random.uniform(5.0, 50.0)
            failures = random.randint(3, 10)
            friction = random.uniform(0.6, 1.0)
            tickets = random.randint(1, 3)
            churn_prob = random.uniform(0.70, 0.95)
        else:
            # Simulate a healthy user
            recency = random.uniform(1.0, 14.0)
            freq = random.randint(5, 50)
            monetary = random.uniform(50.0, 500.0)
            failures = random.randint(0, 1)
            friction = random.uniform(0.0, 0.3)
            tickets = 0
            churn_prob = random.uniform(0.05, 0.25)
            
        data.append(Customer(
            merchant_id=merchant_id,
            user_id=user_id,
            recency_days=recency,
            frequency=freq,
            monetary_value=monetary,
            session_failures=failures,
            payment_friction_index=friction,
            active_support_tickets=tickets,
            churn_probability=churn_prob,
            is_deleted=False
        ))
        
    return data

def stream_data():
    print(f"🚀 Starting Real-Time Data Simulator...")
    print(f"Writing to SQL Database")
    
    while True:
        db = SessionLocal()
        try:
            total_injected = 0
            for merchant_id in MERCHANTS:
                customers = generate_batch(merchant_id, size=random.randint(1, 5))
                db.add_all(customers)
                total_injected += len(customers)
                
            db.commit()
            print(f"[{time.strftime('%X')}] ⚡ INJECTED {total_injected} telemetry logs into SQL database.")
            time.sleep(3) # Stream new data every 3 seconds
        except KeyboardInterrupt:
            print("\n🛑 Simulator Offline.")
            break
        except Exception as e:
            print(f"Error: {e}")
            db.rollback()
            time.sleep(5)
        finally:
            db.close()

if __name__ == "__main__":
    stream_data()
