import struct
import sqlite3
import logging
import os
import sys
from typing import Dict, List

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from sqlalchemy import text
from database.session import SessionTransit as SessionLocal, engine_transit as engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("binary-builder")

class BinaryIndexBuilder:
    """
    [Task 110] Multi-Protocol Binary Indexer.
    Converts relational GTFS data into optimized binary blobs for Turbo/FastPath lookups.
    Supports V3 (12 bytes) and V4 (16 bytes, pricing aware).
    """
    V3_FORMAT = "IHHBBH"   # 12 bytes
    V4_FORMAT = "IHHBBHf"  # 16 bytes
    
    def __init__(self, use_v4: bool = True):
        self.use_v4 = use_v4
        self.fmt = self.V4_FORMAT if use_v4 else self.V3_FORMAT
        self.record_size = 16 if use_v4 else 12

    def run(self):
        session = SessionLocal()
        logger.info(f"🚀 Initializing Binary Rebuild (Protocol: {'V4' if self.use_v4 else 'V3'})")
        
        # 1. Ensure Table exists
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS station_transit_index_bin (
                station_code TEXT PRIMARY KEY,
                transit_blob BLOB,
                version INTEGER,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # 2. Fetch all stop_times + trip info (Optimized Join)
        query = text("""
            SELECT 
                s.code as station_code,
                t.trip_id,
                st.arrival_time,
                st.departure_time,
                st.stop_sequence,
                c.monday, c.tuesday, c.wednesday, c.thursday, c.friday, c.saturday, c.sunday,
                f.amount as base_price
            FROM stop_times st
            JOIN stops s ON st.stop_id = s.id
            JOIN trips t ON st.trip_id = t.id
            JOIN calendar c ON t.service_id = c.service_id
            LEFT JOIN fares f ON t.trip_id = CAST(f.trip_id AS TEXT) AND f.class_type = '3A'
            AND f.id = (SELECT MIN(id) FROM fares f2 WHERE f2.trip_id = f.trip_id AND f2.class_type = '3A')
        """)
        
        logger.info("Fetching relational data...")
        rows = session.execute(query).fetchall()
        
        # 3. Group by Station
        station_data: Dict[str, bytes] = {}
        for row in rows:
            code = row.station_code
            if code not in station_data: station_data[code] = b""
            
            # Pack Service Mask (7 bits)
            mask = (row.monday << 0 | row.tuesday << 1 | row.wednesday << 2 | 
                    row.thursday << 3 | row.friday << 4 | row.saturday << 5 | row.sunday << 6)
            
            # Normalize Times to Minutes
            def to_mins(t_obj):
                if hasattr(t_obj, 'hour'): return t_obj.hour * 60 + t_obj.minute
                return 0
            
            arr = to_mins(row.arrival_time)
            dep = to_mins(row.departure_time)
            
            # Pack Binary Record
            try:
                trip_int = int(row.trip_id)
                if self.use_v4:
                    packed = struct.pack(self.fmt, trip_int, dep, arr, mask, row.stop_sequence, 0, float(row.base_price or 0.0))
                else:
                    packed = struct.pack(self.fmt, trip_int, dep, arr, mask, row.stop_sequence, 0)
                
                station_data[code] += packed
            except ValueError:
                continue # Skip non-numeric trips for binary index
                
        # 4. Upsert into Transit Index
        total_stations = len(station_data)
        logger.info(f"Persisting binary blobs for {total_stations} stations...")
        
        for code, blob in station_data.items():
            session.execute(text("""
                INSERT INTO station_transit_index_bin (station_code, transit_blob, version)
                VALUES (:code, :blob, :ver)
                ON CONFLICT(station_code) DO UPDATE SET transit_blob = excluded.transit_blob, version = excluded.version
            """), {"code": code, "blob": blob, "ver": 4 if self.use_v4 else 3})
            
        session.commit()
        session.close()
        logger.info("✅ Binary Rebuild Success. Fiber Core Operational.")

if __name__ == "__main__":
    builder = BinaryIndexBuilder(use_v4=True)
    builder.run()
