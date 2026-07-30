import sqlite3
db_path = 'backend/database/transit_graph.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("SELECT COUNT(DISTINCT trip_id) FROM fares")
count = cur.fetchone()[0]
print(f"Total Unique Trips with Fares: {count}")

cur.execute("SELECT COUNT(*) FROM trips")
total_trips = cur.fetchone()[0]
print(f"Total Trips in DB: {total_trips}")

conn.close()
