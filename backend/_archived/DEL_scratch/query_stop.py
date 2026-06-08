import sqlite3
import os

db_paths = ["backend/railway.db", "backend/railway_data.db"]

for db_path in db_paths:
    print(f"--- Checking {db_path} ---")
    if not os.path.exists(db_path):
        print("Does not exist")
        continue
    conn = sqlite3.connect(db_path)
    try:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(f"Tables: {[t[0] for t in tables]}")
        if any(t[0] == 'stops' for t in tables):
            row = conn.execute("SELECT * FROM stops WHERE id = 125").fetchone()
            if row:
                print(f"Stop 125: {row}")
            else:
                print("Stop 125 not found")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
