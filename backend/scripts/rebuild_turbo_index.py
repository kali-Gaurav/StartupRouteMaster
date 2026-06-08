import sys
import os
import struct
import logging
import asyncio
import numpy as np
from sqlalchemy import text

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from database.session import SessionTransit
from core.infrastructure.container import container

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("index-builder")

async def rebuild_v4_index():
    """
    [Task 11.8] Build V4 Binary Index (16 bytes: IHHBBHf).
    Includes base price estimation.
    """
    # 0. Initialize DB via IoC
    await container.get("db")
    
    db = SessionTransit()
    try:
        # 1. Fetch all stops serving as origins
        stops = db.execute(text("SELECT id, code FROM stops")).fetchall()
        logger.info(f"Rebuilding index for {len(stops)} stops...")

        for stop_id, code in stops:
            # Fetch all departures from this stop
            query = """
                SELECT st.trip_id, st.departure_timestamp, st.arrival_timestamp, 
                       t.service_mask, st.stop_sequence, st.dist_m,
                       COALESCE(f.fare, 0.0) as estimated_price
                FROM stop_times st
                JOIN trips t ON st.trip_id = t.id
                LEFT JOIN fares f ON st.trip_id = f.trip_id AND f.stop_sequence = st.stop_sequence
                WHERE st.stop_id = :sid
            """
            rows = db.execute(text(query), {"sid": stop_id}).fetchall()
            if not rows: continue

            blob = bytearray()
            def _safe_int(v):
                try: return int(v)
                except:
                    import re
                    match = re.search(r'\d+', str(v))
                    return int(match.group()) if match else 0
            for r in rows:
                tid = _safe_int(r[0])
                # Convert timestamps to relative minutes from midnight
                dep_dt = r[1]
                arr_dt = r[2]
                
                # Check if r[1] is datetime or string (sqlite quirk)
                if isinstance(dep_dt, str):
                    from datetime import datetime
                    dep_dt = datetime.fromisoformat(dep_dt)
                    arr_dt = datetime.fromisoformat(arr_dt)

                dep_mins = (dep_dt.hour * 60 + dep_dt.minute)
                arr_mins = (arr_dt.hour * 60 + arr_dt.minute)
                
                mask = int(r[3])
                seq = int(r[4])
                dist = int(r[5] // 1000)
                price = float(r[6])

                try:
                    record = struct.pack("IHHBBHf", tid, dep_mins, arr_mins, mask, seq, dist, price)
                    blob.extend(record)
                except Exception as e:
                    logger.error(f"Encoding Error for trip {tid}: {e}")

            if blob:
                upsert = """
                    INSERT INTO station_transit_index_bin (station_code, transit_blob, version)
                    VALUES (:code, :blob, 4)
                    ON CONFLICT(station_code) DO UPDATE SET transit_blob = :blob, version = 4
                """
                db.execute(text(upsert), {"code": code, "blob": bytes(blob)})
        
        db.commit()
        logger.info("✅ V4 Index Rebuild Complete.")
    except Exception as e:
        logger.error(f"Index Rebuild Failed: {e}")
        db.rollback()
    finally:
        db.close()

async def main():
    # 0. Initialize DB via IoC for the version check too
    await container.get("db")
    
    db = SessionTransit()
    try:
        db.execute(text("ALTER TABLE station_transit_index_bin ADD COLUMN version INTEGER DEFAULT 3"))
        db.commit()
    except: pass 
    db.close()
    
    await rebuild_v4_index()

if __name__ == "__main__":
    asyncio.run(main())
