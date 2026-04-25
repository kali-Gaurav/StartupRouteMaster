import asyncio
import logging
import time
from datetime import datetime, timedelta
from core.route_engine.engine import RailwayRouteEngine

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("verify_search")

async def run_final_search_verification():
    print("\n--- FINAL SEARCH ENGINE VERIFICATION (E2E) ---")
    engine = RailwayRouteEngine()
    await engine.init()
    
    # Test Scenario: NDLS to BCT (Major Route)
    src = "NDLS"
    dst = "BCT"
    date = datetime.now() + timedelta(days=1)
    
    print(f"\nScenario: {src} -> {dst} on {date.date()}")
    
    try:
        start = time.perf_counter()
        # Use the orchestrator for a realistic persona
        routes = await engine.orchestrator.search_all(
            src, dst, date, 
            persona="business", 
            constraints=None
        )
        duration = (time.perf_counter() - start) * 1000
        
        print(f"Search Duration: {duration:.2f}ms")
        print(f"Routes Found: {len(routes)}")
        
        if len(routes) > 0:
            print("[OK] Search logic is producing results.")
            for i, r in enumerate(routes[:3]):
                print(f"  [{i}] ID: {r.id} | Modes: {len(r.segments)} | Score: {r.value_score:.2f}")
        else:
            print("[CRITICAL] Search logic returned ZERO results for a major hub-to-hub route.")

    except Exception as e:
        print(f"[FAIL] Search verification crashed: {e}")

    print("\n--- SEARCH VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(run_final_search_verification())
