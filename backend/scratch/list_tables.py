
import sqlite3
import os

db_files = [
    "database/user_store.db",
    "database/transit_graph.db"
]

for db_file in db_files:
    if os.path.exists(db_file):
        print(f"\n--- Tables in {db_file} ---")
        conn = sqlite3.connect(db_file)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cur.fetchall()
        for table in tables:
            print(table[0])
        conn.close()
    else:
        print(f"\n--- {db_file} does not exist ---")
