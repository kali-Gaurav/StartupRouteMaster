import sqlite3
import os

db_path = 'backend/database/transit_graph.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

tables = ['agency', 'stops', 'gtfs_routes', 'calendar', 'calendar_dates', 'trips', 'stop_times', 'frequencies', 'transfers', 'route_shapes']

for table in tables:
    try:
        cursor.execute(f"SELECT count(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"{table}: {count} rows")
    except Exception as e:
        print(f"Error reading {table}: {e}")

conn.close()
