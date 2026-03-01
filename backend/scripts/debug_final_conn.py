
import sqlite3
import os

db_path = 'backend/database/transit_graph.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

query = """
    SELECT s1.trip_id, s1.departure_time, s2.arrival_time 
    FROM segments s1 
    JOIN segments s2 ON s1.trip_id = s2.trip_id 
    WHERE s1.source_station_id=111 AND s2.dest_station_id=110
"""
cursor.execute(query)
print("Any connectivity (regardless of time):", cursor.fetchall())

query_time = """
    SELECT s1.trip_id, s1.departure_time, s2.arrival_time 
    FROM segments s1 
    JOIN segments s2 ON s1.trip_id = s2.trip_id 
    WHERE s1.source_station_id=111 AND s2.dest_station_id=110 
    AND s2.departure_time > s1.departure_time
"""
cursor.execute(query_time)
print("Connectivity with correct order:", cursor.fetchall())

conn.close()
