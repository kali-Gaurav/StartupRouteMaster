import sqlite3
import struct
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_task_11")

def unpack_binary_blob(blob):
    """Mirror of TurboRouter._unpack_trains logic."""
    if not blob: return {}
    num_trains = struct.unpack_from("<H", blob, 0)[0]
    trains = {}
    offset = 2
    for _ in range(num_trains):
        # IHHBBHH = 14 bytes
        tid, dep, arr, mask, seq, f3a, fsl = struct.unpack_from("<IHHBBHH", blob, offset)
        trains[tid] = {
            'dep': dep, 'arr': arr, 'mask': mask, 'seq': seq, 
            'f3a': f3a, 'fsl': fsl
        }
        offset += 14
    return trains

def verify_binary_integrity():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Pick a major station (e.g., NDLS or MS)
    station = 'NDLS'
    cur.execute("SELECT trains_binary FROM station_transit_index WHERE station_code = ?", (station,))
    row = cur.fetchone()
    
    if not row or not row[0]:
        logger.error(f"FAILURE: No binary data found for {station}")
        return False
    
    blob = row[0]
    trains = unpack_binary_blob(blob)
    
    logger.info(f"SUCCESS: Decoded {len(trains)} trains for {station} via Binary BLOB.")
    
    # Pick a random train and verify realistic data
    if trains:
        sample_tid = list(trains.keys())[0]
        data = trains[sample_tid]
        logger.info(f"Sample Train {sample_tid}: DepMins={data['dep']}, Mask={data['mask']}, Fare3A={data['f3a']}")
        
        # Test 1: Day of run bitmask (Task 12 check)
        # Sunday bit = 1 << 6 = 64
        # Monday bit = 1 << 0 = 1
        if (data['mask'] & 127) == 0:
            logger.error("FAILURE: Mask is 0, train would never run.")
            return False
            
        # Test 2: Fare sanity
        if data['f3a'] > 10000:
            logger.error(f"FAILURE: Unrealistic fare {data['f3a']} detected.")
            return False

    conn.close()
    return True

if __name__ == "__main__":
    if verify_binary_integrity():
        print("\n✅ TASK 11 VERIFIED: Binary Index Integrity is Solid.")
    else:
        print("\n❌ TASK 11 FAILED: Integrity Check Failed.")
        exit(1)
