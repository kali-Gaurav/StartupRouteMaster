
import sqlite3
import os

db_path = 'backend/database/transit_graph.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

query = """
    SELECT 
        s.trip_id, s.source_station_id, s.dest_station_id, 
        s.departure_time, s.arrival_time, s.arrival_day_offset, 
        s.duration_minutes, s.distance_km, s.cost,
        t.trip_id as train_number, r.long_name as train_name
    FROM segments s
    JOIN trips t ON s.trip_id = t.id
    JOIN gtfs_routes r ON t.route_id = r.id
    LIMIT 5
"""
cursor.execute(query)
rows = cursor.fetchall()
for row in rows:
    print(row)

conn.close()
