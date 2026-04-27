
import sqlite3
import os

db_path = "c:/Users/Gaurav Nagar/OneDrive/Desktop/startupV2/backend/data/transit.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- Stops ---")
cursor.execute("SELECT id, code, name FROM stops WHERE code IN ('NDLS', 'ALJN')")
print(cursor.fetchall())

print("\n--- Trips ---")
cursor.execute("""
    SELECT t.id, t.trip_headsign 
    FROM trips t
    JOIN stop_times st1 ON t.id = st1.trip_id
    JOIN stops s1 ON st1.stop_id = s1.id
    JOIN stop_times st2 ON t.id = st2.trip_id
    JOIN stops s2 ON st2.stop_id = s2.id
    WHERE s1.code = 'NDLS' AND s2.code = 'ALJN' AND st1.stop_sequence < st2.stop_sequence
    LIMIT 5
""")
print(cursor.fetchall())
conn.close()
