import sqlite3
import sys
import os

def verify_fts():
    db_path = 'backend/database/transit_graph.db'
    if not os.path.exists(db_path):
        print("❌ DB not found")
        return
        
    conn = sqlite3.connect(db_path)
    try:
        print("🔎 Searching for 'Rajdhani' in FTS5...")
        res = conn.execute("SELECT * FROM trains_fts WHERE trains_fts MATCH 'Rajdhani' LIMIT 3").fetchall()
        print(f"Results: {res}")
        if res:
            print("🎉 SUCCESS: FTS5 Train search is functional.")
        else:
            print("⚠️ WARNING: FTS5 search returned 0 results. Check if data was populated.")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    verify_fts()
