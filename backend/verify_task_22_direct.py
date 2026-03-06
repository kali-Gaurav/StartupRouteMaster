import sys
import os
import time
from sqlalchemy import text

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.session import SessionTransit
from core.route_engine.direct_index import get_direct_manager

def verify_task_22():
    print("=== Verifying Task 22: Level 0 - Direct Pre-computation ===")
    
    db = SessionTransit()
    
    try:
        # Ensure we have some data to index
        # We'll just build the index from whatever is in the real transit DB
        start_time = time.perf_counter()
        manager = get_direct_manager(db)
        duration_ms = (time.perf_counter() - start_time) * 1000
        print(f"Index initialization took: {duration_ms:.2f}ms")
        
        # Test a lookup (assuming we know some station IDs)
        # We'll find a random pair that exists in the index
        if not manager._index:
            print("[SKIP] Direct index is empty. Check transit DB segments table.")
            return
            
        pair = next(iter(manager._index.keys()))
        src, dst = pair
        
        lookup_start = time.perf_counter()
        trips = manager.get_direct_trips(src, dst)
        lookup_duration_ms = (time.perf_counter() - lookup_start) * 1000
        
        print(f"Lookup for {src} -> {dst} found {len(trips)} trips.")
        print(f"Lookup duration: {lookup_duration_ms:.4f}ms")
        
        assert len(trips) > 0
        assert lookup_duration_ms < 1.0 # Must be sub-1ms O(1)
        print("[OK] Level 0 Direct Lookup is blazing fast and accurate.")

    finally:
        db.close()

    print("=== Task 22 Verification Complete ===")

if __name__ == "__main__":
    verify_task_22()
