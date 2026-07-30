import sqlite3
import os

db_path = "database/transit_graph.db"
if not os.path.exists(db_path):
    # Try alternate path relative to backend
    db_path = "backend/database/transit_graph.db" if "backend" not in os.getcwd() else "database/transit_graph.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("TABLE: stop_times")
cursor.execute("PRAGMA table_info(stop_times)")
for row in cursor.fetchall():
    print(row)

print("\nJOIN CHECK (trips + stop_times):")
cursor.execute("SELECT COUNT(*) FROM trips t JOIN stop_times st ON t.id = st.trip_id")
print(cursor.fetchone()[0])

# 5. Check Timestamps
res = conn.execute("SELECT MIN(departure_timestamp), MAX(departure_timestamp) FROM stop_times").fetchone()
print(f"DEBUG: Timestamp Range: {res[0]} to {res[1]}")

print("\nSTOP_TIMES COUNT:")
cursor.execute("SELECT COUNT(*) FROM stop_times")
print(cursor.fetchone()[0])

conn.close()
