
import sqlite3
import os

db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

for table in ["trips", "calendar", "calendar_dates"]:
    print(f"\nSchema for {table}:")
    cursor.execute(f"PRAGMA table_info({table})")
    for row in cursor.fetchall():
        print(row)

conn.close()
