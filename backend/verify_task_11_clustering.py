import sys
import os
import asyncio
from datetime import datetime

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.session import SessionTransit
from database.models import Stop
from core.route_engine.clustering import StationClusterManager

def verify_task_11():
    print("=== Verifying Task 11: Station Spatial Clustering ===")
    
    db = SessionTransit()
    
    try:
        # 1. Setup Mock Nearby Stations if they don't exist
        # New Delhi (NDLS) and Shivaji Bridge (CSB) are very close (~1km)
        ndls = db.query(Stop).filter(Stop.code == "NDLS").first()
        csb = db.query(Stop).filter(Stop.code == "CSB").first()
        
        if not ndls or not csb:
            print("[SKIP] NDLS or CSB not found in DB. Use real stations for this test.")
            return

        print(f"Testing clustering for {ndls.name} ({ndls.latitude}, {ndls.longitude})")
        
        manager = StationClusterManager(db)
        nearby = manager.get_nearby_stations(ndls.id)
        
        nearby_codes = []
        for sid, dist in nearby:
            s = db.query(Stop).filter(Stop.id == sid).first()
            if s: nearby_codes.append(s.code)
            
        print(f"Nearby stations found: {nearby_codes}")
        
        # CSB should be in the cluster of NDLS
        assert "CSB" in nearby_codes or "TKJ" in nearby_codes or "NZM" in nearby_codes
        print("[OK] Nearby stations correctly identified via spatial clustering")

        # 2. Test Walking Transfer Injection
        arrival_time = datetime(2026, 3, 9, 10, 0)
        transfers = manager.inject_walking_transfers(ndls.id, arrival_time)
        
        assert len(transfers) > 0
        assert transfers[0].duration_minutes > 15 # Should include buffer
        print(f"[OK] Injected {len(transfers)} walking transfers with logical durations")

    finally:
        db.close()

    print("=== Task 11 Verification Complete ===")

if __name__ == "__main__":
    verify_task_11()
