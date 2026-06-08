import sqlite3

def check_db(db_path):
    conn = sqlite3.connect(db_path)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f"\n--- Tables in {db_path} ---")
    for t in tables:
        name = t[0]
        count = conn.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        print(f"{name}: {count} rows")
    conn.close()

if __name__ == "__main__":
    check_db('backend/database/railway_data.db')
