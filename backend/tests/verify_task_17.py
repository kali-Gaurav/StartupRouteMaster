import sys
import os
import asyncio
from datetime import datetime
import logging
import numpy as np

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.route_engine.engine import RailwayRouteEngine

logging.basicConfig(level=logging.INFO)

async def verify_task_17():
    print("\n>>> Verifying Task 17: Data Pruning & Sanitization")
    engine = RailwayRouteEngine()
    
    # Force fresh build to see pruning in action
    target_date = datetime(2026, 3, 8)
    graph = await engine._get_current_graph(target_date)
    
    snapshot = graph.snapshot
    
    # 1. Verify No Short Trips
    short_trips = [tid for tid, segs in snapshot.trip_segments.items() if len(segs) < 1]
    # Note: 1 segment = 2 stops.
    print(f"  Trips with 0 segments: {len(short_trips)}")
    
    if len(short_trips) > 0:
        print(f"❌ FAILURE: {len(short_trips)} invalid trips found in memory.")
        return False

    # 2. Verify Coordinate Matrix is valid (no NaNs)
    if np.isnan(snapshot.coordinate_matrix).any():
        print("❌ FAILURE: NaN values found in coordinate matrix.")
        return False
    
    print("  Coordinate matrix is clean (no NaNs).")

    # 3. Verify Trip Count against DB (Optional)
    import sqlite3
    conn = sqlite3.connect('backend/database/transit_graph.db')
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM trips")
    db_count = cur.fetchone()[0]
    conn.close()
    
    mem_count = len(snapshot.trip_segments)
    print(f"  Trips in DB: {db_count}, Trips in Memory: {mem_count}")
    
    if mem_count > db_count:
        print("❌ FAILURE: Memory has more trips than DB (logic error).")
        return False

    print("\n✅ TASK 17 VERIFIED: Sparse and invalid data pruned successfully.")
    return True

if __name__ == "__main__":
    # Clear snapshot to force rebuild
    snapshot_path = "snapshots/graph_snapshot_20260308.pkl"
    if os.path.exists(snapshot_path):
        os.remove(snapshot_path)
        
    asyncio.run(verify_task_17())
