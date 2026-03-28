import sqlite3
import os

dbs = ['database/transit_graph.db', 'database/railway_data.db', 'database/user_store.db']

for db_path in dbs:
    print(f"--- Checking {db_path} ---")
    if not os.path.exists(db_path):
        print("  File not found.")
        continue
    try:
        conn = sqlite3.connect(db_path)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print(f"  Tables: {tables}")
        
        if 'stops' in tables:
            stops = conn.execute("SELECT count(*) FROM stops WHERE code='NDLS'").fetchone()[0]
            print(f"  NDLS in stops: {stops}")
            
        if 'station_transit_index_bin' in tables:
            rows = conn.execute("SELECT count(*) FROM station_transit_index_bin").fetchone()[0]
            print(f"  Binary Index Rows: {rows}")
        
        conn.close()
    except Exception as e:
        print(f"  Error: {e}")
