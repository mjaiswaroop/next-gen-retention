import sqlite3
import os

db_path = "c:/Users/jaisw/OneDrive/Desktop/ml/retention_core.db"

if os.path.exists(db_path):
    print(f"Database {db_path} found. Attempting to add feature_schema column to tenant_configs...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE tenant_configs ADD COLUMN feature_schema JSON;")
        conn.commit()
        print("Successfully added feature_schema column.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("Column feature_schema already exists.")
        else:
            print(f"Error: {e}")
    finally:
        conn.close()
else:
    print(f"Database {db_path} not found.")
