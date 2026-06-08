import sqlite3

def check_db(path):
    print(f"Checking {path}...")
    try:
        conn = sqlite3.connect(path)
        res = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(f"Tables: {[r[0] for r in res]}")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_db('backend/database/user_store.db')
    check_db('backend/database/railway_data.db')
