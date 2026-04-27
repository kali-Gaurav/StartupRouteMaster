
import sqlite3
import os

db_path = "backend/database/transit_graph.db"
if not os.path.exists(db_path):
    print(f"File not found: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Schema for stop_times:")
cursor.execute("PRAGMA table_info(stop_times)")
for row in cursor.fetchall():
    print(row)

print("\nSchema for stops:")
cursor.execute("PRAGMA table_info(stops)")
for row in cursor.fetchall():
    print(row)

conn.close()
