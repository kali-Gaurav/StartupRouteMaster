import sqlite3
import os
import hashlib

def audit_gtfs_trips():
    db_path = "backend/database/transit_graph.db"
    if not os.path.exists(db_path):
        print("Database not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("--- TBR GTFS Structural Audit ---")
    
    # 1. Check max stops in a trip
    cursor.execute("SELECT trip_id, count(*) as c FROM stop_times GROUP BY trip_id ORDER BY c DESC LIMIT 1")
    row = cursor.fetchone()
    print(f"Max stops in a single trip: {row[1]} (Trip ID: {row[0]})")
    
    # 2. Audit Monotonicity of stop_sequence
    cursor.execute("""
        SELECT trip_id
        FROM stop_times
        GROUP BY trip_id
        HAVING max(stop_sequence) - min(stop_sequence) + 1 != count(*)
    """)
    gaps = cursor.fetchall()
    print(f"Trips with non-contiguous stop_sequences (gaps): {len(gaps)}")
    
    # 3. Pattern Hashing (Compressing identical physical routes)
    print("\n--- Pattern Hashing Feasibility ---")
    cursor.execute("""
        SELECT trip_id, group_concat(stop_id, ',') as path
        FROM (SELECT * FROM stop_times ORDER BY trip_id, stop_sequence)
        GROUP BY trip_id
    """)
    trips = cursor.fetchall()
    print(f"Total Unique Trips: {len(trips)}")
    
    patterns = {}
    for tid, path in trips:
        pid = hashlib.md5(path.encode()).hexdigest()[:12]
        if pid not in patterns:
            patterns[pid] = []
        patterns[pid].append(tid)
        
    print(f"Unique Physical Patterns (Paths): {len(patterns)}")
    
    # Analyze compression ratio
    compression = len(trips) / len(patterns)
    print(f"Pattern Compression Ratio: {compression:.2f}x (We can group {compression:.1f} trips into 1 pattern on average)")
    
    conn.close()

if __name__ == "__main__":
    audit_gtfs_trips()
