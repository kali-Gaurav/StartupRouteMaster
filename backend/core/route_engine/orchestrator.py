import asyncio
import logging
import time
import struct
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import text

from .constraints import RouteConstraints
from core.data_structures import Route, RouteSegment, TransferConnection
from .turbo_router import TurboRouter
from .raptor import OptimizedRAPTOR
from .fast_router import FastPathRouter
from .scoring import RouteScorer
from core.pricing.fare_calculator import calculate_fare

from concurrent.futures import ThreadPoolExecutor
import os

# Task 10.18: High-capacity thread pool for CPU-bound binary routing
# The default pool is too small for concurrent multi-threaded orchestration.
ROUTING_POOL = ThreadPoolExecutor(
    max_workers=min(64, (os.cpu_count() or 4) * 8),
    thread_name_prefix="routing_worker"
)

logger = logging.getLogger(__name__)

class UnifiedRoutingOrchestrator:
    """
    10X Performance Orchestrator.
    Manages Tiered Routing:
    - Tier 0: Backbone (Hub-to-Hub)
    - Tier 1: Turbo (SQL Direct/1-T)
    - Tier 2: FastPath (O(1) BFS 2-T)
    - Tier 3: RAPTOR (Discovery)
    """
    def __init__(self, route_engine_instance):
        self.engine = route_engine_instance
        self.turbo_router = TurboRouter()
        self.fast_router = FastPathRouter(None) 
        self.raptor = OptimizedRAPTOR()

    async def search_all_tiers(
        self,
        source_code: str,
        destination_code: str,
        departure_date: datetime,
        constraints: RouteConstraints,
        limit: int = 50,
        db=None
    ) -> List[Route]:
        start_time = time.perf_counter()
        from utils.station_utils import resolve_stations

        # Resolve stations for all engines
        source_stop, dest_stop = resolve_stations(db, source_code, destination_code)
        if not source_stop or not dest_stop: return []

        # 1. Tier 0: Hub-to-Hub Index (Sub-5ms)
        hub_results = self._search_tier_0_hubs(source_stop.id, dest_stop.id, departure_date, db)

        # 2. Prepare Graph
        graph = await self.engine._get_current_graph(departure_date)
        self.fast_router.graph = graph

        # 3. Dynamic Depth Management (New Upgrade)
        # We start with balanced transfers but push to 3 if Tier 0/1 are empty
        max_t = 2 if len(hub_results) > 2 else 3
        self.raptor.max_transfers = max_t

        # 4. RUN ALL ENGINES IN PARALLEL (Using High-Capacity Pool)
        logger.info(f"Orchestrator: Executing engines for {source_code} -> {destination_code} (Max Transfers: {max_t})")
        loop = asyncio.get_running_loop()

        # Tier 1: Turbo (SQL)
        t1_task = loop.run_in_executor(ROUTING_POOL, self.turbo_router.find_routes, source_code, destination_code, departure_date, limit)

        # Tier 2: FastPath (O(1) BFS)
        t2_task = loop.run_in_executor(ROUTING_POOL, self.fast_router.find_routes, source_stop.id, dest_stop.id, departure_date, constraints)

        # Tier 3: RAPTOR (Deep Discovery)
        t3_task = self.raptor.find_routes(source_stop.id, dest_stop.id, departure_date, constraints, graph)

        turbo_raw, fast_res, raptor_res = await asyncio.gather(t1_task, t2_task, t3_task)

        # 5. CONSOLIDATE & UNION
        all_routes: List[Route] = []
        all_routes.extend(hub_results)
        all_routes.extend(self._hydrate_turbo_results(turbo_raw, source_code, destination_code))
        all_routes.extend(fast_res)
        all_routes.extend(raptor_res)

        # 6. UNIVERSAL FARE HYDRATION & SCORING
        # [8.3] Graph Pruning: Filter out cancelled trains
        unique_routes = await self._filter_cancelled_trains(all_routes, departure_date, db)
        unique_routes = self._global_deduplicate(unique_routes)
        await self._hydrate_fares_and_score(unique_routes, constraints, graph, db)

        unique_routes.sort(key=lambda x: x.score)

        latency = (time.perf_counter() - start_time) * 1000
        logger.info(f"Orchestrator: Found {len(unique_routes)} unified routes in {latency:.2f}ms")

        return unique_routes[:limit]
    async def _filter_cancelled_trains(self, routes: List[Route], date: datetime, db) -> List[Route]:
        """[8.3] Filters out routes containing trains marked as cancelled."""
        try:
            date_str = date.strftime("%Y-%m-%d")
            # Use connection if db is Engine
            if hasattr(db, 'connect'):
                with db.connect() as conn:
                    rows = conn.execute(text(
                        "SELECT train_no FROM cancelled_trains WHERE travel_date = :dt"
                    ), {"dt": date_str}).fetchall()
            else:
                # Assume it's a Session
                rows = db.execute(text(
                    "SELECT train_no FROM cancelled_trains WHERE travel_date = :dt"
                ), {"dt": date_str}).fetchall()
            
            cancelled_nos = {str(r[0]) for r in rows}
            if not cancelled_nos: return routes
            
            filtered = []
            for r in routes:
                is_cancelled = False
                for s in r.segments:
                    if str(s.train_number) in cancelled_nos:
                        is_cancelled = True
                        break
                if not is_cancelled:
                    filtered.append(r)
            
            if len(filtered) < len(routes):
                logger.warning(f"Pruned {len(routes) - len(filtered)} routes due to active cancellations on {date_str}.")
            return filtered
        except Exception as e:
            logger.error(f"Error filtering cancellations: {e}")
            return routes

    def _search_tier_0_hubs(self, src_id: int, dst_id: int, date: datetime, db) -> List[Route]:
        """Task 18: Instant Hub-to-Hub lookup [Aggressive Multiplier]."""
        try:
            row = db.execute(text(
                "SELECT trains_json FROM hub_connectivity_index WHERE src_hub_id = :src AND dst_hub_id = :dst"
            ), {"src": src_id, "dst": dst_id}).fetchone()
            
            if not row: return []
            
            trains = json.loads(row[0])
            results = []
            # Increase candidate intake: Take more trains from the index
            for t in trains[:20]: 
                rt = Route()
                seg = RouteSegment(
                    trip_id=t['tid'],
                    departure_stop_id=src_id,
                    arrival_stop_id=dst_id,
                    departure_time=self._parse_turbo_time(t['dep']),
                    arrival_time=self._parse_turbo_time(t['arr']),
                    duration_minutes=0, # Will be hydrated
                    distance_km=0.0,
                    train_number=str(t['tid'])
                )
                rt.add_segment(seg)
                rt.metadata["engine"] = "hub_tier_0"
                results.append(rt)
            return results
        except Exception as e:
            logger.error(f"Hub Tier 0 error: {e}")
            return []

    async def _hydrate_fares_and_score(self, routes: List[Route], constraints: RouteConstraints, graph, db):
        from .scoring import RouteScorer
        from sqlalchemy import text
        
        trip_pks = set()
        train_nos = set()
        for r in routes:
            for s in r.segments:
                if isinstance(s.trip_id, int): trip_pks.add(s.trip_id)
                if s.train_number: train_nos.add(str(s.train_number))
        
        fare_map = {} 
        
        if trip_pks:
            pks_str = ",".join([str(tid) for tid in trip_pks])
            rows = db.execute(text(f"SELECT trip_id, amount FROM fares WHERE trip_id IN ({pks_str})")).fetchall()
            for tid, amt in rows:
                fare_map[str(tid)] = amt

        if train_nos:
            nos_str = ",".join([f"'{n}'" for n in train_nos])
            # Join fares.trip_id (INT) with trips.id (INT) and filter by trips.trip_id (VARCHAR)
            rows = db.execute(text(f"""
                SELECT t.trip_id, f.amount 
                FROM fares f 
                JOIN trips t ON f.trip_id = t.id 
                WHERE t.trip_id IN ({nos_str})
            """)).fetchall()
            for tcode, amt in rows:
                fare_map[str(tcode)] = amt

        for r in routes:
            # [38.3] Multi-leg fare optimization
            is_multi = len(r.segments) > 1
            total_dist = sum(s.distance_km for s in r.segments)
            
            for s in r.segments:
                # If distance is missing, use a default slab
                if not s.distance_km: s.distance_km = 100.0
                
                # Fetch base amount from map (populated above)
                base_amt = fare_map.get(str(s.trip_id)) or fare_map.get(str(s.train_number))
                
                if base_amt and not is_multi:
                    s.fare = float(base_amt)
                else:
                    # [38.2] Recalculate using telescopic logic for multi-leg
                    # Assuming SL class for default discovery
                    fare_res = calculate_fare(s.distance_km, "SL", is_multi_leg=is_multi)
                    s.fare = fare_res["total_fare"]
            
            r.total_cost = sum(s.fare for s in r.segments)
            # Add small discount if total distance is large (Telescopic benefit)
            if is_multi and total_dist > 1000:
                r.total_cost *= 0.98 # Extra 2% optimization for backbone routes
            
            r.total_duration = sum(s.duration_minutes for s in r.segments) + sum(t.duration_minutes for t in r.transfers)
            r.score = await RouteScorer.score_route(r, constraints, getattr(graph.snapshot, 'reliability_scores', {}))

    def _hydrate_turbo_results(self, turbo_raw: List[Dict], source: str, destination: str) -> List[Route]:
        """Converts raw Turbo SQL results into rich Route objects."""
        routes = []
        for r in turbo_raw:
            rt = Route()
            if r.get("type") in ("direct", "direct_backbone"):
                seg = RouteSegment(
                    trip_id=r.get('train_no'),
                    departure_stop_id=0,
                    arrival_stop_id=0,
                    departure_code=source,
                    arrival_code=destination,
                    departure_time=self._parse_turbo_time(r.get('dep')),
                    arrival_time=self._parse_turbo_time(r.get('arr')),
                    duration_minutes=0,
                    distance_km=0.0,
                    fare=1500.0,
                    train_number=str(r.get('train_no'))
                )
                rt.add_segment(seg)
                rt.metadata["engine"] = "turbo_direct"
            elif r.get("type") == "1-transfer":
                legs = r.get("legs", [])
                s1 = RouteSegment(
                    trip_id=legs[0].get('train'),
                    departure_stop_id=0,
                    arrival_stop_id=0,
                    departure_code=legs[0].get('from'),
                    arrival_code=legs[0].get('to'),
                    departure_time=self._parse_turbo_time(legs[0].get('dep')),
                    arrival_time=self._parse_turbo_time(legs[0].get('arr')),
                    duration_minutes=0,
                    distance_km=0.0,
                    train_number=str(legs[0].get('train'))
                )
                s2 = RouteSegment(
                    trip_id=legs[1].get('train'),
                    departure_stop_id=0,
                    arrival_stop_id=0,
                    departure_code=legs[1].get('from'),
                    arrival_code=legs[1].get('to'),
                    departure_time=self._parse_turbo_time(legs[1].get('dep')),
                    arrival_time=self._parse_turbo_time(legs[1].get('arr')),
                    duration_minutes=0,
                    distance_km=0.0,
                    train_number=str(legs[1].get('train'))
                )
                rt.add_segment(s1)
                rt.add_segment(s2)
                
                hub_code = r.get("hub", "UNK")
                wait_mins = int((s2.departure_time - s1.arrival_time).total_seconds() / 60)
                tc = TransferConnection(
                    station_id=0, 
                    arrival_time=s1.arrival_time, 
                    departure_time=s2.departure_time,
                    duration_minutes=wait_mins,
                    station_name=hub_code
                )
                rt.add_transfer(tc)
                rt.metadata["engine"] = "turbo_transfer"
            
            if rt.segments:
                routes.append(rt)
        return routes

    def _parse_turbo_time(self, time_str: str) -> datetime:
        try:
            now = datetime.now()
            t = datetime.strptime(time_str.split('.')[0], "%H:%M:%S").time()
            return datetime.combine(now.date(), t)
        except:
            return datetime.now()

    def _global_deduplicate(self, routes: List[Route]) -> List[Route]:
        """[33.6] Tuned Pareto + [5.9] Strict Deduplication."""
        if not routes: return []
        
        # 1. Apply Strict Sequence & Window Dedup (Task 5)
        from utils.route_utils import RouteDedupFilter
        strict_routes = RouteDedupFilter.apply_strict_dedup(routes)
        
        import numpy as np
        from utils.algo_utils import find_pareto_frontier
        
        # 2. Second Pass: Hard Unique (ID based)
        unique_map = {}
        for r in strict_routes:
            if not r.segments: continue
            jid = r.journey_id
            if jid not in unique_map or r.score < unique_map[jid].score:
                unique_map[jid] = r
        
        initial_list = list(unique_map.values())
        
        # 2. Second Pass: Pareto Optimization
        # Dimensions: [Arrival, Score, Cost, Transfers]
        data = np.array([
            [
                r.segments[-1].arrival_time.timestamp() if r.segments else 0,
                r.score,
                r.total_cost,
                len(r.transfers)
            ]
            for r in initial_list
        ], dtype=np.float64)
        
        mask = find_pareto_frontier(data)
        final_list = [initial_list[i] for i in range(len(initial_list)) if mask[i]]
        
        logger.info(f"Global Deduplication: {len(routes)} -> {len(initial_list)} (Unique) -> {len(final_list)} (Pareto)")
        return final_list
