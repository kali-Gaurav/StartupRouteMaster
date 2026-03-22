
import sqlite3
import json
db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

src_ids = [5533] # NDLS
dst_ids = [1778, 1779, 1780] # CSMT and nearby
target_date = "20260321" # Saturday

query = f"""
    SELECT 
        t.id as trip_id,
        t.trip_id as train_number,
        s1.stop_id as src_id,
        s2.stop_id as dst_id
    FROM stop_times s1
    JOIN stop_times s2 ON s1.trip_id = s2.trip_id
    JOIN trips t ON s1.trip_id = t.id
    JOIN calendar c ON t.service_id = c.service_id
    WHERE s1.stop_id IN ({','.join(map(str, src_ids))})
      AND s2.stop_id IN ({','.join(map(str, dst_ids))})
      AND s1.stop_sequence < s2.stop_sequence
      AND c.saturday = 1
      AND '{target_date}' BETWEEN c.start_date AND c.end_date
    LIMIT 10
"""

print(f"Executing: {query}")
cursor.execute(query)
rows = cursor.fetchall()
print(f"Results: {len(rows)}")
for r in rows:
    print(dict(r))

conn.close()
