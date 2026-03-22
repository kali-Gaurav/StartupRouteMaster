import asyncio
import logging
import sys

# --- CRITICAL: Binary Environment Patch ---
# numpy reads datetime.datetime_CAPI during C-ext init — patch BEFORE any numpy import.
import datetime as _dt_patch
import _datetime as _dt_capi
if not hasattr(_dt_patch, 'datetime_CAPI') and hasattr(_dt_capi, 'datetime_CAPI'):
    setattr(_dt_patch, 'datetime_CAPI', _dt_capi.datetime_CAPI)
del _dt_patch, _dt_capi  # cleanup

from datetime import datetime, timedelta

from core.route_engine.engine import RailwayRouteEngine
from core.route_engine.constraints import RouteConstraints
from core.data_structures import Persona
from services.jit_manager import jit_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_search")

async def verify():
    print("🚀 Starting Final System Verification...")
    
    # 1. Initialize Nodes
    from database.session import initialize_database_pools
    from services.multi_layer_cache import cache_provider
    
    # Manually register and load nodes to avoid JIT race conditions in script
    await initialize_database_pools()
    await cache_provider.initialize()
    
    # Register JIT nodes
    from services.jit_manager import JITNode
    jit_manager.register_node(JITNode(name="DATABASE", loader=lambda: None))
    jit_manager.register_node(JITNode(name="CACHE", loader=lambda: None))
    jit_manager.mark_ready("DATABASE")
    jit_manager.mark_ready("CACHE")

    engine = RailwayRouteEngine()
    
    search_date = datetime.now() + timedelta(days=4)
    search_date = search_date.replace(hour=10, minute=0, second=0)
    
    constraints = RouteConstraints(
        persona=Persona.BUDGET,
        max_transfers=3,
        allow_unconfirmed=True
    )
    
    print(f"🔍 Searching for NDLS -> MMCT on {search_date.date()}...")
    
    from database.session import SessionTransit
    db = SessionTransit()
    try:
        routes = await engine.search(
            source_code="NDLS",
            destination_code="MMCT",
            departure_date=search_date,
            constraints=constraints,
            db=db
        )
        
        # CATEGORIZE FOR VERIFICATION (1 segment = 0 transfers, 2 segments = 1 transfer)
        categories = {"direct": [], "1t": [], "2t": [], "3t": []}
        for r in routes:
            legs = len(r.segments)
            if legs == 1: categories["direct"].append(r)
            elif legs == 2: categories["1t"].append(r)
            elif legs == 3: categories["2t"].append(r)
            elif legs >= 4: categories["3t"].append(r)
            
        print(f"\n✅ Total unique routes: {len(routes)}")
        
        # Summary report
        summary = []
        summary.append(f"Total Routes Found: {len(routes)}")
        summary.append(f"Direct Routes: {len(categories['direct'])}")
        summary.append(f"1-Transfer Routes: {len(categories['1t'])}")
        summary.append(f"2-Transfer Routes: {len(categories['2t'])}")
        summary.append(f"3-Transfer Routes: {len(categories['3t'])}")
        
        report_text = "\n".join(summary)
        print(f"\n--- VERIFICATION REPORT ---\n{report_text}\n")
        
        if len(categories["direct"]) > 0:
            print("🌟 SUCCESS: Direct routes found and categorized correctly!")
        else:
            print("❌ FAILURE: No direct routes found.")

    except Exception as e:
        print(f"\n💥 CRASH: Engine failed during search: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'db' in locals():
            db.close()

if __name__ == "__main__":
    asyncio.run(verify())
