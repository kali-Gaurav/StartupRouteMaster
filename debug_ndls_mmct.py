
import sqlite3
db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# NDLS = 5533, MMCT = 5080
# Saturday, 2026-03-21
query = """
    SELECT 
        t.trip_id,
        s1.departure_time,
        s2.arrival_time,
        c.saturday,
        c.start_date,
        c.end_date
    FROM stop_times s1
    JOIN stop_times s2 ON s1.trip_id = s2.trip_id
    JOIN trips t ON s1.trip_id = t.id
    JOIN calendar c ON t.service_id = c.service_id
    WHERE s1.stop_id = 5533
      AND s2.stop_id = 5080
      AND s1.stop_sequence < s2.stop_sequence
      AND c.saturday = 1
      AND '20260321' BETWEEN c.start_date AND c.end_date
"""
cursor.execute(query)
rows = cursor.fetchall()
print(f"Direct trains NDLS -> MMCT on 2026-03-21: {len(rows)}")
for r in rows[:5]:
    print(r)

conn.close()
