import sqlite3
db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
try:
    row = conn.execute("SELECT * FROM trips WHERE id = 19019").fetchone()
    if row: print(dict(row))
    
    # Also check the route segments for this trip to see where it goes
    rows = conn.execute("""
        SELECT s.stop_id, st.code, st.name, s.departure_timestamp, s.arrival_timestamp
        FROM stop_times s
        JOIN stops st ON s.stop_id = st.id
        WHERE s.trip_id = 19019
        ORDER BY s.stop_sequence
    """).fetchall()
    for r in rows:
        print(f"{r['code']:>6} | {r['name']:<20} | Dep: {r['departure_timestamp']:>8} | Arr: {r['arrival_timestamp']:>8}")
finally:
    conn.close()
