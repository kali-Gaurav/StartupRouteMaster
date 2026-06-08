import sqlite3
import os

db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
try:
    count = conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
    print(f"Total trips: {count}")
    
    # Check stops for BCT and NDLS
    src = conn.execute("SELECT id, code, name FROM stops WHERE code = 'BCT'").fetchall()
    dst = conn.execute("SELECT id, code, name FROM stops WHERE code = 'NDLS'").fetchall()
    print(f"Source (BCT): {list(map(dict, src)) if src else 'Not found'}")
    print(f"Dest (NDLS): {list(map(dict, dst)) if dst else 'Not found'}")
    
    # Check if there are any trips between them on a specific day
    # Monday is 0
    day_idx = 0
    day_col = "monday"
    q = f"""
        SELECT COUNT(*)
        FROM stop_times s1
        JOIN stop_times s2 ON s1.trip_id = s2.trip_id
        JOIN trips t ON s1.trip_id = t.id
        JOIN calendar c ON t.service_id = c.service_id
        WHERE s1.stop_id IN (SELECT id FROM stops WHERE code = 'BCT')
          AND s2.stop_id IN (SELECT id FROM stops WHERE code = 'NDLS')
          AND s1.stop_sequence < s2.stop_sequence
          AND c.{day_col} = 1
    """
    direct_count = conn.execute(q).fetchone()[0]
    print(f"Direct trips (BCT->NDLS) on Monday: {direct_count}")
finally:
    conn.close()
