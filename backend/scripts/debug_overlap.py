
import sqlite3
import os

db_path = 'backend/database/transit_graph.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Find any trip where both NDLS and MTJ appear as source stations
cursor.execute("SELECT trip_id, source_station_id FROM segments WHERE source_station_id='111'")
ndls_trips = {row[0] for row in cursor.fetchall()}

cursor.execute("SELECT trip_id, source_station_id FROM segments WHERE source_station_id='110'")
mtj_trips = {row[0] for row in cursor.fetchall()}

common_trips = ndls_trips.intersection(mtj_trips)
print("Common trip IDs:", common_trips)

if common_trips:
    trip_id = list(common_trips)[0]
    cursor.execute(f"SELECT source_station_id, dest_station_id, departure_time FROM segments WHERE trip_id={trip_id} ORDER BY departure_time")
    print(f"Sequence for trip {trip_id}:", cursor.fetchall())

conn.close()
