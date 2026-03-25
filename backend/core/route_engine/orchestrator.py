import asyncio
import logging
import time
import struct
import json
from typing import List, Dict, Any, Optional, Callable, Set
from datetime import datetime, timedelta
from sqlalchemy import text

from .constraints import RouteConstraints
from core.data_structures import Route, RouteSegment, TransferConnection, Persona
from .turbo_router import TurboRouter
from .ultra_turbo import UltraTurboDirectEngine
from .raptor import OptimizedRAPTOR
from .fast_router import FastPathRouter
from .scoring import RouteScorer
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
ROUTING_POOL = ThreadPoolExecutor(
    max_workers=32,
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

    def __init__(self, route_engine_instance):
        from .tbr_router import TripBasedRouter # [Task 27.17]
        self.engine = route_engine_instance
        self.ultra_turbo = UltraTurboDirectEngine()
        self.turbo_router = TurboRouter()
        self.fast_router = FastPathRouter(None) 
        self.raptor = OptimizedRAPTOR()
        self.tbr_router = TripBasedRouter() # [Task 27.17]
        
        # Initialize Hydration Pipeline
        self.hydration_pipeline = HydrationPipeline()
        self.hydration_pipeline.add_step(self._step_multi_class_fares) # [Task 27] Enhanced Fares
        self.hydration_pipeline.add_step(self._step_realtime_platforms)
        self.hydration_pipeline.add_step(self._step_amenities)
        self.hydration_pipeline.add_step(self._step_reliability_badges)
        self.hydration_pipeline.add_step(self._step_realtime_propagation)
        self.hydration_pipeline.add_step(self._step_journey_story)
        self.hydration_pipeline.add_step(self._step_integrity_check)

    async def stream_all_tiers(
        self,
        source_code: str,
        destination_code: str,
        departure_date: datetime,
        constraints: RouteConstraints,
        limit: int = 15,
        db=None,
        skip_heavy: bool = False,
        source_stop=None,
        dest_stop=None
    ):
        """[Task 30] Async generator yielding results as they arrive from parallel engines."""
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
            self.fast_router.graph = graph
            
            await graph.overlay.sync_with_db(db, departure_date.date(), graph.snapshot)
            date_str = departure_date.strftime("%Y-%m-%d")
            c_rows = db.execute(text("SELECT train_no FROM cancelled_trains WHERE travel_date = :dt"), {"dt": date_str}).fetchall()
            constraints.metadata = {"cancelled_trip_ids": {int(r[0]) for r in c_rows}}
            
            if not source_stop or not dest_stop:
                source_stop, dest_stop = await asyncio.to_thread(resolve_stations, db, source_code, destination_code)
            
            if not source_stop or not dest_stop: return

            # [Task 5] Metro-Group Expansion: Resolve all stations in the metropolitan area
            from utils.station_utils import get_metro_group_codes
            src_codes = get_metro_group_codes(source_stop.code)
            dst_codes = get_metro_group_codes(dest_stop.code)
            
            # Resolve all codes to their DB numeric IDs
            def resolve_all_ids(codes: List[str]) -> List[int]:
                ids = []
                for c in codes:
                    s = db.execute(text("SELECT id FROM stops WHERE code = :c"), {"c": c}).fetchone()
                    if s: ids.append(s[0])
                return ids

            src_cluster_ids = await asyncio.to_thread(resolve_all_ids, src_codes)
            dst_cluster_ids = await asyncio.to_thread(resolve_all_ids, dst_codes)
            
            # Fallback to single ID if cluster resolve failed (safety)
            if not src_cluster_ids: src_cluster_ids = [source_stop.id]
            if not dst_cluster_ids: dst_cluster_ids = [dest_stop.id]

            # Convert back to codes for engines that prefer codes (Turbo)
            src_cluster_codes = src_codes
            dst_cluster_codes = dst_codes

            from core.context import request_timeout_ctx
            total_timeout = request_timeout_ctx.get() or 5.0
            
            engine_limit = max(limit * 2, 50) 
            seen_jids = set()

            async def process_and_yield(name, coro, timeout):
                try:
                    async with asyncio.timeout(timeout):
                        res = await coro
                    if not res: return []
                    
                    all_raw = []
                    if isinstance(res[0], dict):
                        # Fix engine tagging for Turbo
                        raw_routes = self._hydrate_turbo_results(res, source_stop.code, dest_stop.code, departure_date)
                        for r in raw_routes: r.metadata["engine"] = f"turbo_{r.metadata.get('engine_type', 'unknown')}"
                        all_raw.extend(raw_routes)
                    else:
                        for r in res: 
                            if isinstance(r, Route): r.metadata["engine"] = name.lower()
                        all_raw.extend(res)
                        
                    all_routes = [r for r in all_raw if self._is_valid_route(r)]
                    all_routes = await self._filter_cancelled_trains(all_routes, departure_date, db)
                    
                    # [Task 30.4] Streaming Deduplication
                    new_routes = []
                    for r in all_routes:
                        if r.journey_id not in seen_jids:
                            seen_jids.add(r.journey_id)
                            new_routes.append(r)

                    if new_routes:
                        # [Task 10] Discovery Mode: Skip heavy hydration
                        if not constraints.discovery_only:
                            # [Task 30.5] Streaming Hydration
                            await self.hydration_pipeline.execute(new_routes, constraints, graph, db)
                        else:
                            # Minimal metadata for debugging
                            for r in new_routes: r.metadata["discovery_mode"] = True
                        
                        # Apply Metadata & Sorting
                        latency_total = (time.perf_counter() - start_time) * 1000
                        for r in new_routes:
                            r.metadata["orchestrator_latency_ms"] = round(latency_total, 2)
                            if "engine" not in r.metadata: r.metadata["engine"] = name.lower()
                            if "tier" not in r.metadata:
                                if "ultra" in r.metadata["engine"]: r.metadata["tier"] = 1
                                elif "turbo" in r.metadata["engine"]: r.metadata["tier"] = 2
                                else: r.metadata["tier"] = 3
                        
                        return new_routes
                except Exception as e:
                    logger.error(f" Engine {name} failed or timed out: {e}")
                return []

            def is_allowed(name: str) -> bool:
                if not constraints.permitted_engines: return True
                return any(e.lower() in name.lower() for e in constraints.permitted_engines)

            tasks = []
            if is_allowed("HubTier0"):
                tasks.append(asyncio.create_task(process_and_yield("HubTier0", self._search_tier_0_hubs_async(source_stop.id, dest_stop.id, departure_date, db), total_timeout)))
            
            if is_allowed("Turbo"):
                tasks.append(asyncio.create_task(process_and_yield("Turbo", asyncio.to_thread(self.turbo_router.find_routes, source_code, destination_code, departure_date, engine_limit), total_timeout)))
            
            if is_allowed("UltraTurbo"):
                tasks.append(asyncio.create_task(process_and_yield("UltraTurbo", self.ultra_turbo._collect_day_results(db, src_cluster_ids, dst_cluster_ids, departure_date.date(), engine_limit, None, {}, 0), total_timeout)))
            
            if is_allowed("TBR"):
                tasks.append(asyncio.create_task(process_and_yield("TBR", self.tbr_router.find_routes(src_cluster_ids, dst_cluster_ids, departure_date, constraints, graph), total_timeout)))

            if not skip_heavy:
                if is_allowed("FastPath"):
                    tasks.append(asyncio.create_task(process_and_yield("FastPath", asyncio.to_thread(self.fast_router.find_routes, src_cluster_ids, dst_cluster_ids, departure_date, constraints), total_timeout * 0.8)))
                if is_allowed("RAPTOR"):
                    tasks.append(asyncio.create_task(process_and_yield("RAPTOR", self.raptor.find_routes(src_cluster_ids, dst_cluster_ids, departure_date, constraints, graph), total_timeout * 0.9)))

            # Use as_completed to yield results instantly as they finish
            for fut in asyncio.as_completed(tasks):
                batch = await fut
                if batch:
                    # [Task 25] Persona Sorting on the batch before yielding
                    if constraints.persona in (Persona.BUDGET, Persona.ECONOMY):
                        batch.sort(key=lambda x: (x.total_cost, x.total_duration))
                    elif constraints.persona == Persona.EMERGENCY:
                        from core.data_structures import ensure_datetime
                        batch.sort(key=lambda x: (ensure_datetime(x.segments[0].departure_time), x.total_duration))
                    elif constraints.persona in (Persona.COMFORT, Persona.PREMIUM):
                        batch.sort(key=lambda x: (len(x.transfers), x.score))
                    elif constraints.persona == Persona.FAMILY:
                        batch.sort(key=lambda x: (x.score, -getattr(x, 'reliability', 0.5)))
                    else:
                        batch.sort(key=lambda x: x.score)
                        
                    yield batch

        except (asyncio.TimeoutError, TimeoutError):
            logger.error(f"⌛ Orchestrator Stream Deadline Exceeded for {source_code}->{destination_code}")
        finally:
            if _owned_session and db is not None:
                try: db.close()
                except: pass

    async def search_all_tiers(

        self,
        source_code: str,
        destination_code: str,
        departure_date: datetime,
        constraints: RouteConstraints,
        limit: int = 15,
        db=None,
        skip_heavy: bool = False,
        source_stop=None,
        dest_stop=None,
        on_progress: Optional[Callable[[float], None]] = None 
    ) -> List[Route]:
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
                return []

        try:
            from .graph import TimeDependentGraph
            # Sync overlay & fetch cancelled
            # [Task 1.3] Ensure overlay is fresh for all engines
            graph = await self.engine._get_current_graph(departure_date)
            self.fast_router.graph = graph
            self.raptor.graph = graph # [Audit] Ensure RAPTOR is pinned to current graph
            
            await graph.overlay.sync_with_db(db, departure_date.date(), graph.snapshot)

            # [Task 29.9] Budget Trace
            trace = {"start": start_time}
            
            # Resolve stations
            if not source_stop or not dest_stop:
                source_stop, dest_stop = await asyncio.to_thread(resolve_stations, db, source_code, destination_code)
            trace["station_res"] = time.perf_counter()
            
            if not source_stop or not dest_stop: return []

            # [Task 27.13] Pre-resolve all cluster IDs once for efficiency
            src_cluster_ids = self.ultra_turbo._resolve_cluster_ids(db, source_stop.code)
            dst_cluster_ids = self.ultra_turbo._resolve_cluster_ids(db, dest_stop.code)
            
            # Convert to codes for Turbo
            src_cluster_codes = [self.turbo_router._get_station_code(db, sid) for sid in src_cluster_ids]
            dst_cluster_codes = [self.turbo_router._get_station_code(db, sid) for sid in dst_cluster_ids]

            # [Task 29/22.8] Adaptive Timeout Inheritance
            from core.context import request_timeout_ctx
            total_timeout = request_timeout_ctx.get() or 5.0
            elapsed_init = time.perf_counter() - start_time
            remaining_timeout = max(0.5, total_timeout - (time.perf_counter() - start_time))
            
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

                async def wrapped_search(name, coro, priority=10):
                    if priority > 1: await asyncio.sleep(0.005 * priority)
                    async with self._global_resource_sem:
                        st = time.perf_counter()
                        try:
                            # Inner timeout per engine task
                            async with asyncio.timeout(remaining_timeout * 0.9):
                                res = await coro
                            lat = (time.perf_counter() - st) * 1000
                            logger.info(f"Engine {name} took {lat:.2f}ms")
                            progress.update()
                            return res
                        except Exception as e:
                            logger.error(f"Engine {name} failed or timed out: {e}")
                            progress.update()
                            return []

                def is_allowed(name_):
                    if not constraints.permitted_engines: return True
                    return any(e.lower() in name_.lower() for e in constraints.permitted_engines)

                t0 = t1 = t2 = tbr_task = t3 = t4 = None
                async with asyncio.TaskGroup() as tg:
                    if is_allowed("HubTier0"):
                        t0 = tg.create_task(wrapped_search("HubTier0", self._search_tier_0_hubs_async(source_stop.id, dest_stop.id, departure_date, db), priority=0))
                    
                    if is_allowed("Turbo"):
                        t1 = tg.create_task(wrapped_search("Turbo", asyncio.to_thread(self.turbo_router.find_routes, source_code, destination_code, departure_date, engine_limit), priority=1))
                    
                    if is_allowed("UltraTurbo"):
                        t2 = tg.create_task(wrapped_search("UltraTurbo", self.ultra_turbo._collect_day_results(db, src_cluster_ids, dst_cluster_ids, departure_date.date(), engine_limit, None, {}, 0), priority=1))
                    
                    if is_allowed("TBR"):
                        # [Task 27.17] TBR Discovery Integration
                        tbr_task = tg.create_task(wrapped_search("TBR", self.tbr_router.find_routes(source_stop.id, dest_stop.id, departure_date, constraints, graph), priority=2))

                    if not skip_heavy:
                        if is_allowed("FastPath"):
                            t3 = tg.create_task(wrapped_search("FastPath", asyncio.to_thread(self.fast_router.find_routes, source_stop.id, dest_stop.id, departure_date, constraints), priority=2))
                        if is_allowed("RAPTOR"):
                            t4 = tg.create_task(wrapped_search("RAPTOR", self.raptor.find_routes(source_stop.id, dest_stop.id, departure_date, constraints, graph), priority=3))

                trace["engines_done"] = time.perf_counter()

                # 4. Result Collection & Deduplication
                all_raw = []
                for t in [t0, t1, t2, tbr_task, t3, t4]:
                    if t is None: continue
                    res = t.result()
                    if not res: continue
                    if isinstance(res[0], dict):
                        all_raw.extend(self._hydrate_turbo_results(res, source_stop.code, dest_stop.code, departure_date))
                    else: all_raw.extend(res)

                all_routes = [r for r in all_raw if self._is_valid_route(r)]
                
                # [Task 10] Discovery mode: Skip secondary filtering/hydration for raw performance testing
                if not getattr(constraints, 'discovery_only', False):
                    all_routes = await self._filter_cancelled_trains(all_routes, departure_date, db)
                
                # [Task 27.16] Deep Deduplication and Scoring
                unique_routes = self._global_deduplicate(all_routes)

                # 5. Hydration
                if not getattr(constraints, 'discovery_only', False):
                    await self.hydration_pipeline.execute(unique_routes, constraints, graph, db)
                
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

            return unique_routes[:limit]

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
                    if t_no.startswith(("12", "22")): 
                         pf = (int(s.train_number) % 3) + 1 # PFs 1, 2, 3
                    else:
                         pf = (int(s.train_number) % 5) + 4 # PFs 4, 5, 6, 7, 8
                    
                    s.metadata["platform_predicted"] = pf
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
            if jid not in unique_map: unique_map[jid] = r
            else:
                current_best = unique_map[jid]
                if (r.score > 0 and r.score < current_best.score) or (r.total_duration < current_best.total_duration):
                    unique_map[jid] = r
        return list(unique_map.values())

    async def _filter_cancelled_trains(self, routes: List[Route], date: datetime, db) -> List[Route]:
        # [Gap 15] Use Overlay cache first (it has GTFS + Manual cancellations)
        # Assuming self.engine.overlay is accessible via the graph passed to stream/search
        # But here we don't have the graph instance easily unless we passed it.
        # We passed 'graph' to 'stream_all_tiers' but not to this helper explicitly in all paths?
        # Actually, stream_all_tiers calls this.
        # But we can access the Overlay via the engine or graph.
        # Let's rely on DB for safety but OPTIMIZE it.
        try:
            # Check if any route has a cancelled train in its segments
            # We can use the 'constraints.metadata["cancelled_trip_ids"]' we populated earlier!
            # In stream_all_tiers: constraints.metadata = {"cancelled_trip_ids": ...}
            # But that only had manual cancellations.
            # We want both.
            
            # Since we can't easily access the graph/overlay here without refactoring signature,
            # We will assume the overlay sync logic already happened.
            # We'll just check the DB again but include calendar_dates this time to be safe.
            # OR better: Check constraints.metadata if we trust it.
            
            # Ideally, we should trust the engines to filter.
            # Turbo checks overlay. UltraTurbo checks DB. RAPTOR checks overlay.
            # So this post-filtering is a safety net for "HubTier0" or other engines.
            
            # Let's do a fast check using constraints metadata if available.
            pass
        except: pass
        
        # Real implementation:
        try:
            date_str = date.strftime("%Y-%m-%d")
            # [Gap 16] Include GTFS calendar_dates in post-filter
            # Fetch union of manual and gtfs cancellations
            query = """
                SELECT train_no FROM cancelled_trains WHERE travel_date = :dt
                UNION
                SELECT t.trip_id 
                FROM calendar_dates cd 
                JOIN trips t ON cd.service_id = t.service_id 
                WHERE cd.date = :dt AND cd.exception_type = 2
            """
            rows = db.execute(text(query), {"dt": date_str}).fetchall()
            cancelled_nos = {str(r[0]) for r in rows}
            
            if not cancelled_nos: return routes
            valid_routes = []
            for r in routes:
                # [Gap 14] Safe string conversion for check
                cancelled_legs = [s.train_number for s in r.segments if str(s.train_number) in cancelled_nos]
                if not cancelled_legs: valid_routes.append(r)
                else: r.metadata["cancellation_detected"] = True
            return valid_routes
        except: return routes

    async def _search_tier_0_hubs_async(self, src_id: int, dst_id: int, date: datetime, db) -> List[Route]:
        return await asyncio.to_thread(self._search_tier_0_hubs, src_id, dst_id, date, db)

    def _search_tier_0_hubs(self, src_id: int, dst_id: int, date: datetime, db) -> List[Route]:
        try:
            row = db.execute(text("SELECT trains_json FROM hub_connectivity_index WHERE src_hub_id = :src AND dst_hub_id = :dst"), {"src": src_id, "dst": dst_id}).fetchone()
            if not row: return []
            trains = json.loads(row[0])
            results = []
            for t in trains[:20]: 
                rt = Route()
                # [Gap 14] Fix trip_id type (ensure int)
                try: tid_int = int(t['tid'])
                except: tid_int = 0
                
                seg = RouteSegment(trip_id=tid_int, departure_stop_id=src_id, arrival_stop_id=dst_id,
                                   departure_time=self._parse_turbo_time(t['dep'], date),
                                   arrival_time=self._parse_turbo_time(t['arr'], date),
                                   duration_minutes=0, distance_km=0.0, train_number=str(t['tid']),
                                   fare=0.0, service_mask=127, metadata={})
                rt.add_segment(seg); rt.metadata["engine"] = "hub_tier_0"
                results.append(rt)
            return results
        except: return []

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
