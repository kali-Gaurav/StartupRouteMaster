import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("db_harmonize")

def harmonize_ids():
    source_db = 'backend/database/railway_data.db'
    target_db = 'backend/database/transit_graph.db'
    
    s_conn = sqlite3.connect(source_db)
    t_conn = sqlite3.connect(target_db)
    
    s_cur = s_conn.cursor()
    t_cur = t_conn.cursor()
    
    logger.info("Harmonizing Trip IDs with Train Numbers (v3)...")
    
    # 1. Fetch all unique trains from master
    s_cur.execute("SELECT DISTINCT train_no FROM trains_master")
    trains = s_cur.fetchall()
    
    # 2. Rebuild Trips Table
    t_cur.execute("DELETE FROM trips")
    
    trip_inserts = []
    for (t_no,) in trains:
        # Schema: (id, trip_id, route_id, service_id, headsign, direction_id, bike_allowed, wheelchair_accessible, trip_headsign)
        trip_inserts.append((int(t_no), str(t_no), 1, 'DAILY', '', 0, 0, 0, ''))
        
    t_cur.executemany("INSERT INTO trips VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", trip_inserts)
    logger.info(f"Inserted {len(trip_inserts)} consistent trips.")
    
    t_conn.commit()
    s_conn.close()
    t_conn.close()
    logger.info("ID Harmonization Complete.")

if __name__ == "__main__":
    harmonize_ids()
