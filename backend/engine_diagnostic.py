"""
Engine Diagnostic v1: Deep inspection of each routing engine's data pipeline.
Tests: Graph hydration, stop resolution, departure lookups, and search execution.
"""
import asyncio
import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict

from database.session import SessionTransit, initialize_database_pools
from core.route_engine.engine import RailwayRouteEngine
from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.constraints import RouteConstraints
from core.data_structures import Persona

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("diag")

async def run_diagnostic():
    print("\n" + "="*80)
    print("  ENGINE DIAGNOSTIC v1: Data Pipeline Inspection")
    print("="*80 + "\n")

    # --- Phase 1: Infrastructure ---
    await initialize_database_pools()
    db = SessionTransit()
    engine = RailwayRouteEngine()
    date = datetime(2026, 3, 30, 18, 0, 0)
    graph = await engine._get_current_graph(date)

    print(f"\n--- PHASE 1: Graph Snapshot Integrity ---")
    print(f"  Snapshot Date  : {graph.snapshot.date.date()}")
    print(f"  Stop Cache Size: {len(graph.stop_cache)}")
    print(f"  Trip Segments  : {len(graph.snapshot.trip_segments)}")
    print(f"  Transfer Graph : {len(graph.snapshot.transfer_graph)} stations with transfers")

    # Check vectorized data
    has_dep_data = graph.snapshot._departures_data is not None
    has_arr_data = graph.snapshot._arrivals_data is not None
    has_pattern_data = graph.snapshot._pattern_deps_data is not None
    print(f"  Departures Data: {'OK' if has_dep_data else 'MISSING'} (vectorized)")
    print(f"  Arrivals Data  : {'OK' if has_arr_data else 'MISSING'} (vectorized)")
    print(f"  Pattern Deps   : {'OK' if has_pattern_data else 'MISSING'} (vectorized)")

    if has_dep_data:
        print(f"  Departures Array Size: {len(graph.snapshot._departures_data)}")
        print(f"  Departures Index Size: {len(graph.snapshot._departures_index)}")
    if has_pattern_data:
        print(f"  Pattern Deps Array Size: {len(graph.snapshot._pattern_deps_data)}")

    # --- Phase 2: Station Resolution ---
    print(f"\n--- PHASE 2: Station Resolution ---")
    test_codes = ["KYN", "TNA", "MAS", "SBC", "ET", "BINA", "NDLS", "HWH"]
    code_to_id = {}
    
    from utils.station_utils import resolve_stations
    for code in test_codes:
        found = False
        for sid, stop in graph.stop_cache.items():
            if stop.code == code:
                code_to_id[code] = sid
                print(f"  {code:6s} -> ID: {sid:6d} | Name: {stop.name} | City: {stop.city}")
                found = True
                break
        if not found:
            print(f"  {code:6s} -> NOT FOUND in graph stop_cache!")

    # --- Phase 3: Departure Lookup (Per-Station) ---
    print(f"\n--- PHASE 3: Departure Availability ---")
    for code in ["KYN", "MAS", "ET"]:
        sid = code_to_id.get(code)
        if not sid:
            print(f"  {code}: SKIP (no station ID)")
            continue
        
        # Raw departures
        raw_deps = graph.get_departures_from_stop(sid, date, lookahead=1440)
        
        # Pattern departures (what RAPTOR uses)
        pattern_deps = graph.get_pattern_departures(sid, date, lookahead=1440)
        total_pattern = sum(len(v) for v in pattern_deps.values())
        
        print(f"  {code} (ID:{sid}): Raw Deps={len(raw_deps)}, Pattern Deps={total_pattern} ({len(pattern_deps)} patterns)")
        
        if raw_deps:
            first_3 = raw_deps[:3]
            for dt, tid in first_3:
                print(f"    -> Trip {tid} departs at {dt}")
        
        if total_pattern == 0 and len(raw_deps) == 0:
            # Check if the stop_id_map has this ID
            s_idx = graph.snapshot._stop_id_map.get(sid)
            print(f"    [DEBUG] stop_id_map lookup: sid={sid} -> index={s_idx}")
            if s_idx is not None and has_dep_data:
                off, count = graph.snapshot._departures_index[s_idx]
                print(f"    [DEBUG] departures_index: offset={off}, count={count}")
                if count > 0:
                    sample = graph.snapshot._departures_data[off:off+min(3,count)]
                    for row in sample:
                        print(f"    [DEBUG] raw departure data: ts={row[0]}, tid={row[1]}")
                        ts_val = int(row[0])
                        date_ts = int(date.timestamp())
                        print(f"    [DEBUG] departure_ts={ts_val}, search_after_ts={date_ts}, diff_hours={(ts_val-date_ts)/3600:.1f}")

    # --- Phase 4: Individual Engine Tests ---
    print(f"\n--- PHASE 4: Individual Engine Tests ---")
    constraints = RouteConstraints(max_transfers=2, persona=Persona.BUDGET)
    orchestrator = UnifiedRoutingOrchestrator(engine)

    # Test pairs
    pairs = [
        ("KYN", "TNA", "Sub-Urban Short"),
        ("MAS", "SBC", "Inter-City Medium"),
        ("ET", "BINA", "Main Line"),
    ]

    for src_code, dst_code, label in pairs:
        src_id = code_to_id.get(src_code)
        dst_id = code_to_id.get(dst_code)
        if not src_id or not dst_id:
            print(f"\n  [{label}] {src_code}->{dst_code}: SKIP (station not resolved)")
            continue
        
        print(f"\n  [{label}] {src_code} (ID:{src_id}) -> {dst_code} (ID:{dst_id})")
        
        # 4a. Check if ANY trip connects these two stations
        direct_trips = []
        for tid, segs in graph.snapshot.trip_segments.items():
            has_src = any(s.departure_stop_id == src_id for s in segs)
            has_dst = any(s.arrival_stop_id == dst_id for s in segs)
            if has_src and has_dst:
                direct_trips.append(tid)
                if len(direct_trips) >= 5: break
        print(f"    Direct trips in graph: {len(direct_trips)} {'(showing max 5)' if len(direct_trips) >= 5 else ''}")
        if direct_trips:
            for tid in direct_trips[:3]:
                print(f"      Trip {tid}: {[s.departure_code + '->' + s.arrival_code for s in graph.snapshot.trip_segments[tid][:4]]}")

        # 4b. RAPTOR Engine Test
        from core.route_engine.raptor import OptimizedRAPTOR
        raptor = OptimizedRAPTOR(max_transfers=2)
        t0 = time.perf_counter()
        try:
            raptor_results = await raptor.find_routes([src_id], [dst_id], date, constraints, graph)
            raptor_ms = (time.perf_counter() - t0) * 1000
            print(f"    RAPTOR     : {len(raptor_results)} routes in {raptor_ms:.1f}ms | Nodes explored: {raptor._nodes_explored}")
            if raptor_results:
                for r in raptor_results[:2]:
                    print(f"      -> {r.total_duration}min, {len(r.segments)} segs, engine={r.metadata.get('engine')}")
        except Exception as e:
            print(f"    RAPTOR     : ERROR - {e}")

        # 4c. TBR Engine Test
        try:
            t0 = time.perf_counter()
            tbr_results = await orchestrator.tbr_router.find_routes([src_id], [dst_id], date, constraints, graph)
            tbr_ms = (time.perf_counter() - t0) * 1000
            print(f"    TBR        : {len(tbr_results)} routes in {tbr_ms:.1f}ms")
            if tbr_results:
                for r in tbr_results[:2]:
                    segs_str = " -> ".join([f"{s.departure_code}({s.train_number})" for s in r.segments])
                    print(f"      -> {r.total_duration}min | {segs_str}")
        except Exception as e:
            print(f"    TBR        : ERROR - {e}")

        # 4d. Turbo Engine Test
        try:
            t0 = time.perf_counter()
            turbo_results = await orchestrator.turbo_router.find_routes(src_code, dst_code, date, 30)
            turbo_ms = (time.perf_counter() - t0) * 1000
            print(f"    TURBO      : {len(turbo_results)} routes in {turbo_ms:.1f}ms")
            if turbo_results:
                for r in turbo_results[:2]:
                    print(f"      -> type={r.get('type')}, train={r.get('train_no')}")
        except Exception as e:
            print(f"    TURBO      : ERROR - {e}")

        # 4e. Hub Tier 0 Test  
        try:
            t0 = time.perf_counter()
            hub_results = await orchestrator._search_tier_0_hubs_async(src_id, dst_id, date, db)
            hub_ms = (time.perf_counter() - t0) * 1000
            print(f"    HUB TIER 0 : {len(hub_results)} routes in {hub_ms:.1f}ms")
        except Exception as e:
            print(f"    HUB TIER 0 : ERROR - {e}")

    # --- Phase 5: RAPTOR Deep Debug ---
    print(f"\n--- PHASE 5: RAPTOR Deep Debug (MAS->SBC) ---")
    mas_id = code_to_id.get("MAS")
    sbc_id = code_to_id.get("SBC")
    if mas_id and sbc_id:
        # Check metro group expansion
        from utils.station_utils import get_metro_group_codes
        mas_group = get_metro_group_codes("MAS")
        sbc_group = get_metro_group_codes("SBC")
        print(f"  MAS metro group: {mas_group}")
        print(f"  SBC metro group: {sbc_group}")
        
        # Expand to IDs
        mas_ids = {mas_id}
        for code in mas_group:
            s = graph.get_stop_by_code(code)
            if s: mas_ids.add(s.id)
        sbc_ids = {sbc_id}
        for code in sbc_group:
            s = graph.get_stop_by_code(code)
            if s: sbc_ids.add(s.id)
        print(f"  Expanded MAS IDs: {mas_ids}")
        print(f"  Expanded SBC IDs: {sbc_ids}")
        
        # Check can_reach_destination for known trips
        if direct_trips:
            for tid in direct_trips[:3]:
                can_reach = graph.can_reach_destination(tid, sbc_id)
                print(f"  can_reach_destination(trip={tid}, dst={sbc_id}): {can_reach}")

        # Check transfer graph for MAS
        transfers_from_mas = graph.get_transfers_from_stop(mas_id, date, min_transfer_time=15)
        print(f"  Transfers from MAS: {len(transfers_from_mas)}")

    # --- Phase 6: Turbo Empty Leg Debug ---
    print(f"\n--- PHASE 6: Turbo Empty Leg Debug (KYN->TNA) ---")
    kyn_id = code_to_id.get("KYN")
    tna_id = code_to_id.get("TNA")
    if kyn_id and tna_id:
        # Check what Turbo sees
        from core.route_engine.turbo_router import TurboRouter
        tr = orchestrator.turbo_router
        # Check if KYN->TNA has valid segments in graph 
        kyn_trips = []
        for tid, segs in graph.snapshot.trip_segments.items():
            for s in segs:
                if s.departure_stop_id == kyn_id and s.arrival_stop_id == tna_id:
                    kyn_trips.append((tid, s))
                    break
            if len(kyn_trips) >= 5: break
        print(f"  Direct segments KYN({kyn_id})->TNA({tna_id}) in graph: {len(kyn_trips)}")
        for tid, s in kyn_trips[:3]:
            print(f"    Trip {tid}: dep={s.departure_time}, arr={s.arrival_time}, dur={s.duration_minutes}min, dist={s.distance_km}km")

    print(f"\n{'='*80}")
    print(f"  DIAGNOSTIC COMPLETE")
    print(f"{'='*80}\n")

    db.close()
    from services.multi_layer_cache import multi_layer_cache
    try:
        await multi_layer_cache.shutdown()
    except:
        pass

if __name__ == "__main__":
    asyncio.run(run_diagnostic())
