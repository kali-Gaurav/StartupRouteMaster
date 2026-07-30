import sqlite3
import json
import logging
import uuid
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("sync_etl_debug")

def sync_data():
    source_db = 'backend/database/railway_data.db'
    target_db = 'backend/database/transit_graph.db'
    
    s_conn = sqlite3.connect(source_db)
    t_conn = sqlite3.connect(target_db)
    
    s_cur = s_conn.cursor()
    t_cur = t_conn.cursor()
    
    t_cur.execute("SELECT id, trip_id FROM trips")
    trip_map = {str(row[1]).strip(): row[0] for row in t_cur.fetchall()}
    logger.info(f"Target trips count: {len(trip_map)}")

    s_cur.execute("SELECT train_no, class_code, availability FROM train_fares WHERE availability IS NOT NULL")
    avail_data = s_cur.fetchall()
    logger.info(f"Source availability rows: {len(avail_data)}")
    
    inv_to_insert = []
    matched_trains = set()
    
    for train_no, class_code, avail_json in avail_data:
        train_str = str(train_no).strip()
        t_id = trip_map.get(train_str)
        if not t_id:
            continue
        
        matched_trains.add(train_str)
        try:
            entries = json.loads(avail_json)
            for entry in entries:
                date_str = entry.get('date')
                status = entry.get('status', '')
                seats = 0
                if 'AVAILABLE' in status:
                    try: 
                        seats = int(status.split('-')[1])
                    except: seats = 10
                elif 'RAC' in status:
                    seats = 5
                
                try:
                    d_parts = date_str.split('-')
                    if len(d_parts) == 3:
                        d = f"{d_parts[2]}-{d_parts[1].zfill(2)}-{d_parts[0].zfill(2)}"
                        inv_to_insert.append((str(uuid.uuid4()), d, class_code, seats, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), t_id, 64))
                except: pass
        except: continue
        
    logger.info(f"Matched trains: {len(matched_trains)}")
    logger.info(f"Inserting {len(inv_to_insert)} seat inventory records...")
    
    if inv_to_insert:
        t_cur.execute("DELETE FROM seat_inventory")
        t_cur.executemany(
            "INSERT INTO seat_inventory (id, travel_date, coach_type, available_seats, last_reconciled_at, trip_id, total_seats) VALUES (?, ?, ?, ?, ?, ?, ?)",
            inv_to_insert
        )
        t_conn.commit()
    
    s_conn.close()
    t_conn.close()
    logger.info("Debug Sync complete.")

if __name__ == "__main__":
    sync_data()
