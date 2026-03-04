import sqlite3
import os

db_path = 'backend/database/transit_graph.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Find a trip passing through NDLS
c.execute("""
    SELECT t.id, t.trip_id, st.stop_sequence, s.code, s.name, s.latitude, s.longitude
    FROM trips t
    JOIN stop_times st ON t.id = st.trip_id
    JOIN stops s ON st.stop_id = s.id
    WHERE s.code = 'NDLS'
    LIMIT 20
""")
results = c.fetchall()
print("Trips through NDLS:")
for r in results:
    print(r)

if results:
    trip_id = results[0][0]
    print(f"\nAll stops for trip_id {trip_id}:")
    c.execute("""
        SELECT st.stop_sequence, s.code, s.name, s.latitude, s.longitude
        FROM stop_times st
        JOIN stops s ON st.stop_id = s.id
        WHERE st.trip_id = ?
        ORDER BY st.stop_sequence
    """, (trip_id,))
    for r in c.fetchall():
        print(r)

conn.close()
