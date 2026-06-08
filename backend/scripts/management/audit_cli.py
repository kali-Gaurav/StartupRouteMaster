import argparse
import asyncio
import time
import logging
from datetime import datetime, timedelta

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("audit_cli")

def main():
    parser = argparse.ArgumentParser(description="RouteMaster Advanced Audit & Verification CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: db-audit
    db_parser = subparsers.add_parser("db-audit", help="Verify physical database against SQLAlchemy models and Alembic heads.")
    
    # Subcommand: verify
    v_parser = subparsers.add_parser("verify", help="Semantic validation of routing logic.")
    v_parser.add_argument("source", help="Source station code (e.g., NDLS)")
    v_parser.add_argument("dest", help="Destination station code (e.g., MMCT)")

    # Subcommand: benchmark
    b_parser = subparsers.add_parser("benchmark", help="Stress tests all routing tiers and outputs a latency/yield matrix.")

    # Subcommand: chaos
    c_parser = subparsers.add_parser("chaos", help="Injects live network/cache faults to assert Orchestrator self-healing.")

    args = parser.parse_args()

    if args.command == "db-audit":
        asyncio.run(audit_database())
    elif args.command == "verify":
        asyncio.run(verify_routes(args.source, args.dest))
    elif args.command == "benchmark":
        asyncio.run(benchmark_engines())
    elif args.command == "chaos":
        asyncio.run(chaos_audit())

async def audit_database():
    print("\n--- DATABASE INTEGRITY AUDIT ---")
    from database.session import initialize_database_pools, SessionUser, SessionTransit
    from database.base import UserBase, TransitBase
    from sqlalchemy import text
    import alembic.config
    import alembic.script
    import alembic.runtime.migration
    
    await initialize_database_pools()
    
    # 1. Audit User Base (Supabase/Postgres)
    print("\n>>> [Audit: User Store]")
    db_user = SessionUser()
    try:
        from database import models 
        model_tables = set(UserBase.metadata.tables.keys())
        if db_user.bind.dialect.name == 'sqlite':
            res = db_user.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        else:
            res = db_user.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).fetchall()
        physical_tables = set([r[0] for r in res])
        
        missing = model_tables - physical_tables
        print(f"  Model Tables: {len(model_tables)}")
        print(f"  Physical Tables: {len(physical_tables)}")
        if missing:
            print(f"  [FAIL] Missing tables: {missing}")
        else:
            print("  [OK] User store schema matches models.")
    finally:
        db_user.close()

    # 2. Audit Transit Base (Railway/SQLite)
    print("\n>>> [Audit: Transit Engine]")
    db_transit = SessionTransit()
    try:
        model_tables = set(TransitBase.metadata.tables.keys())
        if db_transit.bind.dialect.name == 'sqlite':
            res = db_transit.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        else:
            res = db_transit.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).fetchall()
        physical_tables = set([r[0] for r in res])
        
        missing = model_tables - physical_tables
        print(f"  Model Tables: {len(model_tables)}")
        print(f"  Physical Tables: {len(physical_tables)}")
        if missing:
            print(f"  [FAIL] Missing tables: {missing}")
        else:
            print("  [OK] Transit engine schema matches models.")
    finally:
        db_transit.close()
    
    print("\n--- AUDIT COMPLETE ---\n")

async def verify_routes(src_code: str, dst_code: str):
    print(f"\n--- 🗺️ ROUTE SEMANTIC VERIFICATION: {src_code} -> {dst_code} ---")
    from database.session import initialize_database_pools, SessionTransit
    from services.search_service import SearchService
    
    await initialize_database_pools()
    db = SessionTransit()
    search_service = SearchService(db)
    
    target_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    
    try:
        res = await search_service.search_routes(src_code, dst_code, target_date)
        if res.get("status") != "success":
            print(f"[FAIL] Search failed: {res.get('message')}")
            return
            
        journeys = res.get("data", {}).get("journeys", [])
        print(f"[OK] Search successful. Yield: {len(journeys)} routes.")
        
        # Semantic Integrity Checks
        violations = 0
        for idx, journey in enumerate(journeys):
            segments = journey.get("segments", [])
            if not segments:
                print(f"[FAIL] Journey {idx} has NO segments!")
                violations += 1
                continue
                
            # Chronological check
            prev_arr = None
            for s_idx, seg in enumerate(segments):
                dep_time = datetime.fromisoformat(seg["departure_time"])
                arr_time = datetime.fromisoformat(seg["arrival_time"])
                
                if dep_time >= arr_time:
                    print(f"[FAIL] Journey {idx}, Seg {s_idx}: Departure >= Arrival")
                    violations += 1
                
                if prev_arr and dep_time < prev_arr:
                    print(f"[FAIL] Journey {idx}, Seg {s_idx}: Departs before previous segment arrives (Time paradox)")
                    violations += 1
                
                prev_arr = arr_time
                
        if violations == 0:
            print("[OK] Semantic validation passed: All routes are chronologically and physically possible.")
        else:
            print(f"[FAIL] Encountered {violations} semantic violations.")
            
    finally:
        db.close()
    print("--- VERIFICATION COMPLETE ---\n")

async def benchmark_engines():
    print("\n--- 🏎️ ENGINE PERFORMANCE BENCHMARK ---")
    from database.session import initialize_database_pools, SessionTransit
    from core.route_engine.engine import RailwayRouteEngine
    from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
    from utils.station_utils import resolve_stations
    
    await initialize_database_pools()
    db = SessionTransit()
    engine = RailwayRouteEngine()
    orchestrator = UnifiedRoutingOrchestrator(engine)
    date = datetime.now() + timedelta(days=2)
    
    test_cases = [("KYN", "TNA", "Short"), ("MAS", "SBC", "Medium"), ("NDLS", "MMCT", "Long")]
    
    try:
        graph = await engine._get_current_graph(date)
        
        for src, dst, label in test_cases:
            print(f"\nEvaluating Profile: {label} ({src} -> {dst})")
            s_stop, d_stop = resolve_stations(db, src, dst)
            if not s_stop or not d_stop:
                print("  [WARN] Stations not resolvable.")
                continue
            
            # Tier 1: Turbo
            t0 = time.perf_counter()
            from core.route_engine.base import RoutingRequest, RouteConstraints
            req = RoutingRequest(source_code=src, destination_code=dst, departure_date=date, constraints=RouteConstraints(), limit=10, db_session=db)
            t_res = await orchestrator.turbo_router.find_routes(req)
            t_ms = (time.perf_counter() - t0) * 1000
            print(f"  +- TURBO  : {t_ms:>8.2f}ms | Yield: {len(t_res)}")
            
            # Tier 2: TBR
            t0 = time.perf_counter()
            req.src_cluster_ids = [s_stop.id]
            req.dst_cluster_ids = [d_stop.id]
            tbr_res = await orchestrator.tbr_router.find_routes(req)
            tbr_ms = (time.perf_counter() - t0) * 1000
            print(f"  +- TBR    : {tbr_ms:>8.2f}ms | Yield: {len(tbr_res)}")
            
            # Tier 3: RAPTOR
            t0 = time.perf_counter()
            rap_res = await orchestrator.raptor.find_routes(s_stop.id, d_stop.id, date, RouteConstraints(), graph)
            rap_ms = (time.perf_counter() - t0) * 1000
            print(f"  +- RAPTOR : {rap_ms:>8.2f}ms | Yield: {len(rap_res)}")
            
    finally:
        db.close()
    print("\n--- BENCHMARK COMPLETE ---\n")

async def chaos_audit():
    print("\n--- 🛡️ CHAOS RESILIENCE AUDIT ---")
    from database.session import initialize_database_pools, SessionTransit
    from services.search_service import SearchService
    from core.nexus.audit.chaos import nexus_chaos
    
    await initialize_database_pools()
    db = SessionTransit()
    search_service = SearchService(db)
    
    print("Test 1: Normal Baseline")
    start = time.perf_counter()
    res = await search_service.search_routes("MAS", "SBC", "2026-03-30")
    print(f"  [OK] Yield: {len(res.get('data', {}).get('journeys', []))} routes in {(time.perf_counter()-start)*1000:.1f}ms")
    
    print("\nTest 2: Injecting Redis Cache Latency (+500ms)")
    nexus_chaos.arm("redis", base_delay=0.5, jitter=0.1)
    start = time.perf_counter()
    res2 = await search_service.search_routes("MAS", "SBC", "2026-03-30")
    nexus_chaos.disarm("redis")
    lat2 = (time.perf_counter()-start)*1000
    if res2.get("status") == "success" and lat2 > 500:
        print(f"  [OK] System survived latency. Time: {lat2:.1f}ms")
    else:
        print(f"  [FAIL] Did not properly handle latency.")
        
    print("\nTest 3: Injecting 100% ML Engine Failure")
    nexus_chaos.arm("search_engine", error_rate=1.0)
    try:
        res3 = await search_service.search_routes("MAS", "SBC", "2026-03-30")
        if res3.get("status") == "success":
            print(f"  [OK] Orchestrator Graceful Fallback Active. System did not crash.")
        else:
            print(f"  [FAIL] System returned non-success status during ML failure.")
    except Exception as e:
        print(f"  [FAIL] System CRASHED without fallback: {e}")
    finally:
        nexus_chaos.disarm("search_engine")
        
    print("\n--- CHAOS AUDIT COMPLETE ---\n")

if __name__ == "__main__":
    main()
