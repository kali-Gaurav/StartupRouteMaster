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
        self.hydration_pipeline.add_step(self._step_vectorized_fares)
        self.hydration_pipeline.add_step(self._step_realtime_platforms)
        self.hydration_pipeline.add_step(self._step_amenities)
        self.hydration_pipeline.add_step(self._step_reliability_badges)
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
            
            await graph.overlay.sync_with_db(db, departure_date.date())
            date_str = departure_date.strftime("%Y-%m-%d")
            c_rows = db.execute(text("SELECT train_no FROM cancelled_trains WHERE travel_date = :dt"), {"dt": date_str}).fetchall()
            constraints.metadata = {"cancelled_trip_ids": {int(r[0]) for r in c_rows}}
            
            if not source_stop or not dest_stop:
                source_stop, dest_stop = await asyncio.to_thread(resolve_stations, db, source_code, destination_code)
            
            if not source_stop or not dest_stop: return

            # [Task 27.13] Pre-resolve all cluster IDs once for efficiency
            src_cluster_ids = self.ultra_turbo._resolve_cluster_ids(db, source_stop.code)
            dst_cluster_ids = self.ultra_turbo._resolve_cluster_ids(db, dest_stop.code)
            
            # Convert to codes for Turbo
            src_cluster_codes = [self.turbo_router._get_station_code(db, sid) for sid in src_cluster_ids]
            dst_cluster_codes = [self.turbo_router._get_station_code(db, sid) for sid in dst_cluster_ids]

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
                        all_raw.extend(self._hydrate_turbo_results(res, source_stop.code, dest_stop.code, departure_date))
                    else:
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
                        # [Task 30.5] Streaming Hydration
                        await self.hydration_pipeline.execute(new_routes, constraints, graph, db)
                        
                        # Apply Metadata & Sorting
                        latency_total = (time.perf_counter() - start_time) * 1000
                        for r in new_routes:
                            r.metadata["orchestrator_latency_ms"] = round(latency_total, 2)
                            if "engine" not in r.metadata: r.metadata["engine"] = "unknown"
                            if "tier" not in r.metadata:
                                if r.metadata["engine"] == "ultra_turbo_direct": r.metadata["tier"] = 1
                                elif "turbo" in r.metadata["engine"]: r.metadata["tier"] = 2
                                else: r.metadata["tier"] = 3
                        
                        return new_routes
                except Exception as e:
                    logger.error(f"❌ Engine {name} failed or timed out: {e}")
                return []

            tasks = []
            tasks.append(asyncio.create_task(process_and_yield("HubTier0", self._search_tier_0_hubs_async(source_stop.id, dest_stop.id, departure_date, db), total_timeout)))
            
            # [Task 27.13] Turbo expansion
            tasks.append(asyncio.create_task(process_and_yield("Turbo", asyncio.to_thread(self.turbo_router.find_routes, source_code, destination_code, departure_date, engine_limit), total_timeout)))
            
            # [Task 27.13] UltraTurbo expansion - use pre-resolved IDs
            tasks.append(asyncio.create_task(process_and_yield("UltraTurbo", self.ultra_turbo._collect_day_results(db, src_cluster_ids, dst_cluster_ids, departure_date.date(), engine_limit, None, {}, 0), total_timeout)))
            
            # [Task 27.17] TBR Discovery
            tasks.append(asyncio.create_task(process_and_yield("TBR", self.tbr_router.find_routes(source_stop.id, dest_stop.id, departure_date, constraints, graph), total_timeout)))

            if not skip_heavy:
                tasks.append(asyncio.create_task(process_and_yield("FastPath", asyncio.to_thread(self.fast_router.find_routes, source_stop.id, dest_stop.id, departure_date, constraints), total_timeout * 0.8)))
                tasks.append(asyncio.create_task(process_and_yield("RAPTOR", self.raptor.find_routes(source_stop.id, dest_stop.id, departure_date, constraints, graph), total_timeout * 0.9)))

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
                logger.info(f"📊 System Surge Analysis: Level {level.name} detected.")

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
                            logger.info(f"⏱️ Engine {name} took {lat:.2f}ms")
                            progress.update()
                            return res
                        except Exception as e:
                            logger.error(f"❌ Engine {name} failed or timed out: {e}")
                            progress.update()
                            return []

                async with asyncio.TaskGroup() as tg:
                    t0 = tg.create_task(wrapped_search("HubTier0", self._search_tier_0_hubs_async(source_stop.id, dest_stop.id, departure_date, db), priority=0))
                    t1 = tg.create_task(wrapped_search("Turbo", asyncio.to_thread(self.turbo_router.find_routes, source_code, destination_code, departure_date, engine_limit), priority=1))
                    t2 = tg.create_task(wrapped_search("UltraTurbo", self.ultra_turbo._collect_day_results(db, src_cluster_ids, dst_cluster_ids, departure_date.date(), engine_limit, None, {}, 0), priority=1))
                    
                    # [Task 27.17] TBR Discovery Integration
                    tbr_task = tg.create_task(wrapped_search("TBR", self.tbr_router.find_routes(source_stop.id, dest_stop.id, departure_date, constraints, graph), priority=2))

                    if not skip_heavy:
                        t3 = tg.create_task(wrapped_search("FastPath", asyncio.to_thread(self.fast_router.find_routes, source_stop.id, dest_stop.id, departure_date, constraints), priority=2))
                        t4 = tg.create_task(wrapped_search("RAPTOR", self.raptor.find_routes(source_stop.id, dest_stop.id, departure_date, constraints, graph), priority=3))
                    else: t3, t4 = None, None

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
                all_routes = await self._filter_cancelled_trains(all_routes, departure_date, db)
                
                # [Task 27.16] Deep Deduplication and Scoring
                unique_routes = self._global_deduplicate(all_routes)

                # 5. Hydration
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
                    s.metadata["platform_note"] = "Changed from original"

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
        try:
            date_str = date.strftime("%Y-%m-%d")
            rows = db.execute(text("SELECT train_no FROM cancelled_trains WHERE travel_date = :dt"), {"dt": date_str}).fetchall()
            cancelled_nos = {str(r[0]) for r in rows}
            if not cancelled_nos: return routes
            valid_routes = []
            for r in routes:
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
                seg = RouteSegment(trip_id=t['tid'], departure_stop_id=src_id, arrival_stop_id=dst_id,
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
            if r.get("type") in ("direct", "direct_backbone"):
                dep_dt = self._parse_turbo_time(r.get('dep'), base_date)
                arr_dt = self._parse_turbo_time(r.get('arr'), base_date)
                if arr_dt < dep_dt: arr_dt += timedelta(days=1)
                seg = RouteSegment(trip_id=r.get('train_no'), departure_stop_id=0, arrival_stop_id=0,
                                   departure_code=source, arrival_code=destination,
                                   departure_time=dep_dt, arrival_time=arr_dt,
                                   duration_minutes=int((arr_dt - dep_dt).total_seconds() / 60),
                                   distance_km=0.0, fare=0.0, train_number=str(r.get('train_no')),
                                   service_mask=127, metadata={})
                rt.add_segment(seg); rt.metadata["engine"] = "turbo_direct"
            elif r.get("type") == "1-transfer":
                legs = r.get("legs", [])
                s1_dep = self._parse_turbo_time(legs[0].get('dep'), base_date)
                s1_arr = self._parse_turbo_time(legs[0].get('arr'), base_date); 
                if s1_arr < s1_dep: s1_arr += timedelta(days=1)
                s1 = RouteSegment(trip_id=legs[0].get('train'), departure_stop_id=0, arrival_stop_id=0,
                                   departure_code=legs[0].get('from'), arrival_code=legs[0].get('to'),
                                   departure_time=s1_dep, arrival_time=s1_arr,
                                   duration_minutes=int((s1_arr - s1_dep).total_seconds() / 60),
                                   distance_km=0.0, train_number=str(legs[0].get('train')),
                                   service_mask=127, metadata={})
                s2_dep = self._parse_turbo_time(legs[1].get('dep'), base_date)
                while s2_dep < s1_arr + timedelta(minutes=30): s2_dep += timedelta(days=1)
                s2_arr = self._parse_turbo_time(legs[1].get('arr'), base_date)
                while s2_arr < s2_dep: s2_arr += timedelta(days=1)
                s2 = RouteSegment(trip_id=legs[1].get('train'), departure_stop_id=0, arrival_stop_id=0,
                                   departure_code=legs[1].get('from'), arrival_code=legs[1].get('to'),
                                   departure_time=s2_dep, arrival_time=s2_arr,
                                   duration_minutes=int((s2_arr - s2_dep).total_seconds() / 60),
                                   distance_km=0.0, fare=0.0, train_number=str(legs[1].get('train')),
                                   service_mask=127, metadata={})
                rt.add_segment(s1); rt.add_segment(s2)
                rt.add_transfer(TransferConnection(station_id=0, arrival_time=s1.arrival_time, 
                                                   departure_time=s2.departure_time,
                                                   duration_minutes=int((s2.departure_time - s1.arrival_time).total_seconds()/60), 
                                                   station_name=r.get("hub", "UNK")))
                rt.metadata["engine"] = "turbo_transfer"
            if rt.segments: routes.append(rt)
        return routes

    def _parse_turbo_time(self, time_str: str, base_date: datetime) -> datetime:
        try:
            parts = list(map(int, time_str.split(":")))
            return base_date.replace(hour=parts[0], minute=parts[1], second=0, microsecond=0)
        except: return base_date
