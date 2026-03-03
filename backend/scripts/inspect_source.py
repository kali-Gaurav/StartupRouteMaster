import sqlite3
import os

def inspect_source():
    path = 'backend/database/railway_data.db'
    if not os.path.exists(path):
        print("❌ Source DB not found")
        return
        
    conn = sqlite3.connect(path)
    try:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(f"Source Tables: {[t[0] for t in tables]}")
        
        for table in [t[0] for t in tables]:
            cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
            print(f"  - {table}: {[c[1] for c in cols]}")
            
    finally:
        conn.close()

if __name__ == "__main__":
    inspect_source()
