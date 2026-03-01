
import sqlite3
import os

db_path = 'backend/database/transit_graph.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check departures from NDLS
cursor.execute("SELECT departure_time, dest_station_id, trip_id FROM segments WHERE source_station_id='111' AND departure_time > '08:00:00' LIMIT 5")
print("Departures from NDLS:", cursor.fetchall())

# Check arrivals to BCT
cursor.execute("SELECT arrival_time, source_station_id, trip_id FROM segments WHERE dest_station_id='924' LIMIT 5")
print("Arrivals to BCT:", cursor.fetchall())

conn.close()
