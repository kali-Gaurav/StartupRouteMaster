
import sqlite3
import os

db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print(f"📁 Database: {db_path}")

# Check columns for trips
cursor.execute("PRAGMA table_info(trips)")
cols = [r[1] for r in cursor.fetchall()]
print(f"Columns in 'trips': {cols}")

# Check columns for calendar
cursor.execute("PRAGMA table_info(calendar)")
cols = [r[1] for r in cursor.fetchall()]
print(f"Columns in 'calendar': {cols}")
