
import sqlite3
import os

db_path = 'backend/database/transit_graph.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Find trips that pass through both NDLS (111) and BCT (924)
query = """
    SELECT trip_id FROM segments WHERE source_station_id='111'
    INTERSECT
    SELECT trip_id FROM segments WHERE dest_station_id='924'
"""
cursor.execute(query)
trips = cursor.fetchall()
print("Direct trips (by station id):", trips)

# If no direct trips by ID, check if they are part of the same trip but maybe different IDs?
# No, segments link stops in a trip.

conn.close()
