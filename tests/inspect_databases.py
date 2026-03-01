import sqlite3
import os

databases = [
    'backend/database/railway_data.db',
    'backend/database/transit_graph.db',
    'railway_manager.db',
    'backend/railway_manager.db',
    'routemaster.db',
    'routemaster_agent.db',
    'backend/routemaster.db'
]

for db in databases:
    if os.path.exists(db):
        print(f"\n--- Database: {db} ---")
        try:
            conn = sqlite3.connect(db)
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            print(f"Tables: {[t[0] for t in tables]}")
            for table_tuple in tables:
                table = table_tuple[0]
                count = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                print(f"  {table}: {count} rows")
            conn.close()
        except Exception as e:
            print(f"Error accessing {db}: {e}")
    else:
        print(f"\n--- Database: {db} (NOT FOUND) ---")
