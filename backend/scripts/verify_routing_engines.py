import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta, date

import argparse

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(os.path.join(os.getcwd(), "backend", ".env"))

from database.session import SessionTransit
from utils.station_utils import resolve_stations
from core.route_engine.ultra_turbo import UltraTurboDirectEngine
from core.route_engine.turbo_router import TurboRouter
from core.route_engine.fast_router import FastPathRouter
from core.route_engine.raptor import OptimizedRAPTOR
from core.route_engine.hybrid_engine import HybridRouteEngine
from core.route_engine.engine import RailwayRouteEngine
from core.route_engine.constraints import RouteConstraints
from core.route_engine.orchestrator import UnifiedRoutingOrchestrator

# Configure logging to be less chatty
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

async def verify_engines(target_engine=None):
    # Initialize database pools
    from database.session import initialize_database_pools
    await initialize_database_pools()
    
    db = SessionTransit()
    try:
        # 1. Resolve Test Stations
        src_code, dst_code = "NDLS", "CSMT" # Delhi to Mumbai
        src_stop, dst_stop = resolve_stations(db, src_code, dst_code)
        
        if not src_stop or not dst_stop:
            print(f"CRITICAL FAILURE: Could not resolve test stations {src_code} or {dst_code}")
            return

        print(f"\n{'='*60}")
        print(f"VERIFYING ROUTING ENGINES: {src_stop.name} ({src_stop.code}) -> {dst_stop.name} ({dst_stop.code})")
        print(f"{'='*60}\n")
        
        departure_date = datetime.now() + timedelta(days=2)
        constraints = RouteConstraints()

        # Engine results accumulator
        engine_status = {}

        # ----------------------------------------------------------------------
        # Tier 0: Hub-to-Hub Index (Part of Orchestrator)
        # ----------------------------------------------------------------------
        if target_engine in (None, "tier0"):
            print(f"[*] Testing Tier 0: Hub-to-Hub Index...", end=" ", flush=True)
            try:
                # We need a dummy orchestrator to test its internal method
                print("DEBUG: Initializing RailwayRouteEngine...")
                rail_engine = RailwayRouteEngine()
                print("DEBUG: Initializing UnifiedRoutingOrchestrator...")
                orch = UnifiedRoutingOrchestrator(rail_engine)
                print(f"DEBUG: Calling _search_tier_0_hubs for {src_stop.id} -> {dst_stop.id}...")
                try:
                    hub_routes = await asyncio.to_thread(orch._search_tier_0_hubs, src_stop.id, dst_stop.id, departure_date, db)
                    print(f"DONE ({len(hub_routes)} routes)")
                except Exception as e:
                    import traceback
                    print(f"FAILED: {str(e)}")
                    traceback.print_exc()
                    hub_routes = [] # Ensure hub_routes is defined even on error
                
                engine_status["Tier 0: Hub Index"] = "OK" if len(hub_routes) > 0 else "NO_RESULTS"
                print(f"{engine_status['Tier 0: Hub Index']} ({len(hub_routes)} routes)")
            except Exception as e:
                engine_status["Tier 0: Hub Index"] = f"ERROR: {str(e)}"
                print(f"FAILED")

        # ----------------------------------------------------------------------
        # Tier 1: UltraTurboDirectEngine
        # ----------------------------------------------------------------------
        if target_engine in (None, "ultra"):
            print(f"[*] Testing Tier 1: UltraTurboDirect...", end=" ", flush=True)
            try:
                ut = UltraTurboDirectEngine()
                ut_routes = await ut.find_routes(src_stop.code, dst_stop.code, departure_date.date(), limit=10)
                engine_status["Tier 1: UltraTurbo"] = "OK" if len(ut_routes) > 0 else "NO_RESULTS"
                print(f"{engine_status['Tier 1: UltraTurbo']} ({len(ut_routes)} routes)")
            except Exception as e:
                engine_status["Tier 1: UltraTurbo"] = f"ERROR: {str(e)}"
                print(f"FAILED")

        # ----------------------------------------------------------------------
        # Tier 1: TurboRouter
        # ----------------------------------------------------------------------
        if target_engine in (None, "turbo"):
            print(f"[*] Testing Tier 1: TurboRouter...", end=" ", flush=True)
            try:
                tr = TurboRouter()
                tr_raw = tr.find_routes(src_stop.code, dst_stop.code, departure_date)
                engine_status["Tier 1: TurboRouter"] = "OK" if len(tr_raw) > 0 else "NO_RESULTS"
                print(f"{engine_status['Tier 1: TurboRouter']} ({len(tr_raw)} routes)")
            except Exception as e:
                engine_status["Tier 1: TurboRouter"] = f"ERROR: {str(e)}"
                print(f"FAILED")

        # ----------------------------------------------------------------------
        # Load Graph Snapshot for Tier 2 and 3
        # ----------------------------------------------------------------------
        graph = None
        if target_engine in (None, "fastpath", "raptor", "hybrid", "unified"):
            print(f"[*] Loading Graph Snapshot...", end=" ", flush=True)
            try:
                from core.route_engine.builder import GraphBuilder
                builder = GraphBuilder(ThreadPoolExecutor(max_workers=4))
                graph = await builder.build_graph(departure_date)
                print(f"OK")
            except Exception as e:
                print(f"FAILED: {e}")
                graph = None

        if graph and target_engine in (None, "fastpath", "raptor"):
            # ------------------------------------------------------------------
            # Tier 2: FastPathRouter
            # ------------------------------------------------------------------
            if target_engine in (None, "fastpath"):
                print(f"[*] Testing Tier 2: FastPathRouter...", end=" ", flush=True)
                try:
                    fp = FastPathRouter(graph)
                    fp_routes = fp.find_routes(src_stop.id, dst_stop.id, departure_date, constraints)
                    engine_status["Tier 2: FastPath"] = "OK" if len(fp_routes) > 0 else "NO_RESULTS"
                    print(f"{engine_status['Tier 2: FastPath']} ({len(fp_routes)} routes)")
                except Exception as e:
                    engine_status["Tier 2: FastPath"] = f"ERROR: {str(e)}"
                    print(f"FAILED")

            # ------------------------------------------------------------------
            # Tier 3: OptimizedRAPTOR
            # ------------------------------------------------------------------
            if target_engine in (None, "raptor"):
                print(f"[*] Testing Tier 3: OptimizedRAPTOR...", end=" ", flush=True)
                try:
                    raptor = OptimizedRAPTOR()
                    raptor_routes = await raptor.find_routes(src_stop.id, dst_stop.id, departure_date, constraints, graph)
                    engine_status["Tier 3: RAPTOR"] = "OK" if len(raptor_routes) > 0 else "NO_RESULTS"
                    print(f"{engine_status['Tier 3: RAPTOR']} ({len(raptor_routes)} routes)")
                except Exception as e:
                    engine_status["Tier 3: RAPTOR"] = f"ERROR: {str(e)}"
                    print(f"FAILED")

        # ----------------------------------------------------------------------
        # Kernel: HybridRouteEngine (CSA)
        # ----------------------------------------------------------------------
        if target_engine in (None, "hybrid"):
            print(f"[*] Testing Kernel: Hybrid (CSA)...", end=" ", flush=True)
            try:
                hybrid = HybridRouteEngine()
                hybrid_routes = await hybrid.find_routes(src_stop.id, dst_stop.id, departure_date, constraints, graph)
                engine_status["Kernel: Hybrid CSA"] = "OK" if len(hybrid_routes) > 0 else "NO_RESULTS"
                print(f"{engine_status['Kernel: Hybrid CSA']} ({len(hybrid_routes)} routes)")
            except Exception as e:
                engine_status["Kernel: Hybrid CSA"] = f"ERROR: {str(e)}"
                print(f"FAILED")

        # ----------------------------------------------------------------------
        # Final Verification: UnifiedRoutingOrchestrator
        # ----------------------------------------------------------------------
        print(f"\n[*] Testing FULL PIPELINE (Orchestrator)...", end=" ", flush=True)
        try:
            orch = UnifiedRoutingOrchestrator(rail_engine)
            full_routes = await orch.search_all_tiers(src_stop.code, dst_stop.code, departure_date, constraints)
            engine_status["Full Pipeline"] = "OK" if len(full_routes) > 0 else "NO_RESULTS"
            print(f"{engine_status['Full Pipeline']} ({len(full_routes)} routes)")
            
            if len(full_routes) > 0:
                engines_contributing = {}
                for r in full_routes:
                    eng = r.metadata.get("engine", "unknown")
                    engines_contributing[eng] = engines_contributing.get(eng, 0) + 1
                
                print("\nEngines contributing to final results:")
                for eng, count in engines_contributing.items():
                    print(f"  - {eng}: {count} routes")
        except Exception as e:
            import traceback
            traceback.print_exc()
            engine_status["Full Pipeline"] = f"ERROR: {str(e)}"
            print(f"FAILED")

        # SUMMARY TABLE
        print(f"\n\n{'='*60}")
        print(f"{'ENGINE':<30} | {'STATUS':<20}")
        print(f"{'-'*30}-|----------{'-'*10}")
        for eng, status in engine_status.items():
            print(f"{eng:<30} | {status:<20}")
        print(f"{'='*60}\n")

    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", help="Specific engine to test (tier0, ultra, turbo, fastpath, raptor, hybrid)")
    args = parser.parse_args()
    
    asyncio.run(verify_engines(args.engine))
