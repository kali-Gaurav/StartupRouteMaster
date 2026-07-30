import sqlite3
import json
import logging
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hub_indexing")

def precompute_hub_index():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    logger.info("Identifying Major Hubs...")
    
    # 1. Hub Selection: Top 100 stations by number of unique trips
    cur.execute("""
        SELECT stop_id, COUNT(DISTINCT trip_id) as connectivity
        FROM stop_times
        GROUP BY stop_id
        ORDER BY connectivity DESC
        LIMIT 100
    """)
    hubs = [row[0] for row in cur.fetchall()]
    logger.info(f"Top 100 Hubs identified (First: {hubs[0]}, Last: {hubs[-1]})")

    # 2. Create Table
    cur.execute("DROP TABLE IF EXISTS hub_connectivity_index")
    cur.execute("""
        CREATE TABLE hub_connectivity_index (
            src_hub_id INTEGER,
            dst_hub_id INTEGER,
            trains_json TEXT,
            PRIMARY KEY (src_hub_id, dst_hub_id)
        )
    """)

    # 3. Pre-compute Hub-to-Hub connectivity
    logger.info("Pre-computing Hub-to-Hub direct paths...")
    
    # Get all stop_times for hubs only
    hub_placeholders = ",".join(map(str, hubs))
    cur.execute(f"""
        SELECT trip_id, stop_id, stop_sequence, departure_time, arrival_time 
        FROM stop_times 
        WHERE stop_id IN ({hub_placeholders})
        ORDER BY trip_id, stop_sequence
    """)
    hub_stops = cur.fetchall()
    
    # trip_id -> list of (hub_id, seq, dep, arr)
    trip_to_hubs = defaultdict(list)
    for tid, sid, seq, dep, arr in hub_stops:
        trip_to_hubs[tid].append((sid, seq, dep, arr))

    # hub_pair -> list of trains
    connectivity = defaultdict(list)
    
    for tid, path in trip_to_hubs.items():
        for i in range(len(path)):
            for j in range(i + 1, len(path)):
                src_h, src_seq, src_dep, _ = path[i]
                dst_h, dst_seq, _, dst_arr = path[j]
                
                # Direct train tid connects hub src_h to dst_h
                connectivity[(src_h, dst_h)].append({
                    "tid": tid,
                    "dep": src_dep,
                    "arr": dst_arr
                })

    # 4. Insert
    insert_data = []
    for (src, dst), trains in connectivity.items():
        insert_data.append((src, dst, json.dumps(trains)))

    logger.info(f"Inserting {len(insert_data)} hub-pair edges...")
    cur.executemany("INSERT INTO hub_connectivity_index VALUES (?, ?, ?)", insert_data)
    
    conn.commit()
    conn.close()
    logger.info("Hub Connectivity Index pre-computation complete.")

if __name__ == "__main__":
    precompute_hub_index()
