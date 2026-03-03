import sqlite3
import os

dbs = ['backend/database/railway_data.db', 'backend/database/transit_graph.db']

for db_path in dbs:
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        continue
        
    print(f"Analysis for {db_path}")
    conn = sqlite3.connect(db_path)
    try:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        for table in tables:
            t_name = table[0]
            print(f"Table: {t_name}")
            columns = conn.execute(f"PRAGMA table_info({t_name})").fetchall()
            for col in columns:
                print(f"  {col[1]} ({col[2]})")
    finally:
        conn.close()
