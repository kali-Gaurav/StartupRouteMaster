
import sqlite3
from datetime import datetime
db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Test Date: 2026-03-21 (Saturday)
weekday = "saturday"
db_date = "20260321"

print(f"--- Trip Analysis for {db_date} ({weekday}) ---")
query = f"""
    SELECT count(*) 
    FROM trips t
    JOIN calendar c ON t.service_id = c.service_id
    WHERE c.{weekday} = 1 AND '{db_date}' BETWEEN c.start_date AND c.end_date
"""
cursor.execute(query)
print(f"Active trips on date: {cursor.fetchone()[0]}")

print("\n--- Stop Times Sample for active trips ---")
query_sample = f"""
    SELECT s.trip_id, s.stop_id, s.departure_time, s.departure_timestamp
    FROM stop_times s
    JOIN trips t ON s.trip_id = t.id
    JOIN calendar c ON t.service_id = c.service_id
    WHERE c.{weekday} = 1 AND '{db_date}' BETWEEN c.start_date AND c.end_date
    LIMIT 5
"""
cursor.execute(query_sample)
for row in cursor.fetchall(): print(row)

conn.close()
