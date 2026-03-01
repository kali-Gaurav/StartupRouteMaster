
import sqlite3
import os

db_path = 'backend/database/transit_graph.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Find trips containing BOTH NDLS (111) and MTJ (110)
query = """
    SELECT trip_id FROM segments WHERE source_station_id=111
    INTERSECT
    SELECT trip_id FROM segments WHERE dest_station_id=110
"""
cursor.execute(query)
trips = cursor.fetchall()
print("Common trip IDs (Intersection):", trips)

conn.close()
