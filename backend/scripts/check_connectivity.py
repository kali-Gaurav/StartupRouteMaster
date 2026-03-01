import sqlite3
import os

db_path = "database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check NDLS and BCT
cursor.execute("SELECT id, code, name FROM stops WHERE code IN ('NDLS', 'BCT', 'CNB', 'CSMT', 'PNVL')")
stops = cursor.fetchall()
print(f"Stops: {stops}")

# Check trips between NDLS and CNB
cursor.execute("""
    SELECT COUNT(*) 
    FROM segments seg
    JOIN stops s1 ON CAST(seg.source_station_id AS INTEGER) = s1.id
    JOIN stops s2 ON CAST(seg.dest_station_id AS INTEGER) = s2.id
    WHERE s1.code = 'NDLS' AND s2.code = 'CNB'
""")
count = cursor.fetchone()[0]
print(f"Direct segments NDLS -> CNB: {count}")

# Check any path NDLS to BCT
cursor.execute("""
    SELECT t.trip_id, s1.code, s2.code
    FROM segments seg
    JOIN stops s1 ON CAST(seg.source_station_id AS INTEGER) = s1.id
    JOIN stops s2 ON CAST(seg.dest_station_id AS INTEGER) = s2.id
    JOIN trips t ON seg.trip_id = t.id
    WHERE s1.code = 'NDLS'
    LIMIT 5
""")
print(f"NDLS Departures: {cursor.fetchall()}")

conn.close()
