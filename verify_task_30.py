import asyncio
import logging
import time
from datetime import datetime, date, timedelta
import sys
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-task-30")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.constraints import RouteConstraints
from core.data_structures import Persona, Route, RouteSegment

async def verify_task_30_streaming():
    print("\n🌊 DEEP BEHAVIORAL VERIFICATION: Task 30 (Streaming Results)\n")
    
    # Create Mock Engine and Orchestrator
    class MockEngine:
        async def _get_current_graph(self, dt):
            class MockOverlay:
                async def sync_with_db(self, db, dt): pass
                platform_changes = {}
                def is_cancelled(self, tid): return False
            class MockGraph:
                overlay = MockOverlay()
                snapshot = None # Mock snapshot
            return MockGraph()
            
    engine = MockEngine()
    orchestrator = UnifiedRoutingOrchestrator(engine)
    
    # Mock routing engines to return fake routes with delays to simulate tier speed
    class FastEngine:
        async def find_routes(self, *args, **kwargs):
            await asyncio.sleep(0.05) # 50ms TTFR
            r = Route()
            r.add_segment(RouteSegment(trip_id=1, departure_time=datetime.now(), arrival_time=datetime.now()+timedelta(hours=1), duration_minutes=60, distance_km=100, train_number="FAST", fare=0.0, service_mask=127, metadata={}))
            return [r]
            
    class SlowEngine:
        def find_routes(self, *args, **kwargs): # Turbo uses to_thread, must be sync
            time.sleep(0.2) # 200ms
            # Turbo returns a dict format, but let's just make the mock return a dict
            return [{"type": "direct", "train_no": "SLOW", "dep": "10:00", "arr": "12:00", "duration": 120, "distance": 200.0, "score": 100}]

    class VerySlowEngine:
        async def find_routes(self, *args, **kwargs):
            await asyncio.sleep(0.5) # 500ms
            r = Route()
            r.add_segment(RouteSegment(trip_id=3, departure_time=datetime.now(), arrival_time=datetime.now()+timedelta(hours=3), duration_minutes=180, distance_km=300, train_number="VERYSLOW", fare=0.0, service_mask=127, metadata={}))
            return [r]

    # Patch orchestrator engines
    orchestrator.ultra_turbo.find_routes = FastEngine().find_routes
    orchestrator.turbo_router.find_routes = SlowEngine().find_routes
    
    class SyncFastPath:
        def find_routes(self, *args, **kwargs):
            return []
    orchestrator.fast_router = SyncFastPath()
    
    async def mock_raptor_find(*args, **kwargs):
        return await VerySlowEngine().find_routes()
    orchestrator.raptor.find_routes = mock_raptor_find
    
    async def mock_hub_find(*args, **kwargs):
        return []
    orchestrator._search_tier_0_hubs_async = mock_hub_find
    
    # Mock DB and Stop
    class MockStop:
        id = 1
        code = "NDLS"
    class MockDB:
        def execute(self, *args, **kwargs):
            class R:
                def fetchall(self): return []
            return R()
        def close(self): pass
        
    import utils.station_utils
    utils.station_utils.resolve_stations = lambda db, src, dst: (MockStop(), MockStop())
    
    print("Starting Streaming Search...")
    c = RouteConstraints(persona=Persona.STANDARD)
    
    start_time = time.perf_counter()
    ttfr = None
    batch_count = 0
    
    async for batch in orchestrator.stream_all_tiers("NDLS", "BCT", datetime.now(), c, db=MockDB()):
        if not batch: continue
        batch_count += 1
        current_time = (time.perf_counter() - start_time) * 1000
        
        if ttfr is None:
            ttfr = current_time
            print(f"  🔥 First Batch Received! TTFR: {ttfr:.2f}ms")
            # Should be fast engine (~50ms) + setup overhead (~200ms)
            assert ttfr < 350
            print("  ✅ Subtask 30.2: Tier 1 Fast-Track Yield Verified.")
            
        print(f"  📦 Batch {batch_count} yielded at {current_time:.2f}ms with {len(batch)} routes. Tier: {batch[0].metadata.get('tier')}")
        
    ttlr = (time.perf_counter() - start_time) * 1000
    print(f"\n  🏁 Search Complete. TTLR (Time To Last Result): {ttlr:.2f}ms")
    assert ttlr > 400 # Must wait for the VerySlowEngine (~500ms)
    print("  ✅ Subtask 30.3: Tier 3 Background Processing Verified.")
    print("  ✅ Subtask 30.1: Orchestrator Generator Yield Verified.")
    
    assert batch_count == 3 # Fast, Slow, VerySlow
    
    print("\n🏆 Task 30 Streaming Results Deeply Verified!\n")

if __name__ == "__main__":
    asyncio.run(verify_task_30_streaming())