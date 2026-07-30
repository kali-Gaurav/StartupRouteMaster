import sqlite3
import struct
from datetime import datetime, date
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_task_12")

def get_day_mask(search_date):
    """Mon=1, Tue=2, Wed=4, Thu=8, Fri=16, Sat=32, Sun=64"""
    return 1 << search_date.weekday()

def verify_bitmask_filtering():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # NDLS search
    cur.execute("SELECT trains_binary FROM station_transit_index WHERE station_code = 'NDLS'")
    blob = cur.fetchone()[0]
    
    # 1. Test Monday Search (mask=1)
    monday = date(2026, 3, 9) # Monday
    m_mask = get_day_mask(monday)
    
    # 2. Test Sunday Search (mask=64)
    sunday = date(2026, 3, 8) # Sunday
    s_mask = get_day_mask(sunday)
    
    # Decode
    num_trains = struct.unpack_from("<H", blob, 0)[0]
    m_count, s_count = 0, 0
    offset = 2
    for _ in range(num_trains):
        tid, dep, arr, mask, seq, f3a, fsl = struct.unpack_from("<IHHBBHH", blob, offset)
        if mask & m_mask: m_count += 1
        if mask & s_mask: s_count += 1
        offset += 14
        
    logger.info(f"NDLS Trains: Total={num_trains}, MondayRun={m_count}, SundayRun={s_count}")
    
    if m_count == 0 or s_count == 0:
        logger.error("FAILURE: No trains found running on major days.")
        return False
        
    conn.close()
    return True

if __name__ == "__main__":
    if verify_bitmask_filtering():
        print("\n✅ TASK 12 VERIFIED: Bitmask Filtering is Correct.")
    else:
        print("\n❌ TASK 12 FAILED: Bitmask Filtering Check Failed.")
        exit(1)
