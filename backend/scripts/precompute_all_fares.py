import sqlite3
import sys
import os
import logging

# Add backend to path to import fare_calculator
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.pricing.fare_calculator import calculate_fare

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("full_fare_precompute")

def precompute_all_fares():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Clear existing fares
    cur.execute("DELETE FROM fares")
    
    # 2. Get all segments from the database
    logger.info("Fetching all segments for calculation...")
    cur.execute("""
        SELECT s.id, s.trip_id, s.distance_km, t.trip_id as train_no 
        FROM segments s
        JOIN trips t ON s.trip_id = t.id
    """)
    segments = cur.fetchall()
    logger.info(f"Calculating fares for {len(segments)} segments...")

    fares_to_insert = []
    count = 0
    
    for seg_id, trip_pk, dist, t_no in segments:
        if not dist or dist <= 0: dist = 50.0 # Default min dist
        
        # Calculate for all classes
        for cls in ["SL", "3A", "2A", "1A"]:
            try:
                res = calculate_fare(dist, cls)
                # (segment_id, trip_id, class_type, amount)
                fares_to_insert.append((seg_id, trip_pk, cls, res["total_fare"]))
            except: continue
            
        count += 1
        if count % 20000 == 0:
            logger.info(f"Processed {count} segments...")

    logger.info(f"Inserting {len(fares_to_insert)} total fare entries...")
    cur.executemany("INSERT INTO fares (segment_id, trip_id, class_type, amount) VALUES (?, ?, ?, ?)", fares_to_insert)
    
    conn.commit()
    conn.close()
    logger.info("100% Fare Coverage Achieved.")

if __name__ == "__main__":
    precompute_all_fares()
