import sqlite3
import os

db_path = 'backend/database/transit_graph.db'
if not os.path.exists(db_path):
    # Try another common location if it's not there
    db_path = 'transit_graph.db'

print(f"Connecting to {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

tables = ['agency', 'stops', 'gtfs_routes', 'calendar', 'calendar_dates', 'trips', 'stop_times', 'frequencies', 'transfers', 'route_shapes']

for table in tables:
    print(f"\n--- {table} ---")
    try:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        for col in columns:
            print(col)
    except Exception as e:
        print(f"Error reading table {table}: {e}")

conn.close()
