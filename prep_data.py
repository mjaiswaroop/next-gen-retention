import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import os
import sqlite3

# 1. Download Telco Churn Data
url = "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv"
print("Downloading real dataset...")
df = pd.read_csv(url)

# 2. Map to Retention Core Schema
df['TotalCharges'] = pd.to_numeric(df['TotalCharges'].replace(' ', np.nan))
df.dropna(inplace=True)

new_df = pd.DataFrame()
new_df['user_id'] = df['customerID']
new_df['merchant_id'] = 1

np.random.seed(42)
new_df['recency_days'] = np.where(df['Churn'] == 'Yes', 
                                  np.random.randint(30, 90, len(df)), 
                                  np.random.randint(1, 30, len(df)))

new_df['frequency'] = df['tenure'] * np.random.randint(2, 5, len(df))
new_df['monetary_value'] = df['MonthlyCharges']

base_failures = np.random.randint(0, 3, len(df))
tech_support_penalty = np.where(df['TechSupport'] == 'No', np.random.randint(2, 5, len(df)), 0)
churn_penalty = np.where(df['Churn'] == 'Yes', np.random.randint(3, 8, len(df)), 0)
new_df['session_failures'] = base_failures + tech_support_penalty + churn_penalty

friction_base = np.random.uniform(0.1, 0.4, len(df))
payment_penalty = np.where(df['PaymentMethod'] == 'Electronic check', np.random.uniform(0.3, 0.5, len(df)), 0)
new_df['payment_friction_index'] = np.clip(friction_base + payment_penalty, 0, 1)

new_df['active_support_tickets'] = np.where(df['TechSupport'] == 'Yes', np.random.randint(1, 3, len(df)), 0)

new_df['is_deleted'] = np.where((df['Churn'] == 'Yes') & (np.random.rand(len(df)) < 0.5), True, False)
new_df['churned'] = np.where(df['Churn'] == 'Yes', 1, 0)
# we also need segment to be seeded if the app expects it, but train_models.py computes it!

new_df.to_csv("customers_1.csv", index=False)
print(f"Saved {len(new_df)} real customer records to customers_1.csv")

os.makedirs("data/merchant_id=1", exist_ok=True)
table1 = pa.Table.from_pandas(new_df)
pq.write_table(table1, "data/merchant_id=1/customers_buffer.parquet")

# 3. Seed SQLite Database
from database import SessionLocal
from models import Customer

db = SessionLocal()
try:
    records = new_df.to_dict('records')
    # Filter only expected fields
    expected_fields = ["user_id", "merchant_id", "recency_days", "frequency", "monetary_value", 
                       "session_failures", "payment_friction_index", "active_support_tickets", "is_deleted"]
    
    clean_records = []
    for r in records:
        clean_records.append({k: v for k, v in r.items() if k in expected_fields})
        
    db.query(Customer).filter_by(merchant_id=1).delete()
    db.bulk_insert_mappings(Customer, clean_records)
    db.commit()
    print(f"Successfully seeded {len(clean_records)} customers into SQLite database!")
except Exception as e:
    db.rollback()
    print(f"DB Insert Failed: {e}")
finally:
    db.close()

print("Data prep complete!")
