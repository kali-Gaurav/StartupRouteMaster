import sqlite3
import math
import random
import time

db_path = 'backend/database/transit_graph.db'

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2) * math.sin(dLat / 2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dLon / 2) * math.sin(dLon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def deep_test():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    errors = []

    print("🔍 [TEST 1/7] Connectivity Stress Test...")
    # Find stations with most connections (Hubs)
    cursor.execute("""
        SELECT s.code, count(seg.id) as conn_count 
        FROM stops s 
        JOIN segments seg ON s.id = seg.source_stop_id 
        GROUP BY s.id ORDER BY conn_count DESC LIMIT 10
    """)
    hubs = cursor.fetchall()
    print(f"Top Hubs identified: {hubs}")
    if not hubs: errors.append("No connectivity found in segments table.")

    print("🔍 [TEST 2/7] Path Mathematical Consistency...")
    # Check if sum of segments = total trip time/dist for a random sample of 100 trips
    cursor.execute("SELECT id FROM trips ORDER BY RANDOM() LIMIT 100")
    sample_trips = [r[0] for r in cursor.fetchall()]
    
    for tid in sample_trips:
        cursor.execute("SELECT SUM(distance_km), SUM(duration_minutes) FROM segments WHERE trip_id = ?", (tid,))
        seg_sum = cursor.fetchone()
        
        cursor.execute("SELECT arrival_time, departure_time FROM stop_times WHERE trip_id = ? ORDER BY stop_sequence", (tid,))
        st_times = cursor.fetchall()
        
        if len(st_times) < 2: continue
        
        # Calculate total duration from stop_times: Last Arrival - First Arrival
        # Because segments are now Current_Arrival - Prev_Arrival
        def to_min(t):
            h, m, s = map(int, t.split(':'))
            return h * 60 + m
            
        total_dur_st = to_min(st_times[-1][0]) - to_min(st_times[0][0])
        if total_dur_st < 0: total_dur_st += 1440 # rollover
        
        if abs(seg_sum[1] - total_dur_st) > 1: # 1 min tolerance for rounding
            errors.append(f"Trip {tid}: Segment duration sum ({seg_sum[1]}) != StopTimes duration ({total_dur_st})")

    print("🔍 [TEST 3/7] Geographical Cluster Sanity...")
    # Check if all stations in a cluster are actually within 10km of center
    cursor.execute("SELECT id, latitude, longitude FROM city_clusters ORDER BY RANDOM() LIMIT 20")
    sample_clusters = cursor.fetchall()
    for cid, clat, clon in sample_clusters:
        cursor.execute("""
            SELECT s.latitude, s.longitude FROM stops s 
            JOIN station_cluster_mapping scm ON s.id = scm.station_id 
            WHERE scm.cluster_id = ?
        """, (cid,))
        cluster_stops = cursor.fetchall()
        for slat, slon in cluster_stops:
            dist = haversine(clat, clon, slat, slon)
            if dist > 10: # 10km radius threshold for sanity
                errors.append(f"Cluster {cid}: Station too far from center ({dist:.2f}km)")

    print("🔍 [TEST 4/7] Transfer Logic Validation...")
    # Check if transfer distances match haversine
    cursor.execute("""
        SELECT t.from_stop_id, t.to_stop_id, t.dist_meters, 
               s1.latitude, s1.longitude, s2.latitude, s2.longitude 
        FROM transfers t
        JOIN stops s1 ON t.from_stop_id = s1.id
        JOIN stops s2 ON t.to_stop_id = s2.id
        ORDER BY RANDOM() LIMIT 50
    """)
    for fs, ts, d_m, lat1, lon1, lat2, lon2 in cursor.fetchall():
        calc_d = haversine(lat1, lon1, lat2, lon2) * 1000
        if abs(calc_d - d_m) > 10: # 10m tolerance
            errors.append(f"Transfer {fs}->{ts}: DB dist {d_m} != Calc dist {calc_d:.2f}")

    print("🔍 [TEST 5/7] Fare Slab Coverage...")
    # Check if we have slabs for all classes
    for cls in ['SL', '3A', '2A', '1A']:
        cursor.execute("SELECT count(*) FROM fare_slabs WHERE class_code = ?", (cls,))
        if cursor.fetchone()[0] == 0:
            errors.append(f"Missing fare slabs for class {cls}")

    print("🔍 [TEST 6/7] Index Performance Profiling...")
    # Run a complex query and measure time
    q = """
        SELECT count(*) FROM stop_times s1
        JOIN stop_times s2 ON s1.trip_id = s2.trip_id
        WHERE s1.stop_id = 500 AND s2.stop_id = 600
    """
    start = time.perf_counter()
    cursor.execute(q)
    end = time.perf_counter()
    lat = (end - start) * 1000
    print(f"Index query latency: {lat:.2f}ms")
    if lat > 50: errors.append(f"Slow index query performance: {lat:.2f}ms")

    print("🔍 [TEST 7/7] Search Index (FTS) Integrity...")
    # Test FTS for a random station name fragment
    cursor.execute("SELECT name FROM stops ORDER BY RANDOM() LIMIT 1")
    name = cursor.fetchone()[0]
    frag = name[:4]
    cursor.execute("SELECT count(*) FROM stops_fts WHERE name MATCH ?", (f"{frag}*",))
    if cursor.fetchone()[0] == 0:
        errors.append(f"FTS search failed to find station with fragment: {frag}")

    print("\n" + "="*30)
    if not errors:
        print("✅ ALL DEEP TESTS PASSED! Graph is bulletproof.")
    else:
        print(f"❌ FAILED with {len(errors)} errors:")
        for e in errors[:10]: print(f"  - {e}")
        if len(errors) > 10: print(f"  ... and {len(errors)-10} more.")
    print("="*30)

    conn.close()

if __name__ == "__main__":
    deep_test()
