import sqlite3
import os

def check_db(db_path):
    print(f"\n--- Checking {db_path} ---")
    if not os.path.exists(db_path):
        print(f"File {db_path} does not exist.")
        return
    conn = sqlite3.connect(db_path)
    res = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    tables = [r[0] for r in res]
    print("Tables:", tables)
    
    for t in ['trips', 'stop_times', 'calendar', 'stops', 'hub_connectivity_index', 'station_transit_index_bin']:
        if t in tables:
            count = conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            print(f"{t} count: {count}")
    conn.close()

check_db('database/transit_graph.db')
check_db('database/local_transit.db')
