import asyncio
import logging
import time
import struct
import json
from typing import List, Dict, Any, Optional, Callable, Set
from datetime import datetime, timedelta
from sqlalchemy import text

from .base import BaseRoutingEngine, RoutingRequest, RoutingResponse
from .constraints import RouteConstraints
from core.data_structures import Route, RouteSegment, TransferConnection, Persona
from .turbo_router import TurboRouter
from .ultra_turbo import UltraTurboDirectEngine
from .raptor import OptimizedRAPTOR
from .fast_router import FastPathRouter
from .hub_router import HubRoutingEngine
from .scoring import RouteScorer
from .hydration import create_default_pipeline
from .circuit_breaker import EngineCircuitBreaker
from .throttler import EngineThrottler
from core.pricing.fare_calculator import calculate_fare

from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import os

_cpu_executor = None

def get_cpu_executor():
    global _cpu_executor
    if _cpu_executor is None:
        _cpu_executor = ProcessPoolExecutor(
            max_workers=max(2, (os.cpu_count() or 4) // 2)
        )
    return _cpu_executor

# Standard ThreadPool for I/O and lightweight concurrent logic
import os
workers = min(4, (os.cpu_count() or 4))
ROUTING_POOL = ThreadPoolExecutor(
    max_workers=workers,
    thread_name_prefix="routing_io_worker"
)

logger = logging.getLogger(__name__)

class ProgressTracker:
    """[Task 22.7] Simple progress tracking for TaskGroup."""
    def __init__(self, total_tasks: int, callback: Optional[Callable[[float], None]] = None):
        self.total = total_tasks
        self.completed = 0
        self.callback = callback

    def update(self):
        self.completed += 1
        if self.callback:
            progress = (self.completed / self.total) * 100
            self.callback(progress)

class HydrationPipeline:
    """[Task 28.1] Modular pipeline for route result hydration."""
    def __init__(self):
        self.steps: List[Callable] = []

    def add_step(self, step: Callable):
        self.steps.append(step)

    async def execute(self, routes: List[Route], constraints: RouteConstraints, graph: Any, db: Any):
        for step in self.steps:
            st = time.perf_counter()
            if asyncio.iscoroutinefunction(step):
                await step(routes, constraints, graph, db)
            else:
                step(routes, constraints, graph, db)
            lat = (time.perf_counter() - st) * 1000
            for r in routes:
                if "hydration_stats" not in r.metadata: r.metadata["hydration_stats"] = {}
                r.metadata["hydration_stats"][step.__name__] = round(lat, 2)


class UnifiedRoutingOrchestrator:
    """
    10X Performance Orchestrator.
    Manages Tiered Routing:
    - Tier 0: Backbone (Hub-to-Hub)
    - Tier 1: Turbo (SQL Direct/1-T)
    - Tier 2: FastPath (O(1) BFS 2-T)
    - Tier 3: RAPTOR (Discovery)
    """
    _global_resource_sem = asyncio.Semaphore(10)

    def get_health(self) -> Dict[str, Any]:
        """[Task 40.3 / 41.9] High-Efficiency Health Metrics for VPS monitoring."""
        return {
            "circuits": {name: circuit.get_stats() for name, circuit in self.circuits.items()},
            "throttlers": {name: th.get_stats() for name, th in self.throttlers.items()},
            "engines_registered": list(self.engines.keys())
        }

    def __init__(self, route_engine_instance):
        from .tbr_router import TripBasedRouter # [Task 27.17]
        self.engine = route_engine_instance
        self.engines: Dict[str, BaseRoutingEngine] = {
            "hub_tier_0": HubRoutingEngine(),
            "ultra_turbo_direct": UltraTurboDirectEngine(),
            "turbo_router": TurboRouter(),
            "fastpath_bfs": FastPathRouter(None),
            "raptor": OptimizedRAPTOR(),
            "trip_based": TripBasedRouter()
        }
        self.hub_router = self.engines["hub_tier_0"]
        self.ultra_turbo = self.engines["ultra_turbo_direct"]
        self.turbo_router = self.engines["turbo_router"]
        self.fast_router = self.engines["fastpath_bfs"]
        self.raptor = self.engines["raptor"]
        self.tbr_router = self.engines["trip_based"] # [Task 27.17]
        
        # Initialize Hydration Pipeline from Middleware
        self.hydration_pipeline = create_default_pipeline()

        # [Task 40.2] Initialize Intelligent Circuits for VPS Stability
        self.circuits: Dict[str, EngineCircuitBreaker] = {
            name: EngineCircuitBreaker(name) for name in self.engines.keys()
        }

        # [Task 41.3] Initialize Adaptive Throttlers
        targets = {
            "hub_tier_0": 80.0,
            "ultra_turbo_direct": 120.0,
            "turbo_router": 180.0,
            "fastpath_bfs": 400.0,
            "raptor": 850.0,
            "trip_based": 1200.0
        }
        self.throttlers: Dict[str, EngineThrottler] = {
            name: EngineThrottler(name, targets.get(name, 500.0)) for name in self.engines.keys()
        }

    async def stream_all_tiers(
        self,
        request: RoutingRequest,
        skip_heavy: bool = False,
        source_stop=None,
        dest_stop=None,
        on_progress: Optional[Callable[[float], None]] = None,
        discovery_cache_key: Optional[str] = None
    ):
        """[Task 30/105] Elite Resource-Aware Streaming Orchestrator."""
        source_code = request.source_code
        destination_code = request.destination_code
        departure_date = request.departure_date
        constraints = request.constraints
        limit = request.limit
        db = request.db_session
        # [Task 122 Refined] Nexus Governor Integration
        from core.nexus.audit.governor import nexus_governor
        gov_stats = await nexus_governor.get_stats()
        
        # Determine which heavy engines to skip based on real-time system health
        skip_heavy = False
        import os
        force_heavy = os.getenv("NEXUS_FORCE_CONTINUE_ON_STRESS", "true").lower() == "true"
        max_ram = float(os.getenv("NEXUS_MAX_RAM", "95.0"))
        max_cpu = float(os.getenv("NEXUS_MAX_CPU", "90.0"))

        if not force_heavy:
            if gov_stats["cpu_percent"] > max_cpu or gov_stats["ram_percent"] > max_ram:
                skip_heavy = True
                logger.warning(
                    f"⚖️ [ORCHESTRATOR:GOVERNOR] High load detected (CPU: {gov_stats['cpu_percent']}%, RAM: {gov_stats['ram_percent']}%). "
                    "Skipping heavy engines (RAPTOR, FastPath)."
                )
        else:
            if gov_stats["cpu_percent"] > max_cpu or gov_stats["ram_percent"] > max_ram:
                logger.critical(
                    f"⚠️ [ORCHESTRATOR:ADMIN_ALERT] Resource Pressure High! (CPU: {gov_stats['cpu_percent']}%, RAM: {gov_stats['ram_percent']}%). "
                    "Proceeding with heavy engines due to NEXUS_FORCE_CONTINUE_ON_STRESS."
                )

        start_time = time.perf_counter()
        from utils.station_utils import resolve_stations

        _owned_session = False
        if db is None:
            try:
                from database.session import SessionTransit
                db = SessionTransit()
                _owned_session = True
            except Exception as e:
                logger.error(f"Orchestrator: Failed to create fallback session: {e}")
                return

        try:
            # Sync overlay & fetch cancelled
            graph = await self.engine._get_current_graph(departure_date)
            # Ensure all graph-dependent routers have the latest graph
            self.fast_router.graph = graph
            self.raptor.graph = graph 
            
            await graph.overlay.sync_with_db(db, departure_date.date(), graph.snapshot)
            date_str = departure_date.strftime("%Y-%m-%d")
            c_rows = db.execute(text("SELECT train_no FROM cancelled_trains WHERE travel_date = :dt"), {"dt": date_str}).fetchall()
            constraints.metadata = {"cancelled_trip_ids": {int(r[0]) for r in c_rows}}
            
            if not source_stop or not dest_stop:
                source_stop, dest_stop = await asyncio.to_thread(resolve_stations, db, source_code, destination_code)
            
            if not source_stop or not dest_stop: return

            # [Task 5] Metro-Group Expansion: Resolve all stations in the metropolitan area
            from utils.station_utils import get_metro_group_codes
            
            def _resolve_cluster_ids_sync(code: str, session) -> List[int]:
                if isinstance(code, int): return [code]
                c_str = str(code).upper().strip()
                codes = get_metro_group_codes(c_str)
                
                ids = set()
                q_stops = f"SELECT id FROM stops WHERE code IN ({','.join([':c'+str(i) for i in range(len(codes))])})"
                params = {f"c{i}": c for i, c in enumerate(codes)}
                for r in session.execute(text(q_stops), params).fetchall():
                    ids.add(r[0])
                if not ids: return []
                
                q_clusters = f"""
                    SELECT scm2.station_id 
                    FROM station_cluster_mapping scm1 
                    JOIN station_cluster_mapping scm2 ON scm1.cluster_id = scm2.cluster_id 
                    WHERE scm1.station_id IN ({','.join([':s'+str(i) for i in range(len(ids))])})
                """
                params_cl = {f"s{i}": sid for i, sid in enumerate(ids)}
                try:
                    for r in session.execute(text(q_clusters), params_cl).fetchall():
                        ids.add(r[0])
                except: pass # Table might not exist
                return list(ids)

            # Resolve clusters using the primary DB session
            src_cluster_ids = await asyncio.to_thread(_resolve_cluster_ids_sync, source_code, db)
            dst_cluster_ids = await asyncio.to_thread(_resolve_cluster_ids_sync, destination_code, db)
            
            if not src_cluster_ids: src_cluster_ids = [source_stop.id]
            if not dst_cluster_ids: dst_cluster_ids = [dest_stop.id]

            # Resolved codes for engines that prefer codes
            src_cluster_codes = get_metro_group_codes(source_code)
            dst_cluster_codes = get_metro_group_codes(destination_code)

            from core.context import request_timeout_ctx
            total_timeout = request_timeout_ctx.get() or 5.0
            
            engine_limit = max(limit * 2, 50) 
            # Remove global seen_jids to allow discovery-tracking per engine
            # Global dedup happens in _global_deduplicate (preserves discovered_by metadata)

            async def process_and_yield(name, coro, timeout):
                circuit = self.circuits.get(name)
                if circuit and not await circuit.can_execute():
                    logger.warning(f"🛡️ [ORCHESTRATOR] Bypassing {name} (Circuit OPEN)")
                    return []

                start_exec = time.perf_counter()
                try:
                    async with asyncio.timeout(timeout):
                        res = await coro
                    
                    if res is None: 
                        if circuit: await circuit.record_failure("Engine returned None")
                        return []
                    
                    all_raw = []
                    if name in ("Turbo", "UltraTurbo") and res and isinstance(res[0], dict):
                        # Hub/Turbo engines sometimes return raw dicts
                        raw_routes = self._hydrate_turbo_results(res, source_code, destination_code, departure_date)
                        for r in raw_routes: 
                            if "engine" not in r.metadata: r.metadata["engine"] = name.lower()
                        all_raw.extend(raw_routes)
                    else:
                        # Standard engines return Route objects
                        for r in res: 
                            if isinstance(r, Route): 
                                if "engine" not in r.metadata: r.metadata["engine"] = name.lower()
                        all_raw.extend(res)
                        
                    all_routes = [r for r in all_raw if self._is_valid_route(r)]
                    
                    # Detection of "Silent Malformation"
                    if all_raw and not all_routes:
                        if circuit: await circuit.record_failure("All results failed integrity check")
                        return []
                    
                    if circuit: await circuit.record_success()

                    all_routes = await self._filter_cancelled_trains(all_routes, request)
                    
                    # [Task 30.4] Skip streaming dedup - let global dedup handle it (preserves discovery metadata)
                    new_routes = all_routes

                    if new_routes:
                        should_hydrate = not constraints.discovery_only and gov_stats["ram_percent"] < 95
                        if should_hydrate:
                            await self.hydration_pipeline.execute(new_routes, constraints, graph, db)
                        else:
                            for r in new_routes: r.metadata["speculative"] = True
                        
                        latency_total = (time.perf_counter() - start_time) * 1000
                        for r in new_routes:
                            r.metadata["orchestrator_latency_ms"] = round(latency_total, 2)
                            r.metadata["is_hydrated"] = should_hydrate
                            if "engine" not in r.metadata: r.metadata["engine"] = name.lower()
                            if "tier" not in r.metadata:
                                if "ultra" in r.metadata["engine"]: r.metadata["tier"] = 1
                                elif "turbo" in r.metadata["engine"]: r.metadata["tier"] = 2
                                else: r.metadata["tier"] = 3
                        
                        return new_routes
                    return []

                except Exception as e:
                    if circuit: await circuit.record_failure(str(e))
                    logger.error(f" Engine {name} failed or timed out: {e}")
                    return []

        except (asyncio.TimeoutError, TimeoutError):
            logger.error(f"⌛ Orchestrator Stream Deadline Exceeded for {source_code}->{destination_code}")
        finally:
            if _owned_session and db is not None:
                try: db.close()
                except: pass

    async def _discover_from_engine_async(self, name: str, engine: BaseRoutingEngine, request: RoutingRequest, start_time: float, gov_stats: Dict):
        """[Task 41.11] Unified discovery handler with Circuit Breakers & Throttling."""
        throttler = self.throttlers.get(name)
        circuit = self.circuits.get(name)
        
        # 1. Circuit & Throttler Guards
        if circuit and not await circuit.can_execute():
            return []
            
        is_high_priority = (
            request.constraints.persona in (Persona.PREMIUM, Persona.EMERGENCY) or 
            request.constraints.quota != "GN"
        )
        if throttler and throttler.should_skip(is_premium=is_high_priority):
            logger.warning(f"🚫 [THROTTLER] Skipping {name} due to critical latency.")
            return []

        # 2. Dynamic Limit Adjustment
        engine_limit = request.limit
        if throttler:
            effective_limit = throttler.get_effective_limit(engine_limit)
            request.limit = effective_limit

        # 3. Execution & Timing
        st_task = time.perf_counter()
        try:
            resp = await engine.find_routes(request)
            lat_ms = (time.perf_counter() - st_task) * 1000
            if throttler: throttler.record_latency(lat_ms)
            if circuit: await circuit.record_success()
            
            if not resp or not resp.routes: return []
            
            # 4. Meta-tagging & Consistency
            routes = resp.routes
            for r in routes:
                if "engine" not in r.metadata: r.metadata["engine"] = name.lower()
                r.metadata["is_hydrated"] = False # discovery yield is raw
                # [Task 41.9] Latency feedback to UI
                r.metadata["engine_latency_ms"] = round(lat_ms, 1)
            
            # Post-Filter & Verification (Minimal sync check)
            all_routes = [r for r in routes if self._is_valid_route(r)]
            
            if routes and not all_routes:
                if circuit: await circuit.record_failure("Discovery produced invalid routes")
                return []
                
            return all_routes

        except Exception as e:
            if circuit: await circuit.record_failure(str(e))
            logger.error(f"❌ [ORCHESTRATOR] Engine {name} failed: {e}")
            return []

    async def search_all_tiers(
        self,
        request: RoutingRequest,
        skip_heavy: bool = False,
        source_stop=None,
        dest_stop=None,
        on_progress: Optional[Callable[[float], None]] = None 
    ) -> List[Route]:
        start_time = time.perf_counter()
        from utils.station_utils import resolve_stations
        
        source_code = request.source_code
        destination_code = request.destination_code
        departure_date = request.departure_date
        constraints = request.constraints
        limit = request.limit
        db = request.db_session

        _owned_session = False
        if db is None:
            try:
                from database.session import SessionTransit
                db = SessionTransit()
                _owned_session = True
            except Exception as e:
                logger.error(f"Orchestrator: Failed to create fallback session: {e}")
                return []

        try:
            from .graph import TimeDependentGraph
            # Sync overlay & fetch cancelled
            # [Task 1.3] Ensure overlay is fresh for all engines
            graph = await self.engine._get_current_graph(departure_date)
            
            # [TODO-08] Graph Snapshot Staleness Verifier
            if hasattr(graph, 'snapshot') and graph.snapshot and hasattr(graph.snapshot, 'date'):
                snapshot_date = getattr(graph.snapshot, 'date')
                if isinstance(snapshot_date, datetime):
                    age_days = (datetime.utcnow() - snapshot_date).days
                    if age_days > 7:
                        logger.error(f"🚨 [ORCHESTRATOR] CRITICAL: Graph snapshot is {age_days} days stale. Halting search.")
                        return []

            self.fast_router.graph = graph
            self.raptor.graph = graph # [Audit] Ensure RAPTOR is pinned to current graph
            
            await graph.overlay.sync_with_db(db, departure_date.date(), graph.snapshot)

            # [Task 29.9] Budget Trace
            trace = {"start": start_time}
            
            # Resolve stations
            if not source_stop or not dest_stop:
                source_stop, dest_stop = await asyncio.to_thread(resolve_stations, db, source_code, destination_code)
            trace["station_res"] = time.perf_counter()
            
            # [TODO-02] Strict Resolve Guard with Descriptive Telemetry
            if not source_stop or not dest_stop:
                failed_code = source_code if not source_stop else destination_code
                logger.error(f"❌ [ORCHESTRATOR] Station Resolve Guard Triggered. Could not verify: {failed_code}")
                return []

            # [Task 27.13] Pre-resolve all cluster IDs once for efficiency
            from database.session import get_raw_transit_conn
            async with get_raw_transit_conn() as conn:
                src_cluster_ids = await self.ultra_turbo._resolve_cluster_ids(conn, source_stop.code)
                dst_cluster_ids = await self.ultra_turbo._resolve_cluster_ids(conn, dest_stop.code)
            
            # Convert to codes for Turbo
            src_cluster_codes = [self.turbo_router._get_station_code(db, sid) for sid in src_cluster_ids]
            dst_cluster_codes = [self.turbo_router._get_station_code(db, sid) for sid in dst_cluster_ids]

            # [Task 29/22.8] Adaptive Timeout Inheritance
            from core.context import request_timeout_ctx
            total_timeout = request_timeout_ctx.get() or 5.0
            elapsed_init = time.perf_counter() - start_time
            remaining_timeout = max(0.5, total_timeout - (time.perf_counter() - start_time))
            
            from core.nexus.audit.governor import nexus_governor
            gov_stats = await nexus_governor.get_stats()
            
            from core.resource_monitor import resource_monitor, SurgeLevel
            level = resource_monitor.get_surge_level()
            if level != SurgeLevel.NORMAL:
                logger.info(f"System Surge Analysis: Level {level.name} detected.")

            # [Task 29.8] MOVE ENTIRE PIPELINE INSIDE TIMEOUT
            async with asyncio.timeout(remaining_timeout):
                # 3. Execution
                engine_limit = max(limit * 2, 50) 
                num_tasks = 3 if skip_heavy else 5
                progress = ProgressTracker(num_tasks, on_progress)
                is_allowed = lambda n: constraints.permitted_engines is None or n in constraints.permitted_engines

                # 3. Parallel Search Execution (Task 121: Elastic Collection)
                all_tasks = {}
                
                # [TODO-11] Priority Staggering Tiers
                engine_priorities = {
                    "hub_tier_0": 0,
                    "ultra_turbo_direct": 1,
                    "turbo_router": 2,
                    "fastpath_bfs": 5,
                    "raptor": 8,
                    "trip_based": 12
                }

                # Wrapped discover with prioritized staggering and timeout
                async def prioritized_discover(name, engine, req):
                    # Stagger based on priority (5ms per tier)
                    priority = engine_priorities.get(name, 10)
                    if priority > 0:
                        await asyncio.sleep(0.005 * priority)
                    
                    try:
                        # [TODO-11.2] Apply per-engine deadline to protect overall SLA
                        async with asyncio.timeout(remaining_timeout * 1.5): # Slighly buffer
                             return await self._discover_from_engine_async(name, engine, req, start_time, gov_stats)
                    except (asyncio.TimeoutError, TimeoutError):
                        logger.warning(f"Engine {name} hit internal timeout.")
                        return []
                    except Exception as e:
                        logger.error(f"Engine {name} execution failed: {e}")
                        return []

                for name, engine in self.engines.items():
                    if is_allowed(name):
                        if skip_heavy and name in ["fastpath_bfs", "raptor", "trip_based"]:
                            continue
                        
                        # Create specialized request
                        req = request.model_copy(update={
                            "graph": graph,
                            "src_cluster_ids": src_cluster_ids,
                            "dst_cluster_ids": dst_cluster_ids
                        })

                        # Use unified discovery helper with staggering
                        all_tasks[name] = asyncio.create_task(prioritized_discover(name, engine, req))

                trace["engines_launched"] = time.perf_counter()

                # Use as_completed to avoid waiting for the slowest engine if we already have enough
                done, pending = await asyncio.wait(all_tasks.values(), timeout=10.0)
                
                if pending:
                    logger.warning(f"⏰ {len(pending)} engines timed out. Returning partial results.")
                
                # 4. Result Collection & Hydration
                all_raw = []
                for name, task in all_tasks.items():
                    if task in done and not task.cancelled():
                        try:
                            res = task.result()
                            if res:
                                # [Task 30.5] Streaming Hydration for batch results
                                should_hydrate = not constraints.discovery_only and gov_stats["ram_percent"] < 95
                                if should_hydrate:
                                    await self.hydration_pipeline.execute(res, constraints, graph, db)
                                else:
                                    for r in res: r.metadata["speculative"] = True
                                
                                all_raw.extend(res)
                        except Exception as e:
                            logger.error(f"Engine {name} failed: {e}")

                all_routes = [r for r in all_raw if self._is_valid_route(r)]
                
                # [Task 10] Discovery mode: Skip secondary filtering/hydration for raw performance testing
                if not getattr(constraints, 'discovery_only', False):
                    all_routes = await self._filter_cancelled_trains(all_routes, request)
                
                # [Task 27.16] Deep Deduplication and Scoring
                unique_routes = self._global_deduplicate(all_routes)
                
                # [Task 27.16] Final Persona Sort
                if constraints.persona in (Persona.BUDGET, Persona.ECONOMY):
                    unique_routes.sort(key=lambda x: (x.total_cost, x.total_duration))
                elif constraints.persona == Persona.EMERGENCY:
                    from core.data_structures import ensure_datetime
                    unique_routes.sort(key=lambda x: (ensure_datetime(x.segments[0].departure_time), x.total_duration))
                elif constraints.persona in (Persona.COMFORT, Persona.PREMIUM):
                    unique_routes.sort(key=lambda x: (len(x.transfers), x.score))
                elif constraints.persona == Persona.FAMILY:
                    unique_routes.sort(key=lambda x: (x.score, -getattr(x, 'reliability', 0.5)))
                else:
                    unique_routes.sort(key=lambda x: x.score)

                trace["hydration_done"] = time.perf_counter()

            # [Task 29.9] Performance Report
            perf_report = {k: round((v - start_time) * 1000, 2) for k, v in trace.items() if k != "start"}
            logger.info(f"🚀 Full Orchestration Success in {round((time.perf_counter()-start_time)*1000, 2)}ms. Trace: {perf_report}")

            # 6. Sorting & Metadata
            latency_total = (time.perf_counter() - start_time) * 1000
            for r in unique_routes:
                r.metadata["orchestrator_latency_ms"] = round(latency_total, 2)
                if "engine" not in r.metadata: r.metadata["engine"] = "unknown"
                if "tier" not in r.metadata:
                    if r.metadata["engine"] == "ultra_turbo_direct": r.metadata["tier"] = 1
                    elif "turbo" in r.metadata["engine"]: r.metadata["tier"] = 2
                    else: r.metadata["tier"] = 3

            if constraints.persona in (Persona.BUDGET, Persona.ECONOMY):
                unique_routes.sort(key=lambda x: (x.total_cost, x.total_duration))
            elif constraints.persona == Persona.EMERGENCY:
                from core.data_structures import ensure_datetime
                unique_routes.sort(key=lambda x: (ensure_datetime(x.segments[0].departure_time), x.total_duration))
            elif constraints.persona in (Persona.COMFORT, Persona.PREMIUM):
                unique_routes.sort(key=lambda x: (len(x.transfers), x.score))
            elif constraints.persona == Persona.FAMILY:
                unique_routes.sort(key=lambda x: (x.score, -getattr(x, 'reliability', 0.5)))
            else:
                unique_routes.sort(key=lambda x: x.score)
            # [Yield Fix] Increase return cap to 500 (was 150) for better result variety
            # Removed hard minimum to allow smaller result sets when appropriate
            return unique_routes[:min(limit * 5, 500)]

        except (asyncio.TimeoutError, TimeoutError):
            logger.error(f"⌛ Orchestrator Deadline Exceeded for {source_code}->{destination_code}")
            return [] # Fall-back gracefully
        finally:
            if _owned_session and db is not None:
                try: db.close()
                except: pass

    # --- PIPELINE STEPS ---

    async def _step_realtime_propagation(self, routes: List[Route], constraints: RouteConstraints, graph, db):
        """[Task 16 & Task 30] Advanced delay propagation across transfers."""
        for r in routes:
            for i, s in enumerate(r.segments):
                delay = graph.overlay.get_trip_delay(int(s.trip_id))
                if delay > 0:
                    s.departure_time += timedelta(minutes=delay)
                    s.arrival_time += timedelta(minutes=delay)
                    s.metadata["live_delay_mins"] = delay
                    if "alerts" not in r.metadata: r.metadata["alerts"] = []
                    r.metadata["alerts"].append(f"Train {s.train_number} is running {delay}m late.")

            # Re-calculate transfers and total duration
            if len(r.segments) > 1:
                r.total_duration = int((r.segments[-1].arrival_time - r.segments[0].departure_time).total_seconds() // 60)
                for i in range(len(r.transfers)):
                    # Update transfer wait times based on new realtime arrivals/departures
                    arr_seg = r.segments[i]
                    dep_seg = r.segments[i+1]
                    wait = int((dep_seg.departure_time - arr_seg.arrival_time).total_seconds() // 60)
                    r.transfers[i].duration_minutes = wait
                    if wait < 15: # Critical Threshold
                        r.metadata["reliability_badge"] = "CRITICAL"
                        r.metadata["alerts"].append(f"Risky connection at {r.transfers[i].station_name} ({wait}m wait)!")

    async def _step_vectorized_fares(self, routes: List[Route], constraints: RouteConstraints, graph, db):
        from core.pricing.fare_calculator import calculate_fares_batch
        import numpy as np
        dists = np.array([float(r.total_distance or 0.0) for r in routes], dtype=np.float32)
        batch_fares = calculate_fares_batch(dists, constraints.preferred_class or "SL", is_tatkal=constraints.quota == "TQ", db=db)
        for i, r in enumerate(routes):
            r.total_cost = float(batch_fares[i])
            if r.total_distance > 0:
                for s in r.segments:
                    s.fare = round((s.distance_km / r.total_distance) * r.total_cost, 2)

    def _step_realtime_platforms(self, routes: List[Route], constraints: RouteConstraints, graph, db):
        for r in routes:
            for s in r.segments:
                platform = graph.overlay.platform_changes.get((s.trip_id, s.departure_stop_id))
                if platform:
                    s.metadata["platform_realtime"] = platform
                    s.metadata["platform_note"] = "Live Update"
                else:
                    # [Task 28] Static Heatmap Fallback
                    # Logic: Fast trains (12xxx) usually use lower PFs; Slow trains use higher ones.
                    t_no = str(s.train_number)
                    if t_no.isdigit():
                        if t_no.startswith(("12", "22")): 
                             pf = (int(t_no) % 3) + 1 # PFs 1, 2, 3
                        else:
                             pf = (int(t_no) % 5) + 4 # PFs 4, 5, 6, 7, 8
                        s.metadata["platform_predicted"] = pf
                    else:
                        s.metadata["platform_predicted"] = "TBD"
                    
                    s.metadata["platform_note"] = "Historical Heuristic"

    def _step_amenities(self, routes: List[Route], constraints: RouteConstraints, graph, db):
        for r in routes:
            for s in r.segments:
                t_str = str(s.train_number)
                s.metadata["amenities"] = {
                    "pantry": t_str.startswith(("12", "22")),
                    "e_catering": True,
                    "charging": True,
                    "wifi": t_str.startswith("120")
                }

    async def _step_multi_class_fares(self, routes: List[Route], constraints: RouteConstraints, graph, db):
        # [Task 27] Try multiple classes if the preferred one is missing
        from providers.gateway import provider_gateway
        pref_classes = constraints.preferred_classes or (["3A", "2A", "SL"] if not constraints.preferred_class else [constraints.preferred_class])
        
        for r in routes:
            total_cost = 0.0
            for s in r.segments:
                fare_found = False
                for cls in pref_classes:
                    try:
                        f = await provider_gateway.get_fare(s.trip_id, s.departure_time.strftime("%Y-%m-%d"), s.from_stop_code, s.to_stop_code, cls)
                        if f:
                            s.metadata["fare"] = f.amount
                            s.metadata["class"] = cls
                            total_cost += f.amount
                            fare_found = True
                            break
                    except Exception: continue
                
                if not fare_found:
                    s.metadata["fare"] = 200.0 + (s.duration_minutes * 0.5)
                    s.metadata["class"] = "SL"
                    total_cost += s.metadata["fare"]

            r.total_cost = total_cost
        return routes

    async def _step_reliability_badges(self, routes: List[Route], constraints: RouteConstraints, graph, db):
        for r in routes:
            rel_sum = 0
            for s in r.segments:
                s_rel = 0.95 if str(s.train_number).startswith("1") else 0.85
                s.metadata["reliability_badge"] = "HIGH" if s_rel > 0.9 else "AVERAGE"
                rel_sum += s_rel
            r.metadata["avg_reliability"] = rel_sum / len(r.segments) if r.segments else 0.5

    def _step_journey_story(self, routes: List[Route], constraints: RouteConstraints, graph, db):
        for r in routes:
            dur_rating = max(1, 5 - ((r.total_duration or 0) / 600.0))
            cost_rating = max(1, 5 - ((r.total_cost or 0.0) / 1000.0))
            tr_rating = max(1, 5 - (len(r.transfers) * 1.5))
            r.metadata["rating"] = round((dur_rating * 0.4) + (cost_rating * 0.3) + (tr_rating * 0.3), 1)
            parts = []
            if len(r.segments) == 1: parts.append("Direct journey")
            else: parts.append(f"{len(r.transfers)} transfer(s)")
            if r.total_duration < 360: parts.append("Very fast")
            dep_hour = r.segments[0].departure_time.hour if r.segments else 12
            if 21 <= dep_hour or dep_hour <= 4: parts.append("Overnight")
            r.metadata["journey_story"] = " • ".join(parts)

    def _step_integrity_check(self, routes: List[Route], constraints: RouteConstraints, graph, db):
        """[Task 28.10] Final data validation & optimized synchronous scoring."""
        for r in routes:
            if not r.total_cost or r.total_cost < 1: r.total_cost = 500.0
            if not r.total_duration or r.total_duration < 1:
                if r.segments:
                    r.total_duration = int((r.segments[-1].arrival_time - r.segments[0].departure_time).total_seconds() / 60)
            
            # [Task 28.1] Use synchronous scoring to avoid massive event loop overhead
            r.score = RouteScorer.score_route_sync(r, constraints)

    # --- HELPERS ---

    def _is_valid_route(self, route: Route) -> bool:
        if not route.segments: return False
        for s in route.segments:
            from core.data_structures import ensure_datetime
            dep = ensure_datetime(s.departure_time); arr = ensure_datetime(s.arrival_time)
            if arr <= dep: return False
        return True

    def _global_deduplicate(self, routes: List[Route]) -> List[Route]:
        if not routes: return []
        unique_map: Dict[str, Route] = {}
        for r in routes:
            jid = r.journey_id
            engine_name = r.metadata.get("engine", "unknown")
            if jid not in unique_map:
                unique_map[jid] = r
                r.metadata["discovered_by"] = {engine_name}
            else:
                current_best = unique_map[jid]
                # Combine discovery trail
                if "discovered_by" not in current_best.metadata:
                    current_best.metadata["discovered_by"] = {current_best.metadata.get("engine", "unknown")}
                current_best.metadata["discovered_by"].add(engine_name)
                
                # Keep the better version (lower score is better for generalized cost)
                if (r.score < current_best.score) or (r.total_duration < current_best.total_duration):
                    # Transplant discovery trail to the new best
                    r.metadata["discovered_by"] = current_best.metadata["discovered_by"]
                    unique_map[jid] = r
        return list(unique_map.values())

    async def _filter_cancelled_trains(self, routes: List[Route], request: RoutingRequest) -> List[Route]:
        """[Task 30.7] Fast O(1) In-Memory Cancellation Check using constraints metadata."""
        if not routes: return routes
        
        cancelled_nos = request.constraints.metadata.get("cancelled_trip_ids", set())
        
        if not cancelled_nos and request.db_session:
            try:
                date_str = request.departure_date.strftime("%Y-%m-%d")
                query = """
                    SELECT train_no FROM cancelled_trains WHERE travel_date = :dt
                    UNION
                    SELECT t.trip_id 
                    FROM calendar_dates cd 
                    JOIN trips t ON cd.service_id = t.service_id 
                    WHERE cd.date = :dt AND cd.exception_type = 2
                """
                rows = request.db_session.execute(text(query), {"dt": date_str}).fetchall()
                cancelled_nos = {str(r[0]) for r in rows}
            except Exception as e:
                logger.error(f"Failed to fetch fallback cancellations: {e}")
                
        if not cancelled_nos: 
            return routes
            
        valid_routes = []
        for r in routes:
            cancelled_legs = [s.train_number for s in r.segments if str(s.train_number) in cancelled_nos]
            if not cancelled_legs: 
                valid_routes.append(r)
            else: 
                r.metadata["cancellation_detected"] = True
        return valid_routes



    def _hydrate_turbo_results(self, turbo_raw: List[Dict], source: str, destination: str, base_date: datetime) -> List[Route]:
        routes = []
        for r in turbo_raw:
            rt = Route()
            def safe_int(v):
                try: return int(v)
                except: return 0

            if r.get("type") in ("direct", "direct_backbone"):
                dep_dt = self._parse_turbo_time(r.get('dep'), base_date)
                arr_dt = self._parse_turbo_time(r.get('arr'), base_date)
                # [Task 6] Handle midnight arrival if not already handled by parse
                if arr_dt < dep_dt: arr_dt += timedelta(days=1)
                
                seg = RouteSegment(trip_id=safe_int(r.get('train_no')), departure_stop_id=0, arrival_stop_id=0,
                                   departure_code=source, arrival_code=destination,
                                   departure_time=dep_dt, arrival_time=arr_dt,
                                   duration_minutes=int((arr_dt - dep_dt).total_seconds() // 60),
                                   distance_km=float(r.get('distance', 0.0)), 
                                   train_number=str(r.get('train_no')),
                                   service_mask=127, metadata={})
                rt.add_segment(seg); rt.metadata["engine"] = "turbo_direct"
            elif r.get("type") == "1-transfer":
                legs = r.get("legs", [])
                s1_dep = self._parse_turbo_time(legs[0].get('dep'), base_date)
                s1_arr = self._parse_turbo_time(legs[0].get('arr'), base_date); 
                if s1_arr < s1_dep: s1_arr += timedelta(days=1)
                
                s1 = RouteSegment(trip_id=safe_int(legs[0].get('train')), departure_stop_id=0, arrival_stop_id=0,
                                   departure_code=legs[0].get('from'), arrival_code=legs[0].get('to'),
                                   departure_time=s1_dep, arrival_time=s1_arr,
                                   duration_minutes=int((s1_arr - s1_dep).total_seconds() // 60),
                                   distance_km=0.0, train_number=str(legs[0].get('train')),
                                   service_mask=127, metadata={})
                
                s2_dep = self._parse_turbo_time(legs[1].get('dep'), base_date)
                # Ensure transfer buffer logic respects the actual day of arrival
                while s2_dep < s1_arr + timedelta(minutes=15): s2_dep += timedelta(days=1)
                
                s2_arr = self._parse_turbo_time(legs[1].get('arr'), base_date)
                while s2_arr < s2_dep: s2_arr += timedelta(days=1)
                
                s2 = RouteSegment(trip_id=safe_int(legs[1].get('train')), departure_stop_id=0, arrival_stop_id=0,
                                   departure_code=legs[1].get('from'), arrival_code=legs[1].get('to'),
                                   departure_time=s2_dep, arrival_time=s2_arr,
                                   duration_minutes=int((s2_arr - s2_dep).total_seconds() // 60),
                                   distance_km=0.0, fare=0.0, train_number=str(legs[1].get('train')),
                                   service_mask=127, metadata={})
                rt.add_segment(s1); rt.add_segment(s2)
                rt.add_transfer(TransferConnection(station_id=0, arrival_time=s1.arrival_time, 
                                                   departure_time=s2.departure_time,
                                                   duration_minutes=int((s2.departure_time - s1.arrival_time).total_seconds() // 60), 
                                                   station_name=r.get("hub", "UNK")))
                rt.metadata["engine"] = "turbo_transfer"
            if rt.segments: routes.append(rt)
        return routes

    def _parse_turbo_time(self, time_str: str, base_date: datetime) -> datetime:
        """[Task 9] Robust time parsing for GTFS hours >= 24."""
        try:
            parts = list(map(int, time_str.split(":")))
            h, m = parts[0], parts[1]
            extra_days = h // 24
            return base_date.replace(hour=h % 24, minute=m, second=0, microsecond=0) + timedelta(days=extra_days)
        except: return base_date
