import sqlite3
conn = sqlite3.connect('backend/database/transit_graph.db')
c = conn.cursor()

# Find trips that pass through BOTH ABR (927) and ADI (213)
# and ensure ABR comes before ADI
query = """
    SELECT st1.trip_id, t.trip_id as train_no
    FROM stop_times st1
    JOIN stop_times st2 ON st1.trip_id = st2.trip_id
    JOIN trips t ON st1.trip_id = t.id
    WHERE st1.stop_id = 927 AND st2.stop_id = 213
    AND st1.stop_sequence < st2.stop_sequence
    LIMIT 5
"""
c.execute(query)
res = c.fetchall()
print(f"Direct trips ABR -> ADI: {res}")

if res:
    trip_id = res[0][0]
    # Check service ID for this trip
    c.execute(f"SELECT service_id FROM trips WHERE id={trip_id}")
    print(f"Service ID for trip {trip_id}: {c.fetchone()[0]}")
    
    # Check if segments for this trip are in the 'segments' table
    c.execute(f"SELECT COUNT(*) FROM segments WHERE trip_id={trip_id}")
    print(f"Segments in table for trip {trip_id}: {c.fetchone()[0]}")

conn.close()
