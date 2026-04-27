from dataclasses import dataclass
import asyncio
import logging
import time as _time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any, Tuple, Union, overload, cast
from sqlalchemy.orm import Session
import numpy as np

# Absolute imports for consistency
import sys
import os
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from core.data_structures import Route, RouteSegment, TransferConnection, Persona
from core.frontier import FrontierManager, FrontierRoute
from services.ml.reliability_engine import reliability_engine
from .constraints import RouteConstraints
from core.hubs import MEGA_HUBS, MAJOR_HUBS
from .graph import TimeDependentGraph, StaticGraphSnapshot
from core.routing.frequency_aware_range import get_frequency_aware_sizer
from core.nexus.audit.chaos import chaos_trap
from core.nexus.audit.governor import nexus_governor
from .neural_pruner import get_raptor_pruner
from .base import BaseRoutingEngine, RoutingRequest, RoutingResponse

logger = logging.getLogger("raptor")

@dataclass(slots=True)
class SearchRoute:
    """Lightweight route representation for traversal."""
    trip_id: int
    from_stop_id: int
    to_stop_id: int
    departure_time: datetime
    arrival_time: datetime
    round_num: int
    parent: Optional['SearchRoute'] = None
    transfer: Optional[TransferConnection] = None
    total_dist: float = 0.0
    total_wait: int = 0
    # [Task 4] Bloom-filter based cycle detection (128-bit split bitmask)
    v_bloom_low: int = 0
    v_bloom_high: int = 0
    reliability: float = 1.0 
    total_cost: float = 0.0    # [McRAPTOR]
    comfort_score: float = 0.5 # [McRAPTOR]

    def add_to_bloom(self, station_id: int):
        idx = station_id % 128
        if idx < 64:
            self.v_bloom_low |= (1 << idx)
        else:
            self.v_bloom_high |= (1 << (idx - 64))

    def has_cycle(self, station_id: int) -> bool:
        idx = station_id % 128
        is_set = False
        if idx < 64:
            is_set = bool(self.v_bloom_low & (1 << idx))
        else:
            is_set = bool(self.v_bloom_high & (1 << (idx - 64)))
            
        if not is_set:
            return False
            
        # Bloom hit: Check linked list to confirm (avoids collision pruning)
        curr = self
        while curr:
            if curr.to_stop_id == station_id or curr.from_stop_id == station_id:
                return True
            curr = curr.parent
        return False

class OptimizedRAPTOR(BaseRoutingEngine):
    @property
    def engine_id(self) -> str:
        return "raptor_v2_window"

    def __init__(self, max_transfers: int = 3, max_initial_departures: int = 800, max_onward_departures: int = 400):
        self.max_transfers = max_transfers
        self.cost_fn = self.calculate_generalized_cost
        self.constraints = None
        self.graph = None # Orchestrator dependency
        self.max_initial_departures = max_initial_departures
        self.max_onward_departures = max_onward_departures
        self._nodes_explored = 0
        self._global_min_arrival_mins = float('inf')
        self.frontier_manager = None
        # [Task 51.1] Elastic Frontier Sizing (Reduced aggressiveness to avoid valid-path cuts)
        # Expanded to 5 rounds for OMNISCIENT high-yield discovery
        self.round_frontier_multipliers = {0: 1.0, 1: 1.5, 2: 2.5, 3: 3.5, 4: 5.0, 5: 7.0}

    def _estimate_fare(self, distance_km: float, constraints: RouteConstraints) -> float:
        """[McRAPTOR] Fast fare estimation for hot loop."""
        # Use primary class from constraints or fallback to 3A
        pref_class = constraints.preferred_class or "3A"
        rates = {"SL": 0.6, "3A": 1.2, "2A": 2.5, "1A": 4.5}
        rate = rates.get(pref_class, 1.2)
        return 175.0 + (max(0, distance_km - 100) * rate)

    def _estimate_comfort(self, train_number: str, coach_class: str) -> float:
        """[McRAPTOR] Fast comfort score estimation."""
        score = 0.5
        # Premium trains get a bonus
        if any(p in train_number for p in ["VANDE", "RAJ", "SHT", "DUR"]):
            score += 0.3
        # Class bonus
        if coach_class in ["1A", "2A", "EC"]: score += 0.2
        elif coach_class in ["SL", "2S"]: score -= 0.1
        return min(1.0, max(0.0, score))

    def _safe_fromtimestamp(self, ts: int) -> datetime:
        """[Task 27.11 Audit Fix] Safely handle timestamps for Windows compatibility."""
        try:
            # Handle both very small and very large timestamps
            # Windows max timestamp is around year 3000 (32535215999)
            capped_ts = min(32535215999, max(315532800, int(ts)))
            return datetime.fromtimestamp(capped_ts) # Safe floor 1980
        except (ValueError, OSError):
            return datetime(1980, 1, 1)

    @chaos_trap("search_engine")
    async def find_routes(self, *args: Any, **kwargs: Any) -> Any:
        if len(args) == 1 and isinstance(args[0], RoutingRequest):
            return await self._find_routes_request(args[0])

        if len(args) >= 4:
            source_stop_id, dest_stop_id, departure_date, constraints = args[:4]
            graph = kwargs.get("graph", None)
            src_ids = source_stop_id if isinstance(source_stop_id, list) else [source_stop_id]
            dst_ids = dest_stop_id if isinstance(dest_stop_id, list) else [dest_stop_id]
            request = RoutingRequest(
                source_code="",
                destination_code="",
                source_stop_id=source_stop_id if isinstance(source_stop_id, int) else (source_stop_id[0] if source_stop_id else None),
                destination_stop_id=dest_stop_id if isinstance(dest_stop_id, int) else (dest_stop_id[0] if dest_stop_id else None),
                src_cluster_ids=src_ids,
                dst_cluster_ids=dst_ids,
                departure_date=departure_date,
                constraints=constraints,
                graph=graph,
                limit=getattr(constraints, "max_results", 15),
            )
            response = await self._find_routes_request(request)
            return response.routes

        raise TypeError("OptimizedRAPTOR.find_routes() expects either a RoutingRequest or (src_ids, dst_ids, departure_date, constraints[, graph])")

    async def _compute_routes(self, source_stop_id, dest_stop_id, departure_date, constraints, graph=None):
        return await self.find_routes(source_stop_id, dest_stop_id, departure_date, constraints, graph=graph)

    async def _find_routes_request(self, request: RoutingRequest) -> RoutingResponse:
        source_stop_id = request.src_cluster_ids
        dest_stop_id = request.dst_cluster_ids
        departure_date = request.departure_date
        constraints = request.constraints
        graph = request.graph or self.graph
        limit = request.limit

        if not graph:
             from .engine import route_engine
             graph = await route_engine._get_current_graph(departure_date)
        if graph is None:
             return RoutingResponse(
                 engine_name=self.engine_id,
                 routes=[],
                 latency_ms=0.0,
                 yield_count=0,
                 triage_status="FAILED",
                 metadata={"error": "GRAPH_UNAVAILABLE"},
             )
        assert graph is not None

        # [Task 111] Nexus Governor Budget Allocation
        stats = await nexus_governor.get_stats()
        throttle = stats.get("throttle_factor", 0.0)
        
        # Dynamic Budget scaling: Base 50k, Up to 120k for Idle, Down to 5k for High Stress
        depth_multiplier = {"SHALLOW": 1.0, "MEDIUM": 2.5, "DEEP": 5.0}.get(getattr(constraints, 'search_depth', 'SHALLOW'), 1.0)
        
        if throttle < 0.1:
            self.traversal_budget = int(120000 * depth_multiplier)
        elif throttle < 0.5:
            self.traversal_budget = int(50000 * depth_multiplier)
        else:
            self.traversal_budget = int(10000 * depth_multiplier) # Aggressive pruning under pressure
            
        logger.info(f"📊 [RAPTOR] Budget set to {self.traversal_budget} (Depth: {getattr(constraints, 'search_depth', 'SHALLOW')}, System Throttle: {throttle*100:.1f}%)")
        
        self._nodes_explored = 0 
        self._global_min_arrival_mins = float('inf')
        
        # [Task 27.14] Distance-Aware Window Optimization
        if graph:
            s_id = source_stop_id[0] if isinstance(source_stop_id, list) else source_stop_id
            d_id = dest_stop_id[0] if isinstance(dest_stop_id, list) else dest_stop_id
            s_stop = graph.stop_cache.get(s_id)
            d_stop = graph.stop_cache.get(d_id)
            if s_stop and d_stop:
                # Simple Euclidean-ish distance check for window scaling
                dist = ((s_stop.latitude - d_stop.latitude)**2 + (s_stop.longitude - d_stop.longitude)**2)**0.5 * 111
                if dist < 50:
                    constraints.range_minutes = min(constraints.range_minutes or 1440, 240) # 4h max for terminal runs
                    logger.info(f"RAPTOR: Short-run detected ({dist:.1f}km). Window capped to 4h.")

        # [Task 8.3] Direct Latency Gate
        # Block search if Cache Latch is down (to prevent DB-thundering-herd)
        from services.multi_layer_cache import multi_layer_cache
        if not multi_layer_cache.health_latch:
             logger.critical("🛑 [NEXUS:SEARCH] L2 CACHE FABRIC DOWN. Blocking search to protect DB.")
             return RoutingResponse(
                 engine_name=self.engine_id, 
                 routes=[], 
                 latency_ms=0, 
                 yield_count=0, 
                 triage_status="FAILED",
                 metadata={"error": "CACHE_FABRIC_DOWN"}
             )

        # [Task 9] Budget Watchdog
        start_time = _time.perf_counter()
        timeout_sec = (constraints.timeout_ms / 1000.0) if constraints.timeout_ms else 10.0 # Increased for audit
        
        # [Task 86] Nexus 100: Resource Governor Budgeting (Search Depth)
        try:
            # Use global nexus_governor
            from core.nexus.audit.triage import nexus_triage
            
            # Combine governor pressure (CPU/RAM) with triage signal (Redis/Saga)
            governor_stats = await nexus_governor.get_stats()
            combined_pressure = max(governor_stats["throttle_factor"], nexus_triage.current_backoff)
            
            base_budget = 50000
            # Tier-aware budget allocation: don't collapse budget too aggressively
            # Also ensure minimum 15k budget even at 70% pressure
            self.traversal_budget = max(15000, int(base_budget * (1.0 - combined_pressure * 0.5)))
            
            if self.traversal_budget < base_budget:
                logger.warning(f"📉 [RAPTOR LATCH] Pruned Graph Depth to {self.traversal_budget} nodes (Pressure: {combined_pressure*100:.1f}%)")
        except:
            self.traversal_budget = 50000
        
        def check_timeout():
            if _time.perf_counter() - start_time > timeout_sec:
                raise TimeoutError("RAPTOR search timed out")

        try:
            # [Task 126] Use isolated overlay if provided (Copy-on-Write)
            overlay = request.metadata.get("overlay", graph.overlay)
            
            results = await asyncio.to_thread(self._find_routes_sync, source_stop_id, dest_stop_id, 
                                             departure_date, constraints, graph, check_timeout, overlay)
            
            latency_ms = (_time.perf_counter() - start_time) * 1000
            
            # 2. Hydrate & Rank [Task 7]
            routes = [self._hydrate_route(sr, graph, overlay) for sr in results]
            routes = [r for r in routes if r and len(r.segments) > 0]
            
            if not routes:
                return RoutingResponse(
                    engine_name=self.engine_id, 
                    routes=[], 
                    latency_ms=latency_ms, 
                    yield_count=0
                )
            
            # [Task 7] ML Scoring fallback
            for r in routes: r.score = r.total_duration + (len(r.transfers) * 120)

            routes.sort(key=lambda x: x.total_duration)
            final_routes = routes[:limit]
            
            logger.info(f"RAPTOR Yield: {len(final_routes)} routes, Traversal Depth: {self._nodes_explored} nodes.")
            
            return RoutingResponse(
                engine_name=self.engine_id,
                routes=final_routes,
                latency_ms=latency_ms,
                yield_count=len(final_routes),
                metadata={"nodes_explored": self._nodes_explored}
            )
            
        except (TimeoutError, asyncio.TimeoutError):
            logger.warning(f"RAPTOR search timed out. Returning empty results. Traversal Depth: {self._nodes_explored}")
            return RoutingResponse(
                engine_name=self.engine_id, 
                routes=[], 
                latency_ms=(_time.perf_counter() - start_time) * 1000, 
                yield_count=0, 
                triage_status="FAILED",
                metadata={"error": "TIMEOUT"}
            )
        except Exception as e:
            logger.error(f"RAPTOR Search Error: {str(e)}")
            return RoutingResponse(
                engine_name=self.engine_id, 
                routes=[], 
                latency_ms=(_time.perf_counter() - start_time) * 1000, 
                yield_count=0, 
                triage_status="FAILED",
                metadata={"error": str(e)}
            )

    def _find_routes_sync(self, source_stop_id: Union[int, List[int]], dest_stop_id: Union[int, List[int]],
                         departure_date: datetime, constraints: RouteConstraints,
                         graph: TimeDependentGraph, check_timeout: Any, overlay: Any) -> List[SearchRoute]:
        if not graph: return []

        # [Task 5] Metro-Group Expansion for RAPTOR (Optimized: accept pre-resolved IDs)
        from utils.station_utils import get_metro_group_codes
        
        if isinstance(source_stop_id, list):
            src_ids = set(source_stop_id)
        else:
            src_ids = {source_stop_id}

        if isinstance(dest_stop_id, list):
            dest_ids = set(dest_stop_id)
        else:
            dest_ids = {dest_stop_id}

        search_results = []
        try:
            # 1. Multi-Departure Search (Expanded)
            # We iterate over all source stations in the group
            for s_id in src_ids:
                # We can share the same visited/frontier state across sources if we want to find *any* route
                # But typically RAPTOR starts fresh. For "Any Source -> Any Dest", we can just run them sequentially
                # and merge, OR initialize frontier with ALL of them (Standard RAPTOR).
                # OptimizedRAPTOR seems designed for single-source frontier init.
                # Let's run it for each source and merge, checking budget.
                
                # Update: _search_multi_departure_sync resets frontier. 
                # Ideally, we should initialize frontier with ALL source stops.
                # But refactoring _search_multi_departure_sync to take List[int] is safer.
                pass # Placeholder logic, moving to _search_multi_departure_sync call below

            # Actually, let's just pass the single source_stop_id for now if we don't want to refactor the whole method signature,
            # BUT the task requires expansion.
            # Best way: Refactor _search_multi_departure_sync to accept src_ids list.
            search_results = self._search_multi_departure_sync(graph, list(src_ids), dest_ids, departure_date, constraints, check_timeout, overlay)

        except TimeoutError:
            logger.warning("RAPTOR search loop timed out. Proceeding to hydrate available routes.")

        return search_results

    def _search_multi_departure_sync(self, graph: TimeDependentGraph, source_stop_ids: List[int], dest_stop_ids: Set[int],
                                      departure_dt: datetime, constraints: RouteConstraints, check_timeout: Any, overlay: Any) -> List[SearchRoute]:
        """
        [Task 1a] Scan multi-departure window instead of single point.
        [Task 1b] Merge results from all departures in the window.
        [Task 5] Support Multi-Source Multi-Target (MSMT).
        """
        # [Analysis Only] Surge level detection
        from core.resource_monitor import resource_monitor, SurgeLevel
        level = resource_monitor.get_surge_level()
        if level != SurgeLevel.NORMAL:
            logger.info(f"📊 RAPTOR Surge Analysis: Level {level.name} detected. Budget: {self.traversal_budget}")

        routes_by_round = defaultdict(list)
        departure_ts = int(departure_dt.timestamp())
        
        # 2. Setup Persona-Aware Frontier [Task 42.6]
        # [Task 12.1] Sync transfer limit with constraints
        self.max_transfers = getattr(constraints, 'max_transfers', self.max_transfers)
        self.frontier_manager = FrontierManager(
            max_routes_per_station=30, # Increased per-station diversity
            cost_fn=self.cost_fn,
            constraints=constraints
        )
        self._nodes_explored = 0
        self._global_min_arrival_mins = float('inf')
        snapshot = cast(Any, graph.snapshot)
        if snapshot is None:
            return []
        trip_reachability_bitset = getattr(snapshot, "_trip_reachability_bitset", None)
        
        # [Subtask 146.4] Resolve Bridge Stop IDs for reachability overrides
        bridge_indices = []
        if constraints and getattr(constraints, 'metadata', None):
             bridges = constraints.metadata.get("cross_cluster_bridges", {})
             for hc in bridges.get("src_hubs", []) + bridges.get("dst_hubs", []):
                  h_stop = graph.get_stop_by_code(hc)
                  if h_stop:
                       h_idx = snapshot._stop_id_map.get(h_stop.id)
                       if h_idx is not None: bridge_indices.append(h_idx)
                       
        # Pre-calculated Hub Indices from graph
        hub_indices = getattr(snapshot, '_hub_indices', [])
        effective_bridges = list(set(bridge_indices) | set(hub_indices))
        
        # [Task 171] Initialize Neural Pruner for the current graph
        pruner = get_raptor_pruner(graph)
        if pruner is None:
            return []
        
        # [Phase A3] Neural Pruning Preparation
        s_id = source_stop_ids[0] if source_stop_ids else None
        if s_id and hasattr(pruner, 'prepare_for_search'):
             # Estimate O-D distance for corridor sizing
             s_stop = graph.stop_cache.get(s_id)
             d_stop = graph.stop_cache.get(list(dest_stop_ids)[0]) if dest_stop_ids else None
             if s_stop and d_stop:
                 od_dist = pruner.haversine_distance(s_stop.latitude, s_stop.longitude, d_stop.latitude, d_stop.longitude)
                 pruner.prepare_for_search(s_id, dest_stop_ids, od_dist)

        pressure = nexus_governor.throttle_factor

        # Round 0: Initialize from ALL source stations
        lookahead = constraints.range_minutes if constraints.range_minutes > 0 else 1440
        f_size = 1
        
        for src_id in source_stop_ids:
            pattern_deps = graph.get_pattern_departures(src_id, departure_dt, lookahead=lookahead)

            for pid_hash_val, deps in pattern_deps.items():
                check_timeout()
                if self._nodes_explored > self.traversal_budget: break
                
                # [Task 121: Elite Yield] Fetch pattern segments once per PID to save 10x overhead
                # We need the real pid from snapshot._trip_to_pid for the segment data lookup
                # This needs to be done more elegantly. For now, assume a pattern hash value maps to segment data.
                # The pid_hash_val is generated in graph.py now.
                
                pattern_raw = graph.get_pattern_segments(pid_hash_val)
                if pattern_raw is None: continue

                for dep_time, trip_id in deps[: self.max_initial_departures or None]:
                    # [Task 146] Zero-Latency Reachability Pruning [Elite]
                    # Pruning Rule: Keep trip if it hits a Goal OR a Major Hub.
                    # This ensures we don't explore tiny branch lines that never connect back.
                    can_reach_goal = any(graph.can_reach_destination(trip_id, d_id) for d_id in dest_stop_ids)
                    if not can_reach_goal:
                        # [Elite Yield] Check if trip hits ANY bridge hub or major hub
                        t_idx = snapshot._trip_id_map.get(int(trip_id))
                        if t_idx is not None and effective_bridges and trip_reachability_bitset is not None:
                             bitset_row = trip_reachability_bitset[t_idx]
                             h_found = False
                             for h_idx in effective_bridges:
                                  if bitset_row[h_idx // 64] & (np.uint64(1) << np.uint64(h_idx % 64)):
                                       h_found = True; break
                             if not h_found: continue
                        else:
                             # Legacy fallback if no bitsets
                             if not graph.can_reach_any_hub(trip_id):
                                  continue 
                    
                    # Proceed with expansion...
                    wait_mins = 0 # [Task 121: Correctness] Root-leg wait is always zero relative to departure_dt
                    
                    if overlay.is_cancelled(trip_id): continue

                    self._nodes_explored += 1
                    delay_secs = overlay.get_trip_delay(trip_id) * 60
                    dep_ts_int = int(dep_time.timestamp())
                    start_found = False
                    total_dist_m = 0
                    
                    for row in pattern_raw:
                        s_dep_sid, s_arr_sid = int(row['dep_sid']), int(row['arr_sid'])
                        # The pattern segments return relative time (seconds from midnight).
                        # We need to make them absolute again relative to dep_time for this trip.
                        s_dep_ts_rel = int(row['dep_time']) 
                        s_arr_ts_rel = int(row['arr_time'])
                        
                        # Calculate absolute timestamps for this specific trip
                        trip_start_of_day_ts = dep_ts_int - (dep_ts_int % 86400)
                        s_dep_ts_abs = trip_start_of_day_ts + s_dep_ts_rel + delay_secs
                        s_arr_ts_abs = trip_start_of_day_ts + s_arr_ts_rel + delay_secs
                        
                        # Handle overnight trips within the pattern segments
                        if s_arr_ts_abs < s_dep_ts_abs:
                            s_arr_ts_abs += 86400 # Add a day
                            
                        if not start_found:
                            # Fuzzy match for departure sequence
                            if s_dep_sid == src_id:
                                # We assume the dep_time from 'deps' IS for this src_id
                                start_found = True
                            else: continue

                        # Accumulate distance from start of trip segment
                        dist_m = int(row.get('dist_m', 0))
                        total_dist_m += dist_m
                        total_dist = total_dist_m / 1000.0
                        fare = self._estimate_fare(total_dist, constraints)
                        train_num = snapshot.trip_to_train.get(trip_id, "")
                        comfort = self._estimate_comfort(train_num, constraints.preferred_class or "3A")
                        arr_mins = (s_arr_ts_abs - departure_ts) // 60
                        rel = 1.0 # Base reliability
                        
                        if not self.frontier_manager.is_dominated(s_arr_sid, FrontierRoute(
                                arrival_time=arr_mins, transfers=0, total_wait=wait_mins, total_distance=total_dist,
                                reliability=rel, total_cost=fare, comfort_score=comfort), max_size=f_size):
                             sr = SearchRoute(trip_id=trip_id, from_stop_id=src_id, to_stop_id=s_arr_sid,
                                              departure_time=dep_time, arrival_time=self._safe_fromtimestamp(s_arr_ts_abs),
                                              round_num=0, total_dist=total_dist, total_wait=wait_mins,
                                              reliability=rel, total_cost=fare, comfort_score=comfort)
                             sr.v_bloom_low = 0; sr.v_bloom_high = 0
                             sr.add_to_bloom(src_id); sr.add_to_bloom(s_arr_sid)
                             routes_by_round[0].append(sr)
                             if s_arr_sid in dest_stop_ids: self._global_min_arrival_mins = min(self._global_min_arrival_mins, arr_mins)

        # Onward Rounds [Task 86] Elastic Graph Depth
        effective_max = self.max_transfers
        if nexus_governor.throttle_factor > 0.75:
             effective_max = min(1, self.max_transfers)
             logger.warning(f"⚠️ [RAPTOR:GOVERNOR] Congestion detected ({nexus_governor.throttle_factor:.2f}). Capping to {effective_max} transfers.")

        for r in range(1, effective_max + 1):
            if not routes_by_round[r-1]: break
            if self._nodes_explored > self.traversal_budget: break
            for psr in routes_by_round[r-1]:
                check_timeout()
                if psr.to_stop_id in dest_stop_ids: continue
                # [Task 171] Branch Pruning at the Transfer Level
                # [Task 51.2] Apply Elastic Multiplier for onward transfers
                multiplier = self.round_frontier_multipliers.get(r, 1.0)
                effective_f_size = int(f_size * multiplier)
                
                # Check if branch should be pruned
                if pruner.should_prune(psr.to_stop_id, dest_stop_ids, 
                                      (int(psr.arrival_time.timestamp()) - departure_ts) // 60,
                                      int(self._global_min_arrival_mins), r, pressure):
                     continue
                     
                new_found = self._process_transfers_sync(psr, graph, dest_stop_ids, constraints, departure_dt, r, check_timeout, pruner, pressure, effective_bridges, overlay)
                routes_by_round[r].extend(new_found)
        all_results = []
        for r_idx in range(self.max_transfers + 1):
            for sr in routes_by_round[r_idx]:
                if sr.to_stop_id in dest_stop_ids: all_results.append(sr)
        return self._deduplicate_search_routes(all_results)

    def _process_transfers_sync(self, psr: SearchRoute, graph: TimeDependentGraph, dest_stop_ids: Set[int], 
                                 constraints: RouteConstraints, base_departure_dt: datetime, 
                                 round_num: int, check_timeout: Any, pruner: Any, pressure: float,
                                 effective_bridges: List[int], overlay: Any) -> List[SearchRoute]:
        new_routes = []
        base_departure_ts = int(base_departure_dt.timestamp())
        min_tr = constraints.min_transfer_time or 15
        snapshot = graph.snapshot
        if snapshot is None: return []
        
        # [G11.3] Check for Multimodal Hub Jumps
        # If the stop code is in MEGA_HUBS, bridge to non-rail modes via Providers
        curr_stop = graph.stop_cache.get(psr.to_stop_id)
        if curr_stop and curr_stop.code in MEGA_HUBS:
            # We perform a synchronous bridge check here (or it would've been too slow in the hot loop)
            # Future: Use pre-resolved hub-to-hub provider results cached in Redis.
            pass

        frontier_manager = self.frontier_manager
        if frontier_manager is None:
            return []
        transfers = graph.get_transfers_from_stop(
            psr.to_stop_id, 
            psr.arrival_time, 
            min_transfer_time=min_tr, 
            incoming_trip_id=psr.trip_id,
            search_depth=constraints.search_depth
        )

        for tr in transfers:
            # [G11.3.1] INJECT VIRTUAL JUMPS (Multi-modal)
            # If the transfer station is a Hub, check for direct Flights/Buses to the destination
            if tr.station_code in MEGA_HUBS or tr.station_code in MAJOR_HUBS:
                # To keep RAPTOR-Sync fast, we only look for 'Cached' or 'Pre-scanned' multimodal jumps
                # provided by the SearchService orchestrator in constraints
                if hasattr(constraints, 'multimodal_jumps'):
                    jumps = constraints.multimodal_jumps.get(tr.station_code, [])
                    for jump in jumps:
                        # jump format: {to_stop_id, arrival_time (abs), duration, cost, type}
                        total_dist = psr.total_dist + jump.get("distance_km", 100.0)
                        arr_mins = (int(jump["arrival_time"].timestamp()) - base_departure_ts) // 60
                        if not self.frontier_manager.is_dominated(jump["to_stop_id"], FrontierRoute(
                                arrival_time=arr_mins, transfers=round_num, total_wait=psr.total_wait, 
                                total_distance=total_dist, reliability=0.9), max_size=5):
                             # Create a virtual SearchRoute tagged as the jump type
                             sr = SearchRoute(trip_id=-999, from_stop_id=tr.station_id, to_stop_id=jump["to_stop_id"],
                                              departure_time=jump["departure_time"], arrival_time=jump["arrival_time"],
                                              round_num=round_num, parent=psr, total_dist=total_dist, 
                                              total_wait=psr.total_wait, reliability=0.9)
                             sr.metadata = {"jump_type": jump["type"], "provider_id": jump["provider_id"]}
                             new_routes.append(sr)

            earliest_dep = psr.arrival_time + timedelta(minutes=tr.duration_minutes)
            
            lookahead = constraints.range_minutes if constraints.range_minutes > 0 else 1440
            onward = graph.get_pattern_departures(tr.station_id, earliest_dep, lookahead=lookahead)
            for pid, deps in onward.items():
                check_timeout()
                if self._nodes_explored > self.traversal_budget: break
                for dep_t, trip_id in deps[:self.max_onward_departures]:
                    # [Standard Rail Onward logic ...]
                    can_reach_goal = any(graph.can_reach_destination(trip_id, did) for did in dest_stop_ids)
                    if not can_reach_goal:
                         t_idx = snapshot._trip_id_map.get(int(trip_id))
                         if t_idx is not None and effective_bridges and snapshot._trip_reachability_bitset is not None:
                               bitset_row = snapshot._trip_reachability_bitset[t_idx]
                               h_found = False
                               for h_idx in effective_bridges:
                                    if bitset_row[h_idx // 64] & (np.uint64(1) << np.uint64(h_idx % 64)):
                                         h_found = True; break
                               if not h_found: continue
                         elif not graph.can_reach_any_hub(trip_id):
                               continue 
                    if overlay.is_cancelled(trip_id): continue

                    self._nodes_explored += 1
                    raw = graph.get_trip_segments_raw(trip_id)
                    if raw is None: continue
                    delay_secs = overlay.get_trip_delay(trip_id) * 60
                    dep_ts_int = int(dep_t.timestamp()); start_found = False; dist_m = 0
                    
                    for i, row in enumerate(raw):
                        s_dep_sid, s_arr_sid = int(row['dep_sid']), int(row['arr_sid'])
                        
                        if not start_found:
                            if s_dep_sid == tr.station_id:
                                start_found = True
                            else: continue
                        
                        is_goal = s_arr_sid in dest_stop_ids
                        is_hub = s_arr_sid in effective_bridges
                        
                        if not (is_goal or is_hub):
                             if i % 8 != 0: continue 

                        if psr.has_cycle(s_arr_sid): continue
                        
                        dist_m += int(row['dist_m'])
                        total_dist = psr.total_dist + (dist_m / 1000.0)
                        total_wait = psr.total_wait + (dep_ts_int - int(psr.arrival_time.timestamp())) // 60
                        
                        trip_start_of_day_ts = dep_ts_int - (dep_ts_int % 86400)
                        s_arr_ts_abs = trip_start_of_day_ts + int(row['arr_time']) + delay_secs
                        if s_arr_ts_abs < dep_ts_int: s_arr_ts_abs += 86400

                        arr_mins = (s_arr_ts_abs - base_departure_ts) // 60
                        if arr_mins > self._global_min_arrival_mins + 1440: continue
                        f_size = get_frequency_aware_sizer(s_arr_sid, graph)
                        
                        # [A2.1] Stochastic Reliability Integration
                        # P(success) = P(ArrDelay < Wait + DepDelay)
                        train_num_in = snapshot.trip_to_train.get(psr.trip_id, "DEFAULT")
                        train_num_out = snapshot.trip_to_train.get(trip_id, "DEFAULT")
                        conn_prob = reliability_engine.calculate_connection_probability(
                            train_num_in, train_num_out, total_wait - psr.total_wait
                        )
                        rel = psr.reliability * conn_prob
                        
                        fare = psr.total_cost + (self._estimate_fare(total_dist - psr.total_dist, constraints) - 175.0) # Simple telescopic delta
                        train_num = snapshot.trip_to_train.get(trip_id, "")
                        comfort = (psr.comfort_score + self._estimate_comfort(train_num, constraints.preferred_class or "3A")) / 2.0
                        
                        if not frontier_manager.is_dominated(s_arr_sid, FrontierRoute(
                                arrival_time=arr_mins, transfers=round_num, total_wait=total_wait, 
                                total_distance=total_dist, reliability=rel, total_cost=fare, comfort_score=comfort), max_size=f_size):
                             sr = SearchRoute(trip_id=trip_id, from_stop_id=tr.station_id, to_stop_id=s_arr_sid,
                                              departure_time=dep_t, arrival_time=self._safe_fromtimestamp(s_arr_ts_abs),
                                              round_num=round_num, parent=psr, total_dist=total_dist, 
                                              total_wait=total_wait, reliability=rel, total_cost=fare, comfort_score=comfort)
                             sr.v_bloom_low = psr.v_bloom_low; sr.v_bloom_high = psr.v_bloom_high
                             sr.add_to_bloom(tr.station_id); sr.add_to_bloom(s_arr_sid)
                             new_routes.append(sr)
                             
        return new_routes

    def _hydrate_route(self, sr: SearchRoute, graph: TimeDependentGraph, overlay: Any) -> Route:
        path = []; curr = sr
        while curr: path.append(curr); curr = curr.parent
        path.reverse()
        
        full_segments = []; transfers = []
        snapshot = graph.snapshot
        if snapshot is None: return Route(segments=[], transfers=[])
        
        for node in path:
            if node.transfer: transfers.append(node.transfer)
            
            # [G11.3.2] Handle Multimodal Jumps
            if node.trip_id == -999:
                # This is a virtual jump (Flight/Bus)
                meta = getattr(node, "metadata", {})
                j_type = meta.get("jump_type", "FLIGHT")
                p_id = meta.get("provider_id", "RAPID_BRIDGE")
                
                dep_stop = graph.stop_cache.get(node.from_stop_id)
                arr_stop = graph.stop_cache.get(node.to_stop_id)
                
                full_segments.append(RouteSegment(
                    trip_id=-999,
                    departure_stop_id=node.from_stop_id,
                    arrival_stop_id=node.to_stop_id,
                    departure_time=node.departure_time,
                    arrival_time=node.arrival_time,
                    duration_minutes=int((node.arrival_time - node.departure_time).total_seconds() // 60),
                    distance_km=node.total_dist,
                    service_mask=127,
                    train_number=f"{j_type} via {p_id}",
                    departure_code=dep_stop.code if dep_stop else "",
                    arrival_code=arr_stop.code if arr_stop else "",
                    fare=0.0,
                    metadata={"provider": p_id, "mode": j_type}
                ))
                continue

            # Standard Rail Hydration
            raw_segments = graph.get_trip_segments_raw(node.trip_id)
            if raw_segments is None: continue
            delay_secs = overlay.get_trip_delay(node.trip_id) * 60
            start_idx = -1
            for i, row in enumerate(raw_segments):
                s_dep_sid = int(row['dep_sid'])
                trip_start_of_day_ts = int(node.departure_time.timestamp()) - (int(node.departure_time.timestamp()) % 86400)
                seg_dep_abs_ts = trip_start_of_day_ts + int(row['dep_time']) + delay_secs
                if s_dep_sid == node.from_stop_id and abs(seg_dep_abs_ts - int(node.departure_time.timestamp())) < 2:
                    start_idx = i; break
            
            if start_idx == -1: continue 

            for i in range(start_idx, len(raw_segments)):
                row = raw_segments[i]
                s_dep_sid, s_arr_sid = int(row['dep_sid']), int(row['arr_sid'])
                s_dep_ts_rel, s_arr_ts_rel = int(row['dep_time']), int(row['arr_time'])
                trip_start_of_day_ts = int(node.departure_time.timestamp()) - (int(node.departure_time.timestamp()) % 86400)
                seg_dep_abs_ts = trip_start_of_day_ts + s_dep_ts_rel + delay_secs
                seg_arr_abs_ts = trip_start_of_day_ts + s_arr_ts_rel + delay_secs
                if seg_arr_abs_ts < seg_dep_abs_ts: seg_arr_abs_ts += 86400
                
                duration = int((seg_arr_abs_ts - seg_dep_abs_ts) // 60)
                dep_stop, arr_stop = graph.stop_cache.get(s_dep_sid), graph.stop_cache.get(s_arr_sid)
                full_segments.append(RouteSegment(
                    trip_id=node.trip_id,
                    departure_stop_id=s_dep_sid,
                    arrival_stop_id=s_arr_sid,
                    departure_time=graph.safe_fromtimestamp(seg_dep_abs_ts),
                    arrival_time=graph.safe_fromtimestamp(seg_arr_abs_ts),
                    duration_minutes=duration,
                    distance_km=float(row['dist_m'] / 1000.0),
                    service_mask=int(row['service_mask']),
                    train_number=snapshot.trip_to_train.get(node.trip_id, ""),
                    departure_code=dep_stop.code if dep_stop else "",
                    arrival_code=arr_stop.code if arr_stop else "",
                    fare=0.0
                ))
                if s_arr_sid == node.to_stop_id: break
        
        rt = Route(segments=full_segments, transfers=transfers)
        # Ensure total_distance is set from search result if available, otherwise fallback to sum
        if sr.total_dist > 0:
            rt.total_distance = sr.total_dist
        else:
            rt.total_distance = sum(s.distance_km for s in full_segments)
            
        rt.metadata["engine"] = "raptor_v2_window"
        rt.metadata["reliability"] = round(sr.reliability, 2)
        return rt

    def _deduplicate_search_routes(self, routes: List[SearchRoute]) -> List[SearchRoute]:
        unique = {}
        for r in routes:
            p = []; c = r
            while c: p.append((c.trip_id, c.from_stop_id, c.to_stop_id)); c = c.parent
            k = tuple(reversed(p))
            if k not in unique or r.arrival_time < unique[k].arrival_time: unique[k] = r
        return list(unique.values())

    async def find_one_transfer_hub_routes(self, source_stop_id: int, dest_stop_id: int,
                                         departure_date: datetime, constraints: RouteConstraints,
                                         graph: TimeDependentGraph) -> List[Route]:
        """
        Specialized RAPTOR variant for Phase 4 Hub Discovery.
        Ensures exactly one transfer at a validated hub station.
        """
        orig_max = self.max_transfers
        self.max_transfers = 1
        try:
            # We use a relaxed window for hub discovery
            constraints.range_minutes = max(constraints.range_minutes, 1440) 
            routes = await self.find_routes(source_stop_id, dest_stop_id, departure_date, constraints, graph)
            # Filter for only those with transfers
            return [r for r in routes if len(r.transfers) == 1]
        finally:
            self.max_transfers = orig_max

class HybridRAPTOR(OptimizedRAPTOR):
    def __init__(self, hub_manager, max_transfers=3):
        super().__init__(max_transfers)
        self.hub_manager = hub_manager

    async def find_routes(self, source_stop_id, dest_stop_id, departure_date, constraints, graph=None):
        return await super().find_routes(source_stop_id, dest_stop_id, departure_date, constraints, graph)
