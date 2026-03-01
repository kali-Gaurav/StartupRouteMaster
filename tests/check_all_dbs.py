import sqlite3
import os

db_files = ['railway_manager.db', 'backend/railway_manager.db', 'backend/database/railway_data.db']

for db_file in db_files:
    if os.path.exists(db_file):
        print(f"\nChecking {db_file}...")
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trips'")
            if cursor.fetchone():
                cursor.execute("SELECT id, trip_id FROM trips")
                trips = cursor.fetchall()
                print(f"Trips: {trips}")
            else:
                print("Table 'trips' not found.")
            conn.close()
        except Exception as e:
            print(f"Error: {e}")
    else:
        print(f"\n{db_file} does not exist.")
