import sqlite3
import math
import logging
import json
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("precompute_transfers_v2")

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.sin(phi2) * math.cos(dlambda / 2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def precompute_transfers():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    logger.info("Starting Intelligent Transfer Pre-computation...")
    cur.execute("DROP TABLE IF EXISTS transfers")
    cur.execute("""
        CREATE TABLE transfers (
            from_stop_id INTEGER,
            to_stop_id INTEGER,
            min_transfer_time INTEGER,
            dist_meters FLOAT,
            PRIMARY KEY (from_stop_id, to_stop_id)
        )
    """)

    # 1. Fetch data
    cur.execute("SELECT id, code, latitude, longitude, is_major_junction FROM stops")
    stops = cur.fetchall()
    stop_map = {row[1]: row[0] for row in stops} # code -> id
    
    # 2. Fetch Clusters
    cur.execute("SELECT station_codes_json FROM city_clusters")
    clusters = [json.loads(row[0]) for row in cur.fetchall()]
    
    transfer_data = []
    
    # 3. Add Cluster-based Transfers (Automatic within city)
    logger.info("Adding cluster-based transfers...")
    for cluster in clusters:
        for c1 in cluster:
            for c2 in cluster:
                if c1 in stop_map and c2 in stop_map:
                    # 45 min buffer for city-wide transfer
                    transfer_data.append((stop_map[c1], stop_map[c2], 45, 0.0))

    # 4. Add Distance-based Transfers (5km limit)
    logger.info("Adding distance-based transfers (5km)...")
    for i in range(len(stops)):
        s1_id, s1_code, s1_lat, s1_lon, s1_hub = stops[i]
        
        # Self-transfer
        self_time = 30 if s1_hub else 15
        transfer_data.append((s1_id, s1_id, self_time, 0.0))
        
        for j in range(i + 1, len(stops)):
            s2_id, s2_code, s2_lat, s2_lon, s2_hub = stops[j]
            if abs(s1_lat - s2_lat) < 0.1 and abs(s1_lon - s2_lon) < 0.1:
                dist = haversine(s1_lat, s1_lon, s2_lat, s2_lon)
                if dist < 5000:
                    walk_time = int(dist / 60) + 20 
                    transfer_data.append((s1_id, s2_id, walk_time, dist))
                    transfer_data.append((s2_id, s1_id, walk_time, dist))

    # 5. Insert
    logger.info(f"Inserting {len(transfer_data)} intelligent transfers...")
    cur.executemany("INSERT OR IGNORE INTO transfers VALUES (?, ?, ?, ?)", transfer_data)
    
    conn.commit()
    conn.close()
    logger.info("Transfer pre-computation complete.")

if __name__ == "__main__":
    precompute_transfers()
