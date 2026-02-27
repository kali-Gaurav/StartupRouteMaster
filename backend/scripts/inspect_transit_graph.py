import sqlite3
import os

db_path = "backend/database/transit_graph.db"
if not os.path.exists(db_path):
    print("DB not found")
else:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in c.fetchall()]
    print("Tables:", tables)
    for table in tables:
        c.execute(f"SELECT COUNT(*) FROM {table}")
        print(f" - {table}: {c.fetchone()[0]}")
    conn.close()
