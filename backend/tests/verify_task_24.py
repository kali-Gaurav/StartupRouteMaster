import asyncio
import os
import sys
import time
import logging
from unittest.mock import MagicMock, AsyncMock

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.data_structures import Route, RouteSegment
from services.search_service import SearchService
from database.session import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_task_24")

async def verify_task_24():
    print("\n>>> Verifying Task 24: Parallel Leg Verification")
    
    db = SessionLocal()
    service = SearchService(db)
    
    # 1. Create a 2-transfer route (3 legs)
    route = Route()
    for i in range(3):
        seg = RouteSegment(
            trip_id=i, train_number=f"T{i}", 
            departure_stop_id=i, arrival_stop_id=i+1,
            departure_code=f"S{i}", arrival_code=f"S{i+1}",
            departure_time=datetime.now(), arrival_time=datetime.now(),
            duration_minutes=100, distance_km=100.0
        )
        route.add_segment(seg)
    
    # 2. Mock DataProvider with artificial delay (500ms per call)
    async def mock_call(*args, **kwargs):
        await asyncio.sleep(0.5)
        return {"status": "verified", "available_seats": 10, "total_fare": 1000.0}
        
    service.data_provider.verify_seat_availability_unified = AsyncMock(side_effect=mock_call)
    service.data_provider.verify_fare_unified = AsyncMock(side_effect=mock_call)
    
    # 3. Test Sequential (Theoretical)
    # A 3-leg route has 6 calls (3 seats + 3 fares)
    # Sequential would take 6 * 0.5 = 3.0s
    print("  Testing Parallel Verification for a 3-leg route (6 total API calls)...")
    
    start = time.perf_counter()
    await service._verify_single_route(route, datetime.now())
    parallel_latency = (time.perf_counter() - start) * 1000
    
    print(f"  Parallel Latency: {parallel_latency:.2f}ms")
    print(f"  Theoretical Sequential Latency: 3000ms")
    
    # In parallel, it should take ~500ms (the max of any single task)
    if parallel_latency < 1000: # Allow some overhead
        print(f"  Speedup: {3000 / parallel_latency:.1f}x")
        print("\n✅ TASK 24 VERIFIED: Parallel leg verification is highly efficient.")
        return True
    else:
        print(f"❌ FAILURE: Parallel verification took too long ({parallel_latency:.2f}ms).")
        return False

if __name__ == "__main__":
    from datetime import datetime
    asyncio.run(verify_task_24())
