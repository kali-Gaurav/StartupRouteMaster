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

async def verify_task_16_1():
    print("\n>>> Verifying Task 16.1: Coordinate Matrix Generation")
    engine = RailwayRouteEngine()
    
    # Force graph build
    target_date = datetime(2026, 3, 8)
    graph = await engine._get_current_graph(target_date)
    
    snapshot = graph.snapshot
    
    # 1. Check if matrix exists
    if snapshot.coordinate_matrix is None:
        print("❌ FAILURE: coordinate_matrix is None.")
        return False
    
    # 2. Check Type
    if not isinstance(snapshot.coordinate_matrix, np.ndarray):
        print(f"❌ FAILURE: coordinate_matrix is not a numpy array. Found: {type(snapshot.coordinate_matrix)}")
        return False
        
    # 3. Check Shape
    num_stops = len(snapshot.stop_cache)
    expected_shape = (num_stops, 2)
    if snapshot.coordinate_matrix.shape != expected_shape:
        print(f"❌ FAILURE: Unexpected matrix shape. Expected {expected_shape}, got {snapshot.coordinate_matrix.shape}")
        return False
        
    # 4. Check Mapping
    if not snapshot.stop_id_to_idx:
        print("❌ FAILURE: stop_id_to_idx map is empty.")
        return False
        
    # Verify sample station (NDLS if it exists)
    import sqlite3
    conn = sqlite3.connect('backend/database/transit_graph.db')
    cur = conn.cursor()
    cur.execute("SELECT id, latitude, longitude FROM stops WHERE code = 'NDLS'")
    row = cur.fetchone()
    conn.close()
    
    if row:
        sid, lat, lon = row
        idx = snapshot.stop_id_to_idx.get(sid)
        if idx is None:
            print(f"❌ FAILURE: NDLS (ID {sid}) not found in stop_id_to_idx.")
            return False
            
        m_coords = snapshot.coordinate_matrix[idx]
        print(f"  NDLS mapping verified: Matrix[{idx}] = {m_coords}")
        
        # Check tolerance (float32 vs high precision)
        if abs(m_coords[0] - lat) > 0.001 or abs(m_coords[1] - lon) > 0.001:
             print(f"❌ FAILURE: Coordinate mismatch for NDLS. DB: [{lat}, {lon}], Matrix: {m_coords}")
             return False

    print(f"\n✅ TASK 16.1 VERIFIED: Coordinate matrix of shape {snapshot.coordinate_matrix.shape} is operational.")
    return True

if __name__ == "__main__":
    asyncio.run(verify_task_16_1())
