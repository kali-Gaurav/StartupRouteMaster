import sqlite3
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("fare_correction")

def sync_rich_data_properly():
    source_db = 'backend/database/railway_data.db'
    target_db = 'backend/database/transit_graph.db'
    
    s_conn = sqlite3.connect(source_db)
    t_conn = sqlite3.connect(target_db)
    
    s_cur = s_conn.cursor()
    t_cur = t_conn.cursor()
    
    # 1. Map Train No -> Internal Trip PK
    t_cur.execute("SELECT id, trip_id FROM trips")
    trip_map = {str(row[1]).strip(): row[0] for row in t_cur.fetchall()}
    logger.info(f"Loaded {len(trip_map)} trips.")

    # 2. Clear old corrupt fares
    t_cur.execute("DELETE FROM fares")
    
    # 3. Fetch from source: we want the MAX fare for a train-class pair 
    # (since source might have multiple segments, the direct PGT-KOTA fare is the total we need)
    logger.info("Fetching correct total fares from railway_data...")
    s_cur.execute("""
        SELECT train_no, class_code, total_fare 
        FROM train_fares 
        WHERE total_fare > 100
    """)
    source_fares = s_cur.fetchall()
    
    fares_to_insert = []
    for train_no, class_code, total_fare in source_fares:
        t_id = trip_map.get(str(train_no).strip())
        if t_id:
            # (segment_id, trip_id, class_type, amount)
            # We use NULL for segment_id to indicate it's a TRIP-level total
            fares_to_insert.append((None, t_id, class_code, float(total_fare)))

    logger.info(f"Inserting {len(fares_to_insert)} total-trip fare records...")
    t_cur.executemany("INSERT INTO fares (segment_id, trip_id, class_type, amount) VALUES (?, ?, ?, ?)", fares_to_insert)

    t_conn.commit()
    s_conn.close()
    t_conn.close()
    logger.info("Fare correction complete.")

if __name__ == "__main__":
    sync_rich_data_properly()
