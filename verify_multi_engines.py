import asyncio
import logging
import sys
import os
from datetime import datetime

# Setup paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from core.container import container
from core.route_engine.engine import route_engine
from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.constraints import RouteConstraints
from core.data_structures import Persona
from database.session import SessionTransit

async def verify_engines():
    logging.basicConfig(level=logging.INFO)
    print("START: Multi-Engine Verification Audit...")
    
    # Initialize Container & Services via IoC
    try:
        await container.get("db")
        await container.get("search")
    except Exception as e:
        print(f"WARN: Service init failed: {e}")

    departure_date = datetime(2026, 3, 22, 10, 0, 0)
    
    # Instantiate the Orchestrator
    orchestrator = UnifiedRoutingOrchestrator(route_engine)
    print(f"DEBUG: Orchestrator type: {type(orchestrator)}")
    print(f"DEBUG: Orchestrator attrs: {[a for a in dir(orchestrator) if not a.startswith('_')]}")
    
    if not hasattr(orchestrator, 'ultra_turbo'):
        print("ERROR: orchestrator has no 'ultra_turbo' attribute at runtime!")
    if not hasattr(orchestrator, 'turbo_router'):
        print("ERROR: orchestrator has no 'turbo_router' attribute at runtime!")

    # Common Test Case: NDLS -> MMCT
    src_id, dst_id = 5533, 5080
    src_code, dst_code = "NDLS", "MMCT"
    constraints = RouteConstraints(persona=Persona.STANDARD, max_results=20)
    
    # For engines that need the graph
    graph = await route_engine._get_current_graph(departure_date)
    orchestrator.fast_router.graph = graph

    results = {}

    # 1. Test TBR
    print("\n--- Testing TBR Router ---")
    try:
        tbr_routes = await orchestrator.tbr_router.find_routes(src_id, dst_id, departure_date, constraints, graph)
        results["TBR"] = len(tbr_routes)
        print(f"INFO: TBR: Found {len(tbr_routes)} routes")
    except Exception as e:
        print(f"ERROR: TBR Failed: {e}")

    # 2. Test Ultra-Turbo
    print("\n--- Testing Ultra-Turbo ---")
    try:
        from database.session import get_raw_transit_conn
        async with get_raw_transit_conn() as conn:
            src_ids = await orchestrator.ultra_turbo._resolve_cluster_ids(conn, src_code)
            dst_ids = await orchestrator.ultra_turbo._resolve_cluster_ids(conn, dst_code)
            ut_routes = await orchestrator.ultra_turbo._collect_day_results(conn, src_ids, dst_ids, departure_date.date(), 20, None, {}, 0)
            results["Ultra-Turbo"] = len(ut_routes)
            print(f"INFO: Ultra-Turbo: Found {len(ut_routes)} routes")
    except Exception as e:
        print(f"ERROR: Ultra-Turbo Failed: {e}")

    # 3. Test Turbo
    print("\n--- Testing Turbo Router ---")
    try:
        turbo_routes = await asyncio.to_thread(orchestrator.turbo_router.find_routes, src_code, dst_code, departure_date, 20)
        results["Turbo"] = len(turbo_routes)
        print(f"INFO: Turbo: Found {len(turbo_routes)} routes")
    except Exception as e:
        print(f"ERROR: Turbo Failed: {e}")

    # 4. Test RAPTOR
    print("\n--- Testing Optimized RAPTOR ---")
    try:
        raptor_routes = await orchestrator.raptor.find_routes(src_id, dst_id, departure_date, constraints, graph)
        results["RAPTOR"] = len(raptor_routes)
        print(f"INFO: RAPTOR: Found {len(raptor_routes)} routes")
    except Exception as e:
        print(f"ERROR: RAPTOR Failed: {e}")

    # 5. Test FastPath
    print("\n--- Testing FastPath Router ---")
    try:
        fp_routes = await asyncio.to_thread(orchestrator.fast_router.find_routes, src_id, dst_id, departure_date, constraints)
        results["FastPath"] = len(fp_routes)
        print(f"INFO: FastPath: Found {len(fp_routes)} routes")
    except Exception as e:
        print(f"ERROR: FastPath Failed: {e}")

    print("\n" + "="*30)
    print("FINAL AUDIT SUMMARY")
    print("="*30)
    for engine, count in results.items():
        status = "OK" if count > 0 else "LOW YIELD"
        print(f"{engine:<15}: {count:>3} routes {status}")
    print("="*30)

    await container.shutdown_all()

if __name__ == "__main__":
    asyncio.run(verify_engines())
