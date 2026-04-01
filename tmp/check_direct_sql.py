import sqlite3
import os

db_path = 'database/transit_graph.db'
if not os.path.exists(db_path):
    db_path = '../database/transit_graph.db'
    
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# Direct NDLS -> MMCT
query = """
    SELECT t.id, t.trip_id, s1.code as code1, s2.code as code2
    FROM trips t
    JOIN stop_times st1 ON t.id = st1.trip_id
    JOIN stop_times st2 ON t.id = st2.trip_id
    JOIN stops s1 ON st1.stop_id = s1.id
    JOIN stops s2 ON st2.stop_id = s2.id
    WHERE s1.code = 'NDLS' AND s2.code = 'MMCT'
    AND st1.stop_sequence < st2.stop_sequence
"""
rows = conn.execute(query).fetchall()
print(f"Direct trips NDLS -> MMCT: {len(rows)}")
for r in rows[:10]:
    print(f"ID: {r['id']}, TripNo: {r['trip_id']}")

conn.close()
