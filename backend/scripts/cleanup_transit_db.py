import sqlite3
import os

db_path = 'backend/database/transit_graph.db'
tables_to_remove = ['users', 'profiles', 'bookings', 'reviews', 'route_search_logs']

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        for table in tables_to_remove:
            print(f"Removing {table} from transit_graph.db...")
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
        print("Cleanup of transit_graph.db complete.")
    finally:
        conn.close()
else:
    print("transit_graph.db not found.")
