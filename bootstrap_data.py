import sqlite3
from data_pipeline import IngestionEngine

# First check if customers table exists in app_dev.db
conn = sqlite3.connect('app_dev.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables in app_dev.db:", tables)

if ('customers',) in tables:
    engine = IngestionEngine(source_uri="sqlite:///./app_dev.db")
    engine.ingest_table("customers", merchant_id=1)
else:
    # If not, let's just use Pandas to read the CSVs and dump them as parquet
    print("Customers table not found. Ingesting from CSVs directly...")
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    import os
    
    # Merchant 1
    df1 = pd.read_csv("customers_1.csv")
    df1['merchant_id'] = 1
    df1['is_deleted'] = False
    
    # PyArrow requires explicit types or handles them automatically, let's just write dataset
    table1 = pa.Table.from_pandas(df1)
    os.makedirs("data/merchant_id=1", exist_ok=True)
    pq.write_table(table1, "data/merchant_id=1/customers_buffer.parquet")
    print("Ingested Merchant 1 from CSV")

    # Merchant 2
    df2 = pd.read_csv("customers_2.csv")
    df2['merchant_id'] = 2
    df2['is_deleted'] = False
    table2 = pa.Table.from_pandas(df2)
    os.makedirs("data/merchant_id=2", exist_ok=True)
    pq.write_table(table2, "data/merchant_id=2/customers_buffer.parquet")
    print("Ingested Merchant 2 from CSV")
