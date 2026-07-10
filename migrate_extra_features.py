import sqlite3
import os

db_path = "c:/Users/jaisw/OneDrive/Desktop/ml/retention_core.db"

if os.path.exists(db_path):
    print(f"Database {db_path} found. Attempting to add extra_features column...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE customers ADD COLUMN extra_features JSON;")
        conn.commit()
        print("Successfully added extra_features column.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("Column extra_features already exists.")
        else:
            print(f"Error: {e}")
    finally:
        conn.close()
else:
    print(f"Database {db_path} not found.")
