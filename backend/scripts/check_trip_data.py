import sqlite3
import json

db_path = 'backend/database/transit_graph.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Find a trip that is in both trips table AND station_transit_index
print("--- Finding Overlap ---")
cur.execute("SELECT trip_id FROM trips LIMIT 10")
trips_in_table = [str(r[0]) for r in cur.fetchall()]

cur.execute("SELECT trains_map FROM station_transit_index LIMIT 1")
trains_map = json.loads(cur.fetchone()[0])
trips_in_index = [str(k) for k in trains_map.keys()]

overlap = set(trips_in_table).intersection(set(trips_in_index))
print("Overlapping Trip IDs:", list(overlap)[:5])

if overlap:
    target = list(overlap)[0]
    print(f"\n--- Checking Fares for Trip {target} ---")
    cur.execute("SELECT id FROM trips WHERE trip_id = ?", (target,))
    pk = cur.fetchone()[0]
    cur.execute("SELECT class_type, amount FROM fares WHERE trip_id = ?", (pk,))
    fares = cur.fetchall()
    for f in fares:
        print(f)
else:
    print("No overlap found between trips table and index. Database needs deep rebuild.")

conn.close()
