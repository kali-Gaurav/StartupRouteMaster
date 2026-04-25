from services.multi_layer_cache import TTL_ROUTE_SEARCH
from services.multi_layer_cache import DiscoveryQuery
from core.route_engine import data_provider
from core.providers import ServiceStatus
import asyncio
import logging
import os
import orjson as json
import time
import hashlib
import zlib
import gc
import math
import random
from typing import List, Dict, Optional, Any, Tuple, cast, Callable
from services.providers.factory import provider_factory, TransportType
from sqlalchemy.orm import Session
from fastapi import Request
from datetime import datetime, timedelta
from collections import deque

from core.route_engine.engine import RailwayRouteEngine
from core.route_engine import get_route_engine
from core.route_engine.data_provider import DataProvider
from core.data_structures import Route, Persona, PaginationMetadata
from core.pricing.fare_calculator import calculate_fare
from database.config import Config
from services.multi_layer_cache import multi_layer_cache, RouteQuery
from utils.station_utils import resolve_stations
from utils import metrics
from core.metrics import jit_metrics, SurgeLevel, DegradationManager
from database.session import SessionTransit
from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.base import RoutingRequest
from core.route_engine.constraints_engine import ConstraintsEngine
from core.route_engine.categorization import CategorizationEngine
from services.unlock_service import UnlockService
from core.resilience import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.retry import RetryPolicy

logger = logging.getLogger(__name__)

class SearchServiceMetrics:
    """Metrics tracking for search service."""

    def __init__(self):
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()

    async def record_search(self, duration_ms: float, success: bool, routes_found: int):
        """Record search metrics."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "duration_ms": duration_ms,
                "success": success,
                "routes_found": routes_found
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_searches": 0, "success_rate": 0.0}

        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        return {
            "total_searches": total,
            "successful_searches": successful,
            "failed_searches": total - successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "avg_duration_ms": sum(m["duration_ms"] for m in self._metrics) / total if total > 0 else 0.0,
            "total_routes_found": sum(m["routes_found"] for m in self._metrics)
        }


class SearchService:
    _search_semaphore = asyncio.Semaphore(5)

    def __init__(self, db: Optional[Session] = None, route_engine_instance: Optional[RailwayRouteEngine] = None):
        self.db = db
        self.route_engine = route_engine_instance or get_route_engine()
        self.transit_db: Optional[Session] = None
        self.data_provider = DataProvider()

        # Circuit breakers for external services
        self._redis_breaker = circuit_breaker_manager.get_or_create(
            "search_redis",
            CircuitConfig(failure_threshold=5, timeout_seconds=30.0, success_threshold=2)
        )
        self._transit_db_breaker = circuit_breaker_manager.get_or_create(
            "search_transit_db",
            CircuitConfig(failure_threshold=3, timeout_seconds=60.0, success_threshold=2)
        )
        self._rapidapi_breaker = circuit_breaker_manager.get_or_create(
            "search_rapidapi",
            CircuitConfig(failure_threshold=5, timeout_seconds=120.0, success_threshold=3, half_open_max_calls=3)
        )

        # Retry policies
        self._redis_retry = RetryPolicy(
            max_attempts=3,
            initial_delay=0.1,
            max_delay=2.0,
            conditions=[
                lambda e: "timeout" in str(e).lower(),
                lambda e: "connection" in str(e).lower()
            ]
        )
        self._external_api_retry = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=10.0,
            conditions=[
                lambda e: "timeout" in str(e).lower(),
                lambda e: getattr(e, "status_code", 0) == 429
            ]
        )

        # Metrics tracking
        self._metrics = SearchServiceMetrics()

        # Task 7.1: Attach decoupled microservice engine
        from services.search.engine import SearchMicroservice
        # Use a temporary transit session for micro-engine init if needed, or better, pass in on execution
        self.micro_engine = SearchMicroservice(None, self.route_engine) # Fixed: session moved to execution

        logger.info("SearchService initialized with resilience patterns")

    def get_metrics(self) -> dict:
        """Get service metrics."""
        return self._metrics.get_metrics()

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "circuit_breakers": {
                "redis": self._redis_breaker.get_metrics(),
                "transit_db": self._transit_db_breaker.get_metrics(),
                "rapidapi": self._rapidapi_breaker.get_metrics()
            },
            "metrics": self._metrics.get_metrics()
        }

    def reset_circuit_breakers(self):
        """Reset all circuit breakers."""
        self._redis_breaker.reset()
        self._transit_db_breaker.reset()
        self._rapidapi_breaker.reset()
        logger.info("All circuit breakers reset for search_service")

    async def explain_zero_results(self, source: str, destination: str, travel_date: datetime) -> Dict[str, Any]:
        """
        [20.1] Diagnostic utility to explain why search yielded zero results.
        Analyzes constraints, dates, and connectivity.
        """
        reasons = []
        suggestions = []
        
        # 1. Date Check [20.2]
        now = datetime.now()
        if travel_date.date() < now.date():
            reasons.append("Selected date is in the past.")
            suggestions.append("Select a future date for travel.")
        elif (travel_date - now).days > 120:
            reasons.append("Railway bookings usually open only 120 days in advance.")
            suggestions.append("Try a date closer to today.")

        # 2. Connectivity Check [20.3]
        from database.session import SessionTransit
        transient_transit_db = self.transit_db or SessionTransit()
        close_transit_db = self.transit_db is None
        try:
            source_stop, dest_stop = resolve_stations(transient_transit_db, source, destination)
            if not source_stop: reasons.append(f"Origin station '{source}' not recognized.")
            if not dest_stop: reasons.append(f"Destination station '{destination}' not recognized.")
        finally:
            if close_transit_db:
                transient_transit_db.close()
        
        if source_stop and dest_stop:
            # Check if ANY trains run between these stations on any day
            from sqlalchemy import text
            try:
                count = transient_transit_db.execute(text(
                    "SELECT COUNT(*) FROM trips t "
                    "JOIN stop_times s1 ON t.id = s1.trip_id "
                    "JOIN stop_times s2 ON t.id = s2.trip_id "
                    "WHERE s1.stop_id = :s1 AND s2.stop_id = :s2 AND s1.stop_sequence < s2.stop_sequence"
                ), {"s1": cast(int, source_stop.id), "s2": cast(int, dest_stop.id)}).scalar()
                
                if count == 0:
                    reasons.append("No direct trains found between these stations on any day.")
                    suggestions.append("Try searching via a major hub like NDLS, HWH, or CSMT.")
                else:
                    reasons.append("Direct trains exist but may not run on the selected date.")
                    suggestions.append("Try searching +/- 1 day for better availability.")
            except Exception as e:
                logger.error(f"Error in zero-yield diagnostic query: {e}")

        return {
            "status": "no_results",
            "reasons": reasons,
            "suggestions": suggestions,
            "diagnostic_info": {
                "source": source, "destination": destination, "date": travel_date.isoformat()
            }
        }

    async def _log_engine_metrics(self, engine_name: str, duration_ms: float, success: bool):
        try:
            metrics.SEARCH_LATENCY_SECONDS.labels(endpoint=engine_name).observe(duration_ms / 1000.0)
            metrics.SEARCH_REQUESTS_TOTAL.labels(endpoint=engine_name, status=str(success)).inc()
            
            # Redis metrics
            if multi_layer_cache.redis:
                today = datetime.utcnow().date().isoformat()
                await multi_layer_cache.redis.hincrby(f"metrics:engine_usage:{today}", engine_name, 1)
                await multi_layer_cache.redis.hincrby(f"metrics:engine_time:{today}", engine_name, int(duration_ms))
                if success:
                    await multi_layer_cache.redis.hincrby(f"metrics:engine_success:{today}", engine_name, 1)
        except: pass

    async def _suggest_return_leg(self, source: str, destination: str, travel_date: datetime) -> Optional[Dict]:
        """
        [P14] Shadow search for the return journey.
        """
        return_results = None
        try:
            from core.route_engine.constraints_engine import ConstraintsEngine
            return_date = travel_date + timedelta(days=2) # Default assumption: 2 day trip
            
            # Simple heuristic: Only suggest if it's a major route
            # Perform a fast, limited search for the reverse path
            orchestrator = UnifiedRoutingOrchestrator(self.route_engine)
            db = SessionTransit()
            try:
                return_results = await orchestrator.stream_all_tiers(
                    RoutingRequest(
                        source_code=destination,
                        destination_code=source,
                        departure_date=return_date,
                        constraints=ConstraintsEngine.initialize_constraints(
                            persona_str=Persona.COMFORT.value,
                            travel_date=return_date.date(),
                            quota="GN"
                        ),
                        db_session=db
                    ),
                    skip_heavy=True
                )
            finally:
                db.close()
                
                if return_results and len(return_results) > 0:
                    top_return = return_results[0]
                    price = getattr(top_return, "fare", getattr(top_return, "total_cost", 0))
                    return {
                        "direction": "RETURN",
                        "route": top_return,
                        "suggestion_text": f"Complete your loop: Return to {source} on {return_date.date()} for ₹{price}"
                    }
        except Exception as e:
            logger.debug(f"Return suggestion failed: {e}")
        return None

    async def search_routes(
        self, source: str, destination: str, travel_date: str, 
        budget_category: Optional[str] = None, page: int = 1, limit: int = 15, 
        quota: str = "GN", client_ip: Optional[str] = None, geo_state: Optional[str] = None, 
        session_id: Optional[str] = None, cursor: Optional[float] = None, 
        request: Optional[Request] = None,
        permitted_engines: Optional[list[str]] = None,
        discovery_only: bool = False,
        discovery_model: str = "BACKBONE",
        multi_modal: bool = False
    ) -> Dict[Any, Any]:
        overall_start = time.time()
        transit_db = None
        
        # [Point 16] Resource Governor Integration
        from core.resource_monitor import resource_monitor
        budget = resource_monitor.get_resource_budget()
        is_overloaded = budget < 1.0
        
        # Task 34: Early Disconnect Check
        if request and await request.is_disconnected():
            logger.warning("🚫 Search Aborted: Client disconnected before processing.")
            return {"status": "aborted", "journeys": []}

        gc.disable() 
        
        # Adaptive limits based on resource budget
        internal_limit = max(20, int(150 * budget))
        limit = max(5, int(limit * budget))
        
        if is_overloaded:
            logger.info(f"🚦 [NEXUS GOVERNOR] System Pressure Detected (Budget: {budget*100:.1f}%). Adjusting search depth.")
        
        try:
            # 1. Start Transit Session
            from database.session import SessionTransit
            transit_db = SessionTransit()
            
            # (Existing logic inside search_routes ...)
            # 1. Normalize and Prepare Fingerprint Cache
            source = source.upper().strip()
            destination = destination.upper().strip()
            quota = quota.upper().strip()
            session_id = session_id or f"sid_{hashlib.md5(f'{source}:{destination}:{travel_date}:{budget_category}'.encode()).hexdigest()[:10]}"
            
            # [Point 15.1] NIS Observation: Log Search Event
            from services.intelligence_service import IntelligenceService
            search_event_id = None
            intel_svc = None
            if self.db:
                intel_svc = IntelligenceService(self.db)
                search_event_id = await intel_svc.log_search(
                    session_id, None, source, destination, budget_category or "COMFORT"
                )
            
            from core.container import container
            await container.get("search", timeout=300.0)
            await container.get("cache")
            
            # Redis Keys for Cursor-Based Pool (Subtask 1.1 & 18.2)
            pool_key = f"search:pool:{quota}:{session_id}"
            data_key = f"search:data:{quota}:{session_id}"
            seen_key = f"search:seen:{quota}:{session_id}"
            
            # [1.1] Handle Cursor/Page 2+ via existing pool
            if multi_layer_cache.redis and (page > 1 or cursor is not None):
                result = await self.load_more_routes(session_id, limit, quota=quota, cursor=cursor)
                transit_db.close()
                return result

            # 2. Resolve stations via Transit DB
            from utils.station_utils import resolve_stations
            source_stop, dest_stop = await asyncio.to_thread(resolve_stations, transit_db, source, destination)
            if not source_stop or not dest_stop:
                transit_db.close()
                return {"source": source, "destination": destination, "journeys": [], "error": "Station not found"}

            source_stop_id = cast(int, source_stop.id)
            dest_stop_id = cast(int, dest_stop.id)
            source_lat = cast(float, source_stop.latitude)
            source_lon = cast(float, source_stop.longitude)
            dest_lat = cast(float, dest_stop.latitude)
            dest_lon = cast(float, dest_stop.longitude)

            # [Task 41.22] Resolve Metro/Cluster IDs once
            from utils.station_utils import get_metro_group_codes
            def _get_cluster_ids_sync(stop):
                codes = get_metro_group_codes(stop.code, transit_db)
                from sqlalchemy import text
                q = f"SELECT id FROM stops WHERE code IN ({','.join([':c'+str(i) for i in range(len(codes))])})"
                params = {f"c{i}": c for i, c in enumerate(codes)}
                return [r[0] for r in transit_db.execute(text(q), params).fetchall()]

            src_cluster_ids = await asyncio.to_thread(_get_cluster_ids_sync, source_stop)
            dst_cluster_ids = await asyncio.to_thread(_get_cluster_ids_sync, dest_stop)

            try:
                dt = datetime.strptime(travel_date, "%Y-%m-%d")
            except:
                dt = datetime.now()

            # [FIX] Handle 'all' or unexpected budget categories gracefully
            safe_budget = budget_category.lower() if budget_category else "comfort"
            if safe_budget == "all": safe_budget = "comfort"
            
            try:
                persona = Persona(safe_budget)
            except ValueError:
                logger.warning(f"Invalid persona '{safe_budget}' requested. Falling back to COMFORT.")
                persona = Persona.COMFORT

            candidate_list = []
            expansion_triggered = False
            
            # [Task 26.6] Discovery Cache Bypass
            discovery_key = DiscoveryQuery(source, destination, dt.date()).cache_key()
            cached_candidate_list = await multi_layer_cache.get(discovery_key) if multi_layer_cache.redis else None
            orchestrator = UnifiedRoutingOrchestrator(self.route_engine)
            
            if cached_candidate_list:
                logger.info(f"⚡ [NEXUS:ECHO] Discovery Bypass for {discovery_key}. Skipping graph traversal.")
                candidate_list = cached_candidate_list

            c = ConstraintsEngine.initialize_constraints(
                persona_str=persona.value,
                travel_date=dt.date(),
                quota=quota,
                permitted_engines=permitted_engines,
                discovery_only=discovery_only,
                discovery_model=discovery_model
            )

            # 3. GATHER ALL POSSIBLE ROUTES (Tiers 0, 1, 2, 3) - [2.1] & [2.6] Parallel Expansion
            all_unique_routes = {} 
            
            if not candidate_list:
                # [Subtask 4.3] Surge Level 1 Protection
                skip_heavy = budget < 0.6 or jit_metrics.surge_level >= SurgeLevel.CRITICAL
                if skip_heavy:
                    logger.warning(f"🚦 Surge Protection Active (Budget={budget:.2f}): Skipping heavy routing engines.")

                # [2.1] Phase 1: Search Target Date
                # Use a large internal limit (e.g. 200) to allow for diverse candidates
                internal_limit = max(100, limit * 3)
            
                req_target = RoutingRequest(
                    source_code=source,
                    destination_code=destination,
                    source_stop_id=source_stop_id,
                    destination_stop_id=dest_stop_id,
                    src_cluster_ids=src_cluster_ids,
                    dst_cluster_ids=dst_cluster_ids,
                    departure_date=dt,
                    constraints=c,
                    limit=internal_limit,
                    budget=budget,
                    db_session=transit_db
                )
                req_target.multi_modal = multi_modal
                search_res_target = await orchestrator.search_all_tiers(req_target, skip_heavy=skip_heavy)
                from core.data_structures import Route
                for r in search_res_target:
                    if not isinstance(r, Route):
                        continue
                    if not isinstance(r.metadata, dict):
                        r.metadata = {}
                    r.metadata["day_offset"] = 0
                    all_unique_routes[r.journey_id] = r

                # [G11.3] The Omniscient Orchestration Loop
                # We concurrently discover: 1. Rail routes (RAPTOR), 2. Multimodal Bridges (Providers)
                # All multimodal discovery is now handled inside search_all_tiers via MultimodalEngine
                search_res_target = await orchestrator.search_all_tiers(req_target, skip_heavy=skip_heavy)
                
                for r in search_res_target:
                    if not isinstance(r.metadata, dict):
                        r.metadata = {}
                    r.metadata["day_offset"] = 0
                    all_unique_routes[r.journey_id] = r
                
                logger.info(f"🔱 [OMNISCIENT] discovery Complete. Routes: {len(all_unique_routes)}")
                
                # [Subtask 1.5] Disconnection Check 1
                if request and await request.is_disconnected():
                    logger.warning(f"🛑 Search Aborted: Client disconnected during Phase 1 for {source}->{destination}")
                    return {"journeys": [], "aborted": True}

                # [2.2] Multi-Day Expansion Engine: UPGRADED Yield Threshold (Task 2.2)
                # If we found fewer than 15 routes (was 5), expand to neighboring days.
                expansion_triggered = False
                from core.nexus.audit.triage import nexus_triage
                
                if len(all_unique_routes) < 15 and budget > 0.4:
                    if nexus_triage.current_backoff > 0.65 or DegradationManager.should_skip_heavy_expansion():
                        logger.info(f"🚦 [NEXUS LATCH] System Pressure: {nexus_triage.current_backoff*100:.1f}%. Halting Multi-Day Memory Flood.")
                    else:
                        # Only expand to days that already have a cached snapshot; never trigger a full graph rebuild
                        from core.route_engine.snapshot_manager import SnapshotManager
                        _snap_mgr = SnapshotManager()
                        _plus_date = dt + timedelta(days=1)
                        _plus_cached = os.path.exists(_snap_mgr._get_filename(_plus_date))

                        if not _plus_cached:
                            logger.info(f"Expansion skipped: no snapshot cached for {_plus_date.date()}. Avoiding graph rebuild.")
                        else:
                            expansion_triggered = True
                            logger.info(f"Moderate yield ({len(all_unique_routes)}) detected for {source}->{destination}. Expanding search.")

                            # Day +1
                            req_plus = RoutingRequest(
                                source_code=source, 
                                destination_code=destination, 
                                source_stop_id=source_stop_id,
                                destination_stop_id=dest_stop_id,
                                src_cluster_ids=src_cluster_ids,
                                dst_cluster_ids=dst_cluster_ids,
                                departure_date=_plus_date, 
                                constraints=c, 
                                limit=internal_limit, 
                                db_session=transit_db
                            )
                            req_plus.multi_modal = multi_modal
                            res_plus = await orchestrator.search_all_tiers(req_plus)
                            for r in res_plus:
                                if r.journey_id not in all_unique_routes:
                                    r.metadata["day_offset"] = 1
                                    r.metadata["alt_reason"] = f"Alternative: Available on {_plus_date.strftime('%b %d')}"
                                    all_unique_routes[r.journey_id] = r

                    # [Subtask 1.5] Disconnection Check 2
                    if request and await request.is_disconnected():
                        logger.warning(f"🛑 Search Aborted: Client disconnected during Expansion for {source}->{destination}")
                        return {"journeys": [], "aborted": True}

                    # Day -1 (Only if still moderate yield and snapshot cached)
                    if len(all_unique_routes) < 15:
                        # Don't suggest past dates if searching for today
                        _minus_date = dt - timedelta(days=1)
                        if _minus_date.date() >= datetime.utcnow().date():
                            if not hasattr(self, '_snap_mgr'):
                                from core.route_engine.snapshot_manager import SnapshotManager
                                self._snap_mgr = SnapshotManager()
                            _minus_cached = os.path.exists(self._snap_mgr._get_filename(_minus_date))
                            if not _minus_cached:
                                logger.info(f"Day-1 expansion skipped: no snapshot cached for {_minus_date.date()}.")
                            else:
                                req_minus = RoutingRequest(
                                    source_code=source, 
                                    destination_code=destination, 
                                    source_stop_id=source_stop_id,
                                    destination_stop_id=dest_stop_id,
                                    src_cluster_ids=src_cluster_ids,
                                    dst_cluster_ids=dst_cluster_ids,
                                    departure_date=_minus_date, 
                                    constraints=c, 
                                    limit=internal_limit, 
                                    db_session=transit_db
                                )
                                req_minus.multi_modal = multi_modal
                                res_minus = await orchestrator.search_all_tiers(req_minus)
                                for r in res_minus:
                                    if r.journey_id not in all_unique_routes:
                                        r.metadata["day_offset"] = -1
                                        r.metadata["alt_reason"] = f"Alternative: Available on {_minus_date.strftime('%b %d')}"
                                        all_unique_routes[r.journey_id] = r
                                
                                # Task 34 Check
                                if request and await request.is_disconnected():
                                    return {"journeys": [], "aborted": True}
            
            # [Subtask 1.5] Disconnection Check 3
            if request and await request.is_disconnected():
                return {"journeys": [], "aborted": True}

            # [6.2] Smart Proximity Recovery (Zero Yield)
            recovery_tasks = []
            if len(all_unique_routes) == 0 and budget > 0.3:
                logger.info(f"Zero yield for {source}->{destination}. Triggering Proximity Discovery [Point 6].")
                from core.hubs import get_hubs_near
                
                # Fetch more alternative hubs within a larger radius if possible
                alt_sources = get_hubs_near(source_lat, source_lon, limit=2)
                alt_dests = get_hubs_near(dest_lat, dest_lon, limit=2)
                
                recovery_tasks = []
                for alt_s in alt_sources:
                    for alt_d in alt_dests:
                        if alt_s == source and alt_d == destination: continue # Skip original pair
                        
                        r_req = RoutingRequest(
                            source_code=alt_s, 
                            destination_code=alt_d, 
                            departure_date=dt, 
                            constraints=c, 
                            limit=20, 
                            db_session=transit_db
                        )
                        recovery_tasks.append(orchestrator.search_all_tiers(r_req))
                
                if recovery_tasks:
                    recovery_results = await asyncio.gather(*recovery_tasks)
                    for batch in recovery_results:
                        for r in batch:
                            if r.journey_id not in all_unique_routes:
                                r.metadata["is_proximity_alt"] = True
                                res_label = f"Suggesting: {r.segments[0].departure_code} -> {r.segments[-1].arrival_code}"
                                r.metadata["alt_reason"] = f"{res_label} (Nearby Alternative)"
                                all_unique_routes[r.journey_id] = r

                # [6.4] Forced Join via Hub (Traditional Inter-train Join)
                hub_tasks = []
                candidate_hubs = []
                if len(all_unique_routes) == 0:
                    logger.info("Still zero yield. Attempting Hub Join Fallback.")
                    candidate_hubs = list(set(get_hubs_near(source_lat, source_lon, limit=3) + \
                                         get_hubs_near(dest_lat, dest_lon, limit=3)))

                for hub_code in candidate_hubs:
                    # [6.4] Forced Join via Hub
                    # We pass our pre-resolved source/dest IDs where they match
                    req_h1 = RoutingRequest(
                        source_code=source, 
                        destination_code=hub_code, 
                        source_stop_id=source_stop_id,
                        src_cluster_ids=src_cluster_ids,
                        departure_date=dt, 
                        constraints=c, 
                        limit=50,
                        db_session=transit_db
                    )
                    req_h2 = RoutingRequest(
                        source_code=hub_code, 
                        destination_code=destination, 
                        destination_stop_id=dest_stop_id,
                        dst_cluster_ids=dst_cluster_ids,
                        departure_date=dt, 
                        constraints=c, 
                        limit=50,
                        db_session=transit_db
                    )
                    hub_tasks.append(orchestrator.search_all_tiers(req_h1))
                    hub_tasks.append(orchestrator.search_all_tiers(req_h2))
                
        
                hub_raw_results = await asyncio.gather(*hub_tasks)
                
                # Simple Join Heuristic: For each hub, join leg1 and leg2
                for i in range(0, len(hub_raw_results), 2):
                    leg1_list = hub_raw_results[i]
                    leg2_list = hub_raw_results[i+1]
                    hub_code = candidate_hubs[i//2]
                    
                    for l1 in leg1_list:
                        for l2 in leg2_list:
                            # [6.6] Time-Sensitive Join with Live Delay Infusion [Point 12]
                            l2_dep = l2.segments[0].departure_time
                            l1_arr = l1.segments[-1].arrival_time
                            
                            # Infuse Live Delay for first leg (limit to healthy budget)
                            first_leg_train = l1.segments[-1].train_number
                            delay_mins = 0
                            if budget > 0.6:
                                delay_res = await self.data_provider.get_live_status(first_leg_train)
                                delay_mins = delay_res.get("delay_mins", 0)
                                if delay_mins > 0:
                                    logger.info(f"⚡ Live Delay Infusion: Train {first_leg_train} is {delay_mins}m late. Adjusting hub arrival.")
                                    l1_arr += timedelta(minutes=delay_mins)

                            wait = (l2_dep - l1_arr).total_seconds() / 60
                            
                            # Buffers: 45m min for delayed/live join, 60m for static
                            min_buffer = 45 if delay_mins > 0 else 60
                            
                            if min_buffer <= wait <= 720:
                                # Create joined route
                                from core.data_structures import Route, TransferConnection
                                merged = Route()
                                for s in l1.segments: merged.add_segment(s)
                                for s in l2.segments: merged.add_segment(s)
                                for t in l1.transfers: merged.add_transfer(t)
                                for t in l2.transfers: merged.add_transfer(t)
                                # Add hub transfer
                                hub_tc = TransferConnection(
                                    station_id=0,
                                    station_code=hub_code,
                                    arrival_time=l1_arr,
                                    departure_time=l2_dep,
                                    duration_minutes=int(wait),
                                    station_name=hub_code,
                                    facilities_score=0.5,
                                    safety_score=0.5,
                                    platform_from=None,
                                    platform_to=None,
                                    is_multi_station=False,
                                    transfer_type="hub_transfer"
                                )
                                merged.add_transfer(hub_tc)
                                merged.metadata["ui_reasons"] = [f"Hub Transfer via {hub_code}"]
                                if wait < 75:
                                    merged.metadata["ui_reasons"].append("Tight Connection ⚠️")
                                    merged.metadata["is_high_risk_transfer"] = True
                                    merged.metadata["ui_reasons"].append("Enable Guardian Heartbeat 🛡️")
                                
                                if delay_mins > 30:
                                     merged.metadata["ui_reasons"].append(f"Leg 1 Delayed ({delay_mins}m) ⏳")

                                all_unique_routes[merged.journey_id] = merged
                                
                                # [Task 12.1] Tier-Aware Yield Threshold
                                from core.route_engine.constraints import DiscoveryModel
                                discovery_yield_target = 50 if discovery_model == DiscoveryModel.OMNISCIENT.value or discovery_model == "OMNISCIENT" else 20
                                if len(all_unique_routes) >= discovery_yield_target:
                                    break

                # [G1.2.1] FINAL FALLBACK & PREMIUM ARBITRAGE: Arbitrage Swarm (Parallel Bus/Air)
                # Task 10.1: Always inject Release Valve suggestions for premium users (budget > 0.5)
                if (len(all_unique_routes) == 0 or budget > 0.5):
                    logger.info(f"🚂 Checking Arbitrage 'Release Valves' for {source}->{destination}.")
                    from services.agents.arbitrage_agent import arbitrage_agent
                    arbitrage_results = await arbitrage_agent.find_arbitrage_routes(source, destination, dt)
                    for r in arbitrage_results:
                        if r.journey_id not in all_unique_routes:
                            r.metadata["is_arbitrage"] = True
                            r.metadata.setdefault("ui_reasons", []).append("Release Valve Alternative 🔓")
                            all_unique_routes[r.journey_id] = r

            # [Task 7 Check] If we already have results from search_res_target/expansion, use them.
            # Otherwise, we use the candidate_list from the expansion merged set.
            candidate_list = list(all_unique_routes.values())
            
            # [G1.6.1] VIRTUAL INTERLINING: Multi-Modal Stitching
            try:
                from core.route_engine.interlining_engine import interlining_engine
                # Filter for candidates to stitch
                rail_candidates = [r for r in candidate_list if r.metadata.get("mode") == "RAIL" or not r.metadata.get("mode")]
                bus_candidates = [r for r in candidate_list if r.metadata.get("mode") == "BUS"]
                
                if rail_candidates and bus_candidates:
                    interlined = await interlining_engine.find_interlined_routes(rail_candidates, bus_candidates)
                    for ir in interlined:
                         all_unique_routes[ir.journey_id] = ir
                    logger.info(f"✨ [INTERLINING] Injected {len(interlined)} multi-modal chains.")
            except Exception as e:
                logger.error(f"Interlining failed: {e}")

            # [Task 7] Verification Microservice Pattern
            # Split into Discovery -> Verification -> Ranking
            verified_routes = await self._verify_routes_parallel(list(all_unique_routes.values()), dt, quota)
            
            # [Task 7.3] Infuse ML Reliability scores for all candidates
            from services.ml.availability_heuristic import availability_heuristic
            for r in verified_routes:
                if not getattr(r, 'availability_probability', None) or r.availability_probability == 1.0:
                    # If not verified by API, use ML heuristic
                    score = availability_heuristic.get_route_availability_score(r.segments)
                    r.availability_probability = score
                    r.metadata.setdefault("ui_reasons", [])
                    r.metadata["ui_reasons"].append(f"{int(score*100)}% Confirmation Chance (AI)")
                    r.metadata["is_ml_scored"] = True
            
            # [Task 7.8] Optional Remote Microservice Re-reconciliation
            try:
                ms_provider = await container.get("microservices")
                if ms_provider and ms_provider.status == ServiceStatus.HEALTHY:
                    # Bulk reliability check logic could go here
                    pass
            except: pass

            # [9.2] High-Risk Detection: GN_WL > 50 or Probability < 0.5
            high_risk_count = sum(1 for r in verified_routes if getattr(r, 'availability_probability', 1.0) < 0.5)
            logger.info(f"Verification Results: {len(verified_routes)} routes, High Risk: {high_risk_count}")
            
            # [9.3] Auto-Trigger Tatkal Search
            if quota == "GN" and high_risk_count >= (len(verified_routes) / 2) and len(verified_routes) > 0:
                logger.info(f"High risk GN yield detected ({high_risk_count}). Auto-triggering Tatkal search [9.3].")
                req_tatkal = RoutingRequest(
                    source_code=source, 
                    destination_code=destination, 
                    source_stop_id=source_stop_id,
                    destination_stop_id=dest_stop_id,
                    src_cluster_ids=src_cluster_ids,
                    dst_cluster_ids=dst_cluster_ids,
                    departure_date=dt, 
                    constraints=c, 
                    limit=10, 
                    db_session=transit_db
                )
                tatkal_results = await orchestrator.search_all_tiers(req_tatkal)
                logger.info(f"Tatkal Search found {len(tatkal_results)} candidates.")
                # Re-verify with Quota="TQ"
                verified_tq = await self._verify_routes_parallel(tatkal_results, dt, "TQ")
                logger.info(f"Verified {len(verified_tq)} Tatkal routes.")
                
                for r in verified_tq:
                    if not isinstance(r.metadata, dict):
                        r.metadata = {}
                    r.metadata["quota"] = "TQ"
                    r.metadata["is_alternative"] = True
                    r.metadata["is_verified"] = True 
                    r.metadata.setdefault("ui_reasons", []).append("High Availability Alternative (Tatkal)")
                    all_unique_routes[r.journey_id] = r
                
                logger.info(f"Total Unique Routes after merge: {len(all_unique_routes)}")
                # Re-rank
                candidate_list = sorted(all_unique_routes.values(), key=lambda x: x.score)
                top_candidates = candidate_list[:limit]
                logger.info(f"Top {limit} candidates selected for final set.")
                
                to_verify_final = [r for r in top_candidates if not r.metadata.get("is_verified")]
                logger.info(f"Final verification needed for {len(to_verify_final)} routes.")
                
                if to_verify_final:
                    verified_new = await self._verify_routes_parallel(to_verify_final, dt, quota)
                    verified_map = {r.journey_id: r for r in verified_new}
                    verified_routes = [verified_map.get(r.journey_id, r) for r in top_candidates]
                else:
                    verified_routes = top_candidates
                
                # [Point 23] Persona-Aware Value Scoring
                # [Point 15 & 23] NIS-Aware Value Scoring
                weights = await IntelligenceService.get_current_weights(self.db) if self.db else {"availability": 1.0, "speed": 1.0, "comfort": 1.0, "safety": 1.0}
                def calculate_value_score(r):
                    # Multi-dimensional dynamic scoring
                    availability_f = getattr(r, 'availability_probability', 0.5)
                    speed_f = 1000.0 / max(1, r.total_duration)
                    comfort_f = 1.0 / (len(r.transfers) + 1)
                    safety_f = getattr(r, "safety_score", 1.0)
                    
                    score = (
                        weights["availability"] * availability_f + 
                        weights["speed"] * (speed_f / 100.0) + # Normalized speed
                        weights["comfort"] * comfort_f +
                        weights["safety"] * safety_f
                    ) * 10.0 # Scale to 0-10
                    return score

                from services.pricing_service import PricingService
                # [Optimization] Parallel Monetization & Pricing Injection
                async def inject_metadata(r):
                    if r is None:
                        return
                    metadata = getattr(r, "metadata", None) or {}
                    r.metadata = metadata
                    metadata["value_score"] = calculate_value_score(r)
                    
                    # [Generation 9] Monetization & Conversion Infusion
                    try:
                        # 1. FOMO Signals (G3.6.1)
                        from services.agents.fomo_agent import fomo_agent
                        fomo_data = await fomo_agent.get_conversion_signals(r.journey_id, getattr(r, "availability_count", 0))
                        metadata["fomo_signals"] = fomo_data.get("signals", [])
                        
                        # 2. Dynamic Pricing (G2.6.1)
                        from services.agents.pricing_dynamic_agent import pricing_dynamic_agent
                        fee_data = await pricing_dynamic_agent.calculate_convenience_fee(source, destination)
                        metadata["convenience_fee"] = fee_data
                        
                        # 3. Adaptive Upsell (G1.9.1)
                        from services.agents.upsell_agent import upsell_agent
                        addons = await upsell_agent.get_route_addons(r.to_dict())
                        metadata["addons"] = addons
                        
                        if fomo_data.get("has_high_fomo"):
                            metadata.setdefault("ui_reasons", []).append("🔥 High Demand - Book Soon!")
                    except Exception as ge:
                        logger.error(f"Gen 9 Monetization Injection failed: {ge}")

                    # [Point 1] Calculate Dynamic Unlock Fee
                    try:
                        from services.pricing_service import PricingService
                        metadata["unlock_fee"] = await PricingService.get_dynamic_unlock_fee(
                            self.db, source, destination, 
                            seats_available=getattr(r, "availability_count", None)
                        ) if self.db else 0.0
                        
                        if metadata.get("ui_reasons") is None:
                            metadata["ui_reasons"] = []
                            
                        metadata["ui_reasons"].extend(
                            PricingService.get_pricing_reasons(metadata["unlock_fee"])
                        )
                    except Exception as pe:
                        logger.warning(f"Dynamic pricing injection failed (possibly circuit open): {pe}")
                        metadata["unlock_fee"] = 0.0
                        if metadata.get("ui_reasons") is None:
                            metadata["ui_reasons"] = []

                if verified_routes:
                    await asyncio.gather(*[inject_metadata(r) for r in verified_routes])
                
                # [Point 22] Guardian Agent - Persona-Safe Routing
                from services.agents.guardian_agent import GuardianAgent
                guardian = GuardianAgent()
                safe_res = await guardian.run({"routes": verified_routes, "persona": persona})
                verified_routes = safe_res.get("routes", verified_routes)
                
                # [Task 26.8] Discovery Cache Store for future users
                if multi_layer_cache.redis and verified_routes:
                    await multi_layer_cache.put(discovery_key, verified_routes, ttl=TTL_ROUTE_SEARCH)
                    logger.info(f"💾 [NEXUS:ECHO] Persistent Discovery stored for {discovery_key}")
            else:
                # Discovery Bypass: Skip heavy gathering/verification
                verified_routes = candidate_list
                
            # Re-sort by Safety-Weighted Value Score
            # [P27] Yield Management Integration: Dynamic Surge Pricing
            from services.enhanced_pricing_service import enhanced_pricing_service
            for r in verified_routes:
                try:
                    # Convert route to a format the pricing service expects if needed
                    # Or pass the route object directly if it has the required attrs
                    new_price, breakdown = enhanced_pricing_service.calculate_final_price(r)
                    r.total_cost = new_price
                    # Inject breakdown into metadata for transparency
                    r.metadata["pricing_breakdown"] = breakdown
                except Exception as pe:
                    logger.warning(f"Pricing engine failure for {r.journey_id}: {pe}")

            # [ALGORITHM_MVP] Integrate Delay-Aware Routing
            # Apply delay predictions to route scoring
            try:
                from services.delay_aware_routing import get_delay_aware_routing
                delay_service = get_delay_aware_routing()
                if hasattr(delay_service, 'apply_delay_to_routes'):
                    verified_routes = await delay_service.apply_delay_to_routes(verified_routes, dt.date())
                    logger.info(f"Applied delay predictions to {len(verified_routes)} routes")
            except Exception as de:
                logger.warning(f"Delay-aware routing integration failed: {de}")

            # [ALGORITHM_MVP] Integrate Real-Time Route Hydration
            # Apply live status data to routes
            try:
                from services.realtime_route_hydration import get_realtime_hydration
                realtime_service = get_realtime_hydration()
                if hasattr(realtime_service, 'hydrate_routes'):
                    verified_routes = await realtime_service.hydrate_routes(verified_routes, dt.date())
                    logger.info(f"Hydrated {len(verified_routes)} routes with real-time data")
            except Exception as re:
                logger.warning(f"Real-time hydration integration failed: {re}")

            # [ALGORITHM_MVP] Record Search Event for Demand Tracking
            # Learn from search patterns for pricing and recommendations
            try:
                from services.algorithm_data_service import get_algorithm_data_service
                data_service = get_algorithm_data_service(self.db)
                data_service.record_search_event(source, destination, dt.date())
            except Exception as de:
                logger.debug(f"Data service integration failed: {de}")

            # [ALGORITHM_MVP] Generate Complete Travel Plan with Unified Planner
            # This provides multi-option travel plans with crowd awareness
            travel_plan_metadata = {}
            try:
                from services.unified_travel_planner import get_travel_planner
                planner = get_travel_planner(self.db)
                
                # Create travel request
                from services.unified_travel_planner import TravelRequest, TravelPreference, WaitPreference
                travel_req = TravelRequest(
                    origin=source,
                    destination=destination,
                    travel_date=dt.date(),
                    passenger_count=1,
                    travel_preference=TravelPreference.BALANCED,
                    wait_preference=WaitPreference.ANY_WAIT,
                    max_wait_hours=6
                )
                
                # Generate plan
                travel_plan = await planner.create_travel_plan(travel_req)
                
                # Add travel plan metadata to response
                if travel_plan and travel_plan.options:
                    # Add plan summary to response metadata
                    recommended = travel_plan.get_recommended()
                    travel_plan_metadata["travel_plan"] = {
                        "plan_id": travel_plan.plan_id,
                        "options_count": len(travel_plan.options),
                        "has_wait_option": any(o.wait_duration_minutes > 0 for o in travel_plan.options),
                        "has_multi_modal": any(o.option_type == "multi_modal" for o in travel_plan.options),
                        "recommended_departure": recommended.departure_time.isoformat() if recommended else None,
                        "recommended_fare": recommended.total_fare if recommended else 0
                    }
                    logger.info(f"Travel plan generated with {len(travel_plan.options)} options")
            except Exception as tpe:
                logger.debug(f"Travel plan generation failed: {tpe}")

            # [P28] Growth Agent Integration: Conversion Hooks
            from services.agents.growth_agent import growth_agent_swarm as growth_agent
            personalize_fn = getattr(growth_agent, "personalize_results", None)
            if callable(personalize_fn):
                personalize_fn_call = cast(Callable[..., Any], personalize_fn)
                personalize_result = personalize_fn_call(verified_routes, persona)
                if asyncio.iscoroutine(personalize_result):
                    verified_routes = await personalize_result
                else:
                    verified_routes = personalize_result

            def final_rank_score(r):
                base = r.metadata.get("value_score", 0)
                safety = getattr(r, "safety_score", 1.0)
                # If persona is ECONOMY (Family), safety has higher weight
                if persona.upper() in ["ECONOMY", "FAMILY"]:
                    return base * (safety ** 2) 
                return base * safety

            verified_routes.sort(key=final_rank_score, reverse=True)
            logger.info(f"Reranked {len(verified_routes)} routes using Safety-Weighted Value Scoring.")

            categories = CategorizationEngine.categorize(verified_routes, persona)
            
            # [Task 12.1] Bucket Preservation in Redis for Category-Aware Load More
            if multi_layer_cache.redis:
                data_key = f"search:data:{quota}:{session_id}"
                async with multi_layer_cache.redis.pipeline(transaction=True) as pipe:
                    # 1. Store global data for all verified routes
                    for r in verified_routes:
                        await pipe.hset(data_key, r.journey_id, json.dumps(r.to_dict(), default=str))
                    
                    # 2. Store specific category pools (ZSETs)
                    for bucket_name, bucket_routes in categories.items():
                        if bucket_name in ["direct", "one_transfer", "two_transfer", "three_plus_transfer"] and isinstance(bucket_routes, list):
                            cat_pool_key = f"search:pool:{bucket_name}:{quota}:{session_id}"
                            for r_dict in bucket_routes:
                                score = r_dict.get("score", 0)
                                await pipe.zadd(cat_pool_key, {r_dict["journey_id"]: score})
                            await pipe.expire(cat_pool_key, TTL_ROUTE_SEARCH)
                    
                    # 3. Store the master session pool for regular pagination
                    master_pool_key = f"search:pool:{quota}:{session_id}"
                    for r in verified_routes:
                        await pipe.zadd(master_pool_key, {r.journey_id: r.score})
                    await pipe.expire(master_pool_key, TTL_ROUTE_SEARCH)
                    await pipe.expire(data_key, TTL_ROUTE_SEARCH)
                    
                    await pipe.execute()
                    logger.info(f"💾 [REDIS:STORAGE] Session {session_id} results pooled across {len(categories)} categories.")
            
            all_hydrated_dicts = []
            seen_jids = set()
            for bucket_name, bucket_routes in categories.items():
                if isinstance(bucket_routes, list):
                    for r_dict in bucket_routes:
                        if r_dict["journey_id"] not in seen_jids:
                            all_hydrated_dicts.append(r_dict)
                            seen_jids.add(r_dict["journey_id"])

            masked_journeys = [UnlockService.mask_route(rd) for rd in all_hydrated_dicts]
            next_cursor = verified_routes[-1].score if verified_routes else None

            total_pages = math.ceil(len(candidate_list) / limit) if candidate_list else 0
            pagination = PaginationMetadata(
                total_results=len(candidate_list),
                current_page=1,
                limit=limit,
                has_next=len(candidate_list) > limit,
                total_pages=total_pages
            )

            # [P14] Intelligent Trip Stacking (Loop Suggestion)
            return_suggestion = await self._suggest_return_leg(source, destination, dt)

            latency = (time.time() - overall_start) * 1000
            final_response = {
                "status": "success",
                "source": source, "destination": destination, "session_id": session_id,
                "routes": categories,
                "data": {
                    "journeys": masked_journeys,
                    "grouped_journeys": {k: ([UnlockService.mask_route(r) for r in v] if isinstance(v, list) else v) for k, v in categories.items()},
                    "pagination": pagination.to_dict(),
                    "next_cursor": next_cursor,
                    "suggestions": [return_suggestion] if return_suggestion else []
                },
                "total_available": pagination.total_results,
                "latency_ms": int(latency),
                "jit_status": "NORMAL",
                "metadata": {
                    "expansion_triggered": expansion_triggered,
                    "latency_ms": latency,
                    "total_candidates": len(candidate_list),
                    "monetization": "tier_2_masked"
                }
            }

            if travel_plan_metadata:
                final_response["metadata"].update(travel_plan_metadata)

            # Log search with correct Date type for SQLite/SQLAlchemy
            from database.models import RouteSearchLog, SearchOutcome
            if self.db:
                log = RouteSearchLog(
                    src=source, 
                    dst=destination, 
                    date=dt.date(),
                    latency_ms=latency, 
                    ip_address=client_ip, 
                    geo_state=geo_state
                )
                self.db.add(log)
                self.db.commit()
                
                for r in verified_routes[:5]:
                    outcome = SearchOutcome(
                        search_id=str(log.id),
                        journey_id=r.journey_id,
                        predicted_value_score=getattr(r, "score", 0.0),
                        predicted_confirm_chance=getattr(r, "reliability_score", 0.8),
                        metadata_snapshot=r.to_dict()
                    )
                    self.db.add(outcome)
                
                self.db.commit()
    
                # [Point 15.2] NIS Observation: Log Recommendation Event
                if intel_svc and search_event_id:
                    await intel_svc.log_recommendations(search_event_id, verified_routes)
            
            return final_response
        finally:
            if 'transit_db' in locals() and transit_db is not None:
                transit_db.close()
            gc.enable()

    async def stream_routes(
        self, source: str, destination: str, travel_date: str, 
        budget_category: Optional[str] = None, quota: str = "GN",
        request: Optional[Request] = None
    ):
        """
        [Point 18 & 30] Zero-Block Streaming Hydration via SSE.
        Yields JSON chunks for Server-Sent Events.
        """
        overall_start = time.time()
        source = source.upper().strip()
        destination = destination.upper().strip()
        
        # 1. Initialize Context
        from database.session import SessionTransit
        transit_db = SessionTransit()
        source_stop, dest_stop = resolve_stations(transit_db, source, destination)
        if not source_stop or not dest_stop:
            yield b"data: " + json.dumps({'error': 'Station not found'}) + b"\n\n"
            return

        source_stop_id = cast(int, source_stop.id)
        dest_stop_id = cast(int, dest_stop.id)

        try:
            dt = datetime.strptime(travel_date, "%Y-%m-%d")
        except:
            dt = datetime.now()

        # [Point 15.1] NIS Observation
        from services.intelligence_service import IntelligenceService
        from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
        intel_svc = None
        search_event_id = None
        if self.db:
            intel_svc = IntelligenceService(self.db)
            search_event_id = await intel_svc.log_search(
                "stream_sid", None, source, destination, budget_category or "COMFORT"
            )

        orchestrator = UnifiedRoutingOrchestrator(self.route_engine)
        
        # Build Request
        from core.route_engine.constraints_engine import ConstraintsEngine
        from core.route_engine.base import RoutingRequest
        persona = Persona(budget_category.lower() if budget_category else "comfort")
        c = ConstraintsEngine.initialize_constraints(
            persona_str=persona.value,
            travel_date=dt.date(),
            quota=quota
        )
        
        req = RoutingRequest(
            source_code=source,
            destination_code=destination,
            source_stop_id=source_stop_id,
            destination_stop_id=dest_stop_id,
            departure_date=dt,
            constraints=c,
            db_session=transit_db
        )

        final_verified = []
        
        # 2. STREAM FROM ORCHESTRATOR
        routes = await orchestrator.stream_all_tiers(req)
        
        if request and await request.is_disconnected():
            logger.warning("🚫 Stream Aborted: Client disconnected.")
            return
            
        # Mask and Hydrate
        masked = [UnlockService.mask_route(r.to_dict()) for r in routes]
        final_verified.extend(routes)
        
        # SSE Yield
        payload = {
            "chunk": "final",
            "journeys": masked,
            "latency_ms": int((time.time() - overall_start) * 1000)
        }
        yield b"data: " + json.dumps(payload, default=str) + b"\n\n"

        # 3. Finalize NIS
        if intel_svc and search_event_id:
            await intel_svc.log_recommendations(search_event_id, final_verified)
        transit_db.close()
        yield b"event: end\ndata: {}\n\n"

    async def load_more_routes(self, session_id: str, limit: int = 15, quota: str = "GN", cursor: Optional[float] = None, category: Optional[str] = None) -> Dict[Any, Any]:
        """Subtask 1.3: Yield-Aware Load More using Cursor with Category Support."""
        start_time = time.time()
        from core.container import container
        await container.get("cache")
        await container.get("search")
        if not multi_layer_cache.redis:
            return {"error": "SESSION_EXPIRED", "message": "Search session expired or cache unavailable"}

        # [18.3] Quota-Specific Keys - Fallback to global pool or specific category pool
        if category:
            pool_key = f"search:pool:{category}:{quota}:{session_id}"
        else:
            # Fallback to old persona-based key if needed, or a default pool
            # For simplicity, we assume session_id-mapped pools from search_routes
            pool_key = f"search:pool:{quota}:{session_id}"
            
        data_key = f"search:data:{quota}:{session_id}"
        seen_key = f"search:seen:{category or 'all'}:{quota}:{session_id}"
        
        # [1.1] Cursor-Based Logic: Fetch IDs with score > cursor
        min_score = cursor if cursor is not None else -float('inf')
        
        # Get next batch of IDs from ZSET
        # We use zrangebyscore with a small offset if cursor is provided to avoid duplicates
        # But since we use seen_key, it's safe anyway.
        next_ids_raw = await multi_layer_cache.redis.zrangebyscore(
            pool_key, min_score, float('inf'), start=1 if cursor else 0, num=limit
        )
        
        if not next_ids_raw:
            return {"status": "success", "data": {"journeys": [], "pagination": {"has_next": False}}}

        journey_ids = [jid.decode() if isinstance(jid, bytes) else jid for jid in next_ids_raw]
        
        # Fetch data from Hash
        raw_data_list = await multi_layer_cache.redis.hmget(data_key, journey_ids)
        
        from core.data_structures import Route
        new_batch = []
        for raw in raw_data_list:
            if raw:
                new_batch.append(Route.from_dict(json.loads(raw)))
        
        if not new_batch:
            return {"status": "success", "data": {"journeys": [], "pagination": {"has_next": False}}}

        # Verify (Subtask 1.2)
        # Use first segment's date as baseline
        travel_date = new_batch[0].segments[0].departure_time
        verified = await self._verify_routes_parallel(new_batch, travel_date, quota)

        # Update seen
        for r in verified:
            await multi_layer_cache.redis.sadd(seen_key, r.journey_id)

        from services.unlock_service import UnlockService
        masked = [UnlockService.mask_route(r.to_dict()) for r in verified]

        next_cursor = verified[-1].score if verified else cursor
        pool_size = await multi_layer_cache.redis.zcard(pool_key)
        has_next = (await multi_layer_cache.redis.scard(seen_key)) < pool_size

        return {
            "status": "success",
            "session_id": session_id,
            "data": {
                "journeys": masked,
                "pagination": {
                    "total_results": pool_size,
                    "has_next": has_next,
                    "limit": limit,
                    "next_cursor": next_cursor
                }
            },
            "metadata": {"latency_ms": (time.time() - start_time) * 1000}
        }

    async def re_rank_routes(self, session_id: str, persona_str: str, quota: str = "GN") -> Dict[Any, Any]:
        """
        [10.4] Re-ranks existing search results based on a new persona.
        [18.3] Quota-specific keys.
        """
        start_time = time.time()
        from core.container import container
        await container.get("cache")
        if not multi_layer_cache.redis:
            return {"error": "SESSION_EXPIRED", "message": "Search session expired"}

        data_key = f"search:data:{quota}:{session_id}"
        pool_key = f"search:pool:{quota}:{session_id}"
        
        # 1. Fetch all data from Hash
        all_raw = await multi_layer_cache.redis.hgetall(data_key)
        if not all_raw:
            return {"error": "SESSION_EXPIRED", "message": "No data found for session"}

        from core.route_engine.constraints_engine import ConstraintsEngine
        from core.route_engine.scoring import RouteScorer
        from core.data_structures import Route, Persona
        
        persona = Persona(persona_str)
        constraints = ConstraintsEngine.initialize_constraints(
            persona_str=persona.value,
            travel_date=datetime.now().date()
        )
        
        # 2. Re-Score and Re-Categorize
        routes = []
        for raw in all_raw.values():
            r = Route.from_dict(json.loads(raw))
            # Re-calculate score using new weights
            r.score = await RouteScorer.score_route(r, constraints)
            routes.append(r)
            
        # 3. Update Redis Pool (ZSET) with new scores
        async with multi_layer_cache.redis.pipeline(transaction=True) as pipe:
            for r in routes:
                await pipe.zadd(pool_key, {r.journey_id: r.score})
                await pipe.hset(data_key, r.journey_id, json.dumps(r.to_dict(), default=str))
            await pipe.execute()

        # 4. Final Categorization
        from core.route_engine.categorization import CategorizationEngine
        from services.unlock_service import UnlockService
        
        # For re-rank, we only show verified or all? 
        # Usually, re-rank is for the current pool. We'll verify top 15 if needed.
        sorted_routes = sorted(routes, key=lambda x: x.score)
        categories = CategorizationEngine.categorize(sorted_routes[:30], persona)
        
        return {
            "status": "success",
            "session_id": session_id,
            "persona": persona_str,
            "data": {
                "journeys": [UnlockService.mask_route(r.to_dict()) for r in sorted_routes[:15]],
                "grouped_journeys": {k: [UnlockService.mask_route(r) for r in v] for k, v in categories.items()}
            },
            "metadata": {"latency_ms": (time.time() - start_time) * 1000}
        }

    async def _verify_routes_parallel(self, routes: List[Route], travel_date: datetime, quota: str = "GN") -> List[Route]:
        """
        [Task 12.18] Smart Tiered Verification Budget.
        Ensures high-value routes are verified first under tight RapidAPI quotas.
        """
        if not routes: return []
        
        # 1. Prioritize by Value/Complexity
        interlined = [r for r in routes if r.metadata.get("type") == "VIRTUAL_INTERLINED"]
        structural = {
             "direct": [r for r in routes if len(r.transfers) == 0 and r not in interlined],
             "1-transfer": [r for r in routes if len(r.transfers) == 1 and r not in interlined],
             "2-transfer": [r for r in routes if len(r.transfers) == 2 and r not in interlined],
             "3-plus": [r for r in routes if len(r.transfers) >= 3 and r not in interlined]
        }
        
        to_verify = []
        # Priority 1: 100% of Interlined (Rail+Air) - These are high-yield "Jumps"
        to_verify.extend(interlined)
        
        # Priority 2: Top 5 of each structural bucket (Diversity focus)
        for bucket in structural.values():
            to_verify.extend(bucket[:5])
        
        # Priority 3: Remaining budget (limit total to 25 to protect quota)
        MAX_VERIFY = 25
        if len(to_verify) < MAX_VERIFY:
            others = [r for r in routes if r not in to_verify]
            to_verify.extend(others[:MAX_VERIFY - len(to_verify)])

        logger.info(f"📊 [VERIFY:BUDGET] Selected {len(to_verify)}/{len(routes)} routes for tiered verification.")
        
        from services.rapidapi_provider import rapidapi_provider
        if rapidapi_provider.quota_latch_active:
            logger.warning("🚫 [VERIFY] RapidAPI Quota Latch Active. Bypassing live verification.")
            for r in routes:
                if not isinstance(r.metadata, dict): r.metadata = {}
                r.metadata["is_verified"] = False
                r.metadata["verification_status"] = "QUOTA_EXCEEDED"
            return routes

        # Perform verification TaskGroup with strict timeout
        tasks = [self._verify_single_route(r, travel_date, quota) for r in to_verify]
        
        if tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=6.0)
            except asyncio.TimeoutError:
                logger.warning("🕒 [VERIFY] Global Verification Timeout exceeded (6s).")
            
        return routes

    async def _verify_single_route(self, route: Route, travel_date: datetime, quota: str = "GN") -> Route:
        """Subtask 1.9: Heuristic Fallback on Timeout (>3s)."""
        try:
            # Wrap verification in 3-second timeout
            return await asyncio.wait_for(self._verify_single_route_logic(route, travel_date, quota), timeout=3.0)
        except asyncio.TimeoutError:
            logger.warning(f"Verification timeout for route {route.journey_id}. Falling back to ML heuristic.")
            from services.ml.availability_heuristic import availability_heuristic
            # Use ML heuristic (Task 1.9)
            route.availability_probability = availability_heuristic.get_route_availability_score(route.segments)
            if not isinstance(route.metadata, dict):
                route.metadata = {}
            route.metadata["is_estimated"] = True
            route.metadata["is_verified"] = False
            return route

    async def _verify_single_route_logic(self, route: Route, travel_date: datetime, quota: str = "GN") -> Route:
        """[14.1] Verification logic with Partial Rescue retry."""
        if not isinstance(route.metadata, dict):
            route.metadata = {}
        leg_results = []
        route_segments = route.segments or []
        for seg in route_segments:
            # Try verification for this leg
            res = await self._verify_leg_with_retry(seg, travel_date, route.metadata.get("day_offset", 0), quota)
            leg_results.append((seg, res))
            
        total_fare = 0.0
        total_delay = 0
        total_prob = 1.0
        any_failed = False
        
        for seg, (seat_res, fare_res, status_res) in leg_results:
            if not seat_res or seat_res.get("status") == "error":
                any_failed = True
                break

            # Update segment data from status_res
            if status_res:
                live_pf = status_res.get("platform")
                if live_pf:
                    # In a production multi-leg scenario, we'd map this carefully
                    pass 
                total_delay += status_res.get("delay_mins", 0)
            
            # [15.1] Fare Anomaly Detection: Compare with base logic
            calc_fare_res = calculate_fare(seg.distance_km, "SL") # Baseline
            calc_fare = float(calc_fare_res.get("total_fare", 1200.0))
            api_total = float(fare_res.get("total_fare", 0))
            
            if api_total > 0 and calc_fare > 0:
                deviation = abs(api_total - calc_fare) / calc_fare
                if deviation > 0.3: # [15.2] 30% Threshold
                    logger.warning(f"Fare Anomaly detected for {seg.train_number}: API={api_total}, Calc={calc_fare}. Deviation={deviation:.1%}")
                    route.metadata["is_anomaly"] = True
                    route.metadata["anomaly_reason"] = "SUSPICIOUS_FARE"
            
            # Seat availability prob
            status = str(seat_res.get("availability", "")).upper()
            if "AVAILABLE" in status or "CURR_AVBL" in status:
                total_prob *= 0.99
            elif "WL" in status:
                total_prob *= 0.4
            else:
                total_prob *= 0.5
            
            # Fare
            total_fare += float(fare_res.get("total_fare", 0))

        if any_failed:
            route.metadata["is_verified"] = False
            route.metadata["verification_error"] = "LEG_FAILED"
            return route

        route.availability_probability = total_prob
        route.total_cost = total_fare
        route.total_duration += total_delay
        route.metadata["is_verified"] = True
        return route

    async def _verify_leg_with_retry(self, seg, travel_date, day_offset, quota):
        """[14.2] SALVAGE: Retry a single leg exactly once if it fails."""
        for attempt in range(2): # Attempt 0, then retry 1
            try:
                tasks = [
                    self.data_provider.verify_seat_availability_unified(
                        trip_id=seg.trip_id,
                        travel_date=travel_date + timedelta(days=day_offset),
                        train_number=seg.train_number, from_station=seg.departure_code,
                        to_station=seg.arrival_code, quota=quota
                    ),
                    self.data_provider.verify_fare_unified(
                        segment_id=None, train_number=seg.train_number,
                        from_station=seg.departure_code, to_station=seg.arrival_code
                    ),
                    self.data_provider.get_live_status(seg.train_number)
                ]
                res = await asyncio.gather(*tasks)
                if res[0] and res[0].get("status") != "error":
                    return res
                if attempt == 0:
                    logger.warning(f"Leg verification failed for {seg.train_number}. Retrying once...")
                    await asyncio.sleep(0.5) # Wait before retry
            except Exception as e:
                if attempt == 1: raise e
        return [None, None, None]

    async def search_routes_stream(
        self, source: str, destination: str, travel_date: str, 
        budget_category: Optional[str] = None, quota: str = "GN", 
        chunk_size: int = 3,
        permitted_engines: Optional[list[str]] = None,
        discovery_only: bool = False
    ):
        """Unified Search Implementation."""
        db = self.db
        try:
            dt = datetime.strptime(travel_date, "%Y-%m-%d")
        except:
            dt = datetime.now()

        from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
        from core.route_engine.base import RoutingRequest
        from core.route_engine.constraints_engine import ConstraintsEngine
        from core.data_structures import Persona
        from services.unlock_service import UnlockService
        
        self.transit_db = SessionTransit()
        orchestrator = UnifiedRoutingOrchestrator(self.route_engine)
        persona = Persona(budget_category or "comfort")
        c = ConstraintsEngine.initialize_constraints(
            persona_str=persona.value,
            travel_date=dt.date(),
            quota=quota,
            permitted_engines=permitted_engines,
            discovery_only=discovery_only
        )

        yield {"status": "searching", "message": "Starting multi-engine discovery..."}
        
        # [Task 30.6] Progress Tracking
        total_batches = 4 # Hub, Turbo, UltraTurbo, RAPTOR
        batch_idx = 0
        chunk_size = 15
        
        # Consume the generator dynamically
        req = RoutingRequest(source_code=source, destination_code=destination, departure_date=dt, constraints=c, limit=30, db_session=self.transit_db)
        routes = await orchestrator.stream_all_tiers(request=req)
        routes_batches = []

        for i in range(0, len(routes), chunk_size):
            routes_batches.append(routes[i:i + chunk_size])

        first_discovery = True
        for batch in routes_batches:
            if not batch: continue

            batch_idx += 1
            progress = min(90, int((batch_idx / total_batches) * 100))

            # Yield unverified "speculative" results immediately for TTFR (Idea C)
            speculative_masked = [UnlockService.mask_route(r.to_dict()) for r in batch]
            for r_masked in speculative_masked: r_masked["is_verified"] = False

            if first_discovery:
                yield {
                    "status": "discovered", 
                    "message": f"Discovered {len(batch)} candidate routes from {batch[0].metadata.get('engine', 'unknown')}",
                    "tier": batch[0].metadata.get("tier", "unknown"), 
                    "journeys": speculative_masked, 
                    "is_speculative": True,
                    "progress": progress
                }
                first_discovery = False

            # [Task 30.5] Deep Verification & Global Enrichment
            verified_chunk = await self._verify_routes_parallel(batch, dt, quota)
            masked_chunk = [UnlockService.mask_route(r.to_dict()) for r in verified_chunk if r.metadata.get("is_verified")]

            if masked_chunk:
                for r_masked in masked_chunk: r_masked["is_verified"] = True
                yield {
                    "status": "partial_results", 
                    "tier": batch[0].metadata.get("tier", "unknown"), 
                    "journeys": masked_chunk, 
                    "is_speculative": False,
                    "progress": progress
                }

            await asyncio.sleep(0.01)

        yield {"status": "complete", "message": "Full system scan complete.", "progress": 100}

    def __del__(self):
        transit_db = getattr(self, 'transit_db', None)
        if transit_db is not None:
            try:
                transit_db.close()
            except:
                pass

# Global Singleton
search_service = SearchService()
