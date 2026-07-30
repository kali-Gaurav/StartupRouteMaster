import asyncio
import logging
import time
import struct
import json
from typing import List, Dict, Any, Optional, Callable, Set, cast
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session
from .shadow_orchestrator import shadow_orchestrator
import sys
from pathlib import Path

# [Task 117.9] Path normalization completed. Legacy sys.path hacks removed.
# _root = Path(__file__).resolve().parent.parent.parent
# if str(_root) not in sys.path:
#     sys.path.append(str(_root))

from .base import BaseRoutingEngine, RoutingRequest, RoutingResponse
from .constraints import RouteConstraints
from core.data_utils.structures import Route, RouteSegment, TransferConnection, Persona

from .turbo_router import TurboRouter
from .exhaustive_direct import ExhaustiveDirectEngine
from .one_hop_hub import OneHopHubEngine
from .multi_hop_discovery import MultiHopDiscoveryEngine
from .ultra_turbo import get_db_path

logger = logging.getLogger(__name__)
from .fast_router import FastPathRouter

# ── Tier-1 Features ───────────────────────────────────────────────────────
# Feature B: Query Plan Optimizer
try:
    from .query_plan_optimizer import query_plan_optimizer, SearchDepth
    _QPO_ENABLED = True
except ImportError:
    _QPO_ENABLED = False
    logger.warning("[ORCHESTRATOR] QPO not available — using default dispatch.")

# Feature C: Transfer Intelligence Score
try:
    from .tis_service import tis_service
    _TIS_ENABLED = True
except ImportError:
    _TIS_ENABLED = False
    logger.warning("[ORCHESTRATOR] TIS not available — skipping transfer scoring.")

# Feature D: Corridor Safety Bus
try:
    from .corridor_safety_bus import corridor_safety_bus
    _SAFETY_BUS_ENABLED = True
except ImportError:
    _SAFETY_BUS_ENABLED = False
    logger.warning("[ORCHESTRATOR] CorridorSafetyBus not available — skipping safety penalties.")
from .hub_router import HubRoutingEngine
from .scoring import RouteScorer
from .hydration import create_default_pipeline
from .circuit_breaker import EngineCircuitBreaker
from .throttler import EngineThrottler
from .multimodal_engine import MultimodalEngine
from core.pricing.fare_calculator import calculate_fare
from services.intelligence.demand_service import demand_service

from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import os

# [Phase 3: Patent Innovation Layer]
from core.route_engine.pareto_optimizer import pareto_optimizer
from core.redistribution.engine import redistributor
from core.knowledge.graph_store import knowledge_graph


from core.nexus.spine import NeuralSpine
from core.nexus.topology import ShardRouter, NexusCartographer, Region
from core.nexus.merge_engine import NexusMergeEngine

def get_cpu_executor():
    """[Task 14 & 17] Formalized Neural Spine access."""
    NeuralSpine.initialize()
    return NeuralSpine._executor

# Standard ThreadPool for I/O and lightweight concurrent logic
import os
workers = min(4, (os.cpu_count() or 4))
ROUTING_POOL = ThreadPoolExecutor(
    max_workers=workers,
    thread_name_prefix="routing_io_worker"
)

logger = logging.getLogger(__name__)

def _safe_int(val: Any, default: int = 0) -> int:
    """Safely convert value to int, handling alphanumeric strings like 'TEST123'."""
    if val is None: return default
    if isinstance(val, int): return val
    try:
        # Try direct conversion
        return int(val)
    except (ValueError, TypeError):
        # Handle alphanumeric strings: extract digits or use default
        try:
            digits = ''.join(filter(str.isdigit, str(val)))
            return int(digits) if digits else default
        except:
            return default

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

    async def _inject_multimodal_jumps(self, request: RoutingRequest, constraints: RouteConstraints, graph: Any):
        """[Elite] Pre-scan for direct multimodal jumps (Flights/Buses) from major hubs."""
        from core.engines.hubs import MEGA_HUBS, MAJOR_HUBS, HUB_TERMINAL_MAPPING
        from services.providers.bus_provider import bus_provider
        from database.models import Stop
        
        from services.providers.multimodal_mocks import flight_p

        # [Task 11.2] Multi-Hub Bridge Discovery
        # If the source is not a hub, we look for nearby hubs to jump from
        from core.engines.hubs import get_hubs_near
        source_stop = request.db_session.query(Stop).filter(Stop.code == request.source_code).first()
        
        hub_codes = [request.source_code] if request.source_code in (MEGA_HUBS | MAJOR_HUBS) else []
        if not hub_codes and source_stop:
            # Source is not a hub: Find top 2 nearest mega/major hubs
            hub_codes = get_hubs_near(source_stop.latitude, source_stop.longitude, limit=2)
            logger.info(f"🌐 [ORCHESTRATOR] Source {request.source_code} is not a hub. Scanning jumps from nearby hubs: {hub_codes}")

        for hub_code in hub_codes:
            jumps = []
            
            # 1. Search Buses
            bus_results = await bus_provider.search(hub_code, request.destination_code, request.departure_date.strftime("%Y-%m-%d"))
            
            # 2. Search Flights (if mega hub)
            flight_results = []
            if hub_code in MEGA_HUBS:
                flight_results = await flight_p.search(hub_code, request.destination_code, request.departure_date.strftime("%Y-%m-%d"))

            # Injection logic for RAPTOR to pick up
            dest_stop = request.db_session.query(Stop).filter(Stop.code == request.destination_code).first()
            if not dest_stop:
                continue

            for res_raw in bus_results + flight_results:
                try:
                    res = cast(Dict[str, Any], res_raw)
                    dep_dt = datetime.fromisoformat(res["departure"]) if "departure" in res else request.departure_date + timedelta(hours=4)
                    arr_dt = datetime.fromisoformat(res["arrival"]) if "arrival" in res else dep_dt + timedelta(hours=6)
                    
                    jumps.append({
                        "to_stop_id": dest_stop.id,
                        "departure_time": dep_dt,
                        "arrival_time": arr_dt,
                        "distance_km": res.get("distance_km", 500.0),
                        "type": res["transport_type"].upper(),
                        "provider_id": res["provider_id"],
                        "cost": res.get("total_cost", 0.0)
                    })
                except Exception as e:
                    logger.warning(f"Failed to parse multimodal result: {e}")
            
            constraints.multimodal_jumps[hub_code] = jumps

    async def _inject_safety_overlay(self, request: RoutingRequest, constraints: RouteConstraints):
        """[Task RM-007] Fetch real-time Sathi counts and convert to safety scores (0.0 - 1.0)"""
        from services.sathi_service import SathiService
        from database.session import SessionUser
        
        db = None
        try:
            db = SessionUser()
            sathi_service = SathiService(db)
            counts = await sathi_service.get_active_sathi_counts()
            
            # Map station_code -> station_id for the current graph
            graph = request.graph or self.engine.graph
            if not graph: return
            
            scores = {}
            for code, count in counts.items():
                stop = graph.get_stop_by_code(code)
                if stop:
                    # Normalize: 1 Sathi = 0.7, 2+ = 0.9, 5+ = 1.0. Base is 0.5.
                    score = 0.5 + min(0.5, count * 0.2)
                    scores[stop.id] = score
            
            constraints.station_safety_scores = scores
            logger.info(f"🛡️ [SAFETY:OVERLAY] Injected scores for {len(scores)} stations.")
        except Exception as e:
            logger.warning(f"Failed to inject safety overlay: {e}")
        finally:
            if db:
                db.close()

    def get_health(self) -> Dict[str, Any]:
        """[Task 40.3 / 41.9] High-Efficiency Health Metrics for VPS monitoring."""
        return {
            "circuits": {name: circuit.get_stats() for name, circuit in self.circuits.items()},
            "throttlers": {name: th.get_stats() for name, th in self.throttlers.items()},
            "engines_registered": list(self.engines.keys())
        }

    def __init__(self, route_engine_instance=None):
        self.engine = route_engine_instance
        db_path = get_db_path()
        from .tbr_router import TripBasedRouter
        from .raptor import OptimizedRAPTOR
        from .multimodal_engine import MultimodalEngine
        self.engines: Dict[str, BaseRoutingEngine] = {
            "hub_tier_0": HubRoutingEngine(),
            "exhaustive_direct": ExhaustiveDirectEngine(db_path),
            "one_hop_hub": OneHopHubEngine(db_path),
            "multi_hop_discovery": MultiHopDiscoveryEngine(db_path),
            "turbo_router": TurboRouter(),
            "fastpath_bfs": FastPathRouter(),
            "raptor": OptimizedRAPTOR(),
            "trip_based": TripBasedRouter(),
            "multimodal": MultimodalEngine()
        }
        self.hub_router = self.engines["hub_tier_0"]
        self.exhaustive_direct = self.engines["exhaustive_direct"]
        self.one_hop_hub = self.engines["one_hop_hub"]
        self.multi_hop_discovery = self.engines["multi_hop_discovery"]
        self.fast_router = self.engines["fastpath_bfs"]
        self.raptor = self.engines["raptor"]
        self.tbr_router = self.engines["trip_based"] # [Task 27.17]
        
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

        # Initialize Hydration Pipeline from Middleware
        self.hydration_pipeline = create_default_pipeline()

        # [Task 40.2] Initialize Intelligent Circuits for VPS Stability
        self.circuits: Dict[str, EngineCircuitBreaker] = {
            name: EngineCircuitBreaker(name) for name in self.engines.keys()
        }

    async def search_all_tiers(
        self,
        request: RoutingRequest,
        skip_heavy: bool = False,
        source_stop=None,
        dest_stop=None,
        on_progress=None,
        discovery_cache_key=None
    ) -> List[Route]:
        # [Task RM-007] Inject real-time safety scores before searching
        if request.db_session:
            await self._inject_safety_overlay(request, request.constraints)

        return await self.stream_all_tiers(
            request=request,
            skip_heavy=skip_heavy,
            source_stop=source_stop,
            dest_stop=dest_stop,
            on_progress=on_progress,
            discovery_cache_key=discovery_cache_key
        )

    async def _inject_realtime_heartbeat(self, routes: List[Route], db: Session):
        """
        [P1 & P9] Cerebral Synapse Connection + Reliability Injection.
        Injects proactively synced status and historical reliability weights.
        """
        if not routes or not db:
            return
            
        start_ts = time.perf_counter()
        station_codes = set()
        for r in routes:
            for seg in r.segments:
                station_codes.add(str(getattr(seg, "from_station_code", getattr(seg, "departure_code", ""))).upper())
        
        from database.models import StationRealtimeHeartbeat
        try:
            heartbeats = db.query(StationRealtimeHeartbeat).filter(
                StationRealtimeHeartbeat.station_code.in_(list(station_codes))
            ).all()
            hb_map = {str(hb.station_code).upper(): hb for hb in heartbeats}
        except Exception as e:
            logger.warning(f"Heartbeat DB lookup failed: {e}")
            hb_map = {}
        
        now = datetime.utcnow()
        for r in routes:
            r_guardian_score = 0.0
            r_active_agents = 0
            
            for seg in r.segments:
                seg_from_code = str(getattr(seg, "from_station_code", getattr(seg, "departure_code", ""))).upper()
                hb = hb_map.get(seg_from_code)
                
                if hb is not None:
                    # 1. Pulse Verification (Delay/Status)
                    expires_at = cast(Optional[datetime], getattr(hb, "expires_at", None))
                    if expires_at is None or expires_at > now:
                        seg.metadata["source"] = "pulse"
                        trains = hb.trains_json if isinstance(hb.trains_json, list) else []
                        match = next((t for t in trains if t.get("train_no") == seg.train_number), None)
                        if match:
                            seg.metadata["status"] = match.get("status", "ON_TIME")
                            seg.metadata["delay"] = match.get("delay", 0)
                            if "available_seats" in match:
                                seg.metadata["live_seats"] = match.get("available_seats")
                            r.metadata["heartbeat_verified"] = True
                    
                    # 2. [Task 41.B] Social Trust Pulse
                    seg.metadata["guardian_score"] = getattr(hb, "guardian_score", 0.0)
                    seg.metadata["active_agents"] = getattr(hb, "active_agents_count", 0)
                    r_guardian_score = max(r_guardian_score, seg.metadata["guardian_score"])
                    r_active_agents += seg.metadata["active_agents"]

            # Aggregate route-level social pulse
            r.metadata["social_pulse"] = {
                "guardian_score": r_guardian_score,
                "agent_presence": r_active_agents > 0,
                "total_agents": r_active_agents
            }
            
        latency = (time.perf_counter() - start_ts) * 1000
        if latency > 10.0: # Audit only slow pulses
            logger.info(f"📊 [LATENCY AUDIT:HEARTBEAT] Processed {len(routes)} routes in {latency:.2f}ms.")

    def _is_valid_route(self, route: Route) -> bool:
        return all(
            getattr(seg, 'departure_time', None) is not None and
            getattr(seg, 'arrival_time', None) is not None
            for seg in route.segments
        )

    def _filter_hazardous_routes(self, routes: List[Route]) -> List[Route]:
        """
        [P20.4] SOS Vacuuming.
        Removes routes passing through high-hazard stations.
        """
        if not routes: return []
        
        safe_routes = []
        for r in routes:
            max_hazard = 0.0
            for seg in r.segments:
                # Check from_station
                dep_code = str(getattr(seg, "from_station_code", getattr(seg, "departure_code", ""))).upper()
                max_hazard = max(max_hazard, knowledge_graph.get_hazard_level(dep_code))
                
                # Check to_station
                arr_code = str(getattr(seg, "to_station_code", getattr(seg, "arrival_code", ""))).upper()
                max_hazard = max(max_hazard, knowledge_graph.get_hazard_level(arr_code))
            
            if max_hazard < 0.8: # Tolerance threshold
                if max_hazard > 0.0:
                    r.score = (r.score or 50.0) * (1.0 - max_hazard)
                    r.metadata["safety_warning"] = "Path near active incident"
                safe_routes.append(r)
            else:
                logger.info(f"🛡️ [SOS:VACUUM] Rerouted away from hazardous corridor (Hazard: {max_hazard})")
                
        return safe_routes

    def _apply_demand_yield_boost(self, routes: List[Route], source: str, destination: str):
        """
        [Phase 3] Demand-Aware Biasing.
        Boosts route scores for high-demand/low-yield corridors to encourage exploration.
        """
        demand_score = demand_service.get_corridor_demand(source, destination)
        if demand_score > 0.1:
            boost = 1.0 + (demand_score * 0.15) # Up to 15% boost
            logger.info(f"📈 [ORCHESTRATOR:BOOST] Applying {boost:.2f}x Yield Boost for {source}->{destination} (Demand: {demand_score:.2f})")
            for r in routes:
                r.score = (r.score or 50.0) * boost
                r.metadata["demand_yield_boost"] = True

    async def _filter_cancelled_trains(self, routes: List[Route], departure_date: datetime, db) -> List[Route]:
        if not routes:
            return []
        if db is None or departure_date is None:
            return routes
        try:
            date_str = departure_date.strftime("%Y-%m-%d")
            c_rows = db.execute(text("SELECT train_no FROM cancelled_trains WHERE travel_date = :dt"), {"dt": date_str}).fetchall()
            cancelled_trains = {str(r[0]) for r in c_rows if r and r[0] is not None}
            filtered_routes = []
            for route in routes:
                train_numbers = {getattr(seg, 'train_number', None) for seg in getattr(route, 'segments', [])}
                if not train_numbers.intersection(cancelled_trains):
                    filtered_routes.append(route)
            return filtered_routes
        except Exception as e:
            logger.warning(f"Orchestrator cancellation filter failed: {e}")
            return routes

    async def _search_tier_0_hubs_async(self, src_id: int, dst_id: int, date: datetime, db) -> List[Route]:
        if not db or not src_id or not dst_id:
            return []
        try:
            return await asyncio.to_thread(
                cast(HubRoutingEngine, self.hub_router)._search_tier_0_hubs,
                [src_id],
                [dst_id],
                date,
                db
            )
        except Exception as e:
            logger.error(f"Tier 0 hub search failed: {e}")
            return []

    async def stream_all_tiers(
        self,
        request: RoutingRequest,
        skip_heavy: bool = False,
        source_stop=None,
        dest_stop=None,
        on_progress: Optional[Callable[[float], None]] = None,
        discovery_cache_key: Optional[str] = None
    ) -> List[Route]:
        # [Task 30/105] Elite Omniscient Streaming Orchestrator
        source_code = request.source_code
        destination_code = request.destination_code
        departure_date = request.departure_date
        constraints = request.constraints
        limit = request.limit
        db = request.db_session
        search_iteration = request.metadata.get("search_iteration", 0)

        # [Day 10] Multi-Layer Cache Check (Bypass heavy compute if hot)
        from services.multi_layer_cache import multi_layer_cache
        cache_key = f"nexus:search:{source_code}:{destination_code}:{departure_date.strftime('%Y%m%d')}:{constraints.persona.value}"
        if not request.force_refresh:
            try:
                cached_res = await multi_layer_cache.get(cache_key)
                if cached_res:
                    # Reconstruct Route objects if they are dicts
                    if isinstance(cached_res, list) and len(cached_res) > 0 and isinstance(cached_res[0], dict):
                        from shared.models.route import Route
                        cached_res = [Route(**r) for r in cached_res]
                    logger.info(f"⚡ [CACHE:HIT] Serving {len(cached_res)} routes from L2 Cache.")
                    return cached_res
            except Exception as e:
                logger.warning(f"Cache check failed: {e}")
                
        # ── [Feature B] QPO: Analyze query BEFORE dispatching engines ─────────
        qpo_plan = None
        if _QPO_ENABLED:
            try:
                qpo_plan = query_plan_optimizer.analyze(
                    src_code=source_code,
                    dst_code=destination_code,
                    departure_datetime=departure_date,
                    db=db,
                )
                # Apply QPO recommendations to constraints
                if qpo_plan.max_journey_hours:
                    constraints.max_journey_hours = qpo_plan.max_journey_hours
                if qpo_plan.use_read_replica:
                    request.metadata["use_read_replica"] = True
                if qpo_plan.recommended_hub_limit:
                    constraints.hub_limit = qpo_plan.recommended_hub_limit
                
                logger.info(f"🧠 [QPO] Plan: {qpo_plan.reasoning}")
            except Exception as _qpo_err:
                logger.warning(f"[QPO] Analysis failed (non-fatal): {_qpo_err}")

        # ── [Feature D] Safety Bus: Check for active corridor alerts ──────────
        if _SAFETY_BUS_ENABLED:
            try:
                safety_events = corridor_safety_bus.get_all_active_events()
                if safety_events:
                    # Inject active event station codes into constraints so engines can check them
                    affected_stations = set()
                    for ev in safety_events:
                        affected_stations.update(ev.station_codes)
                    constraints.metadata["safety_blocked_stations"] = list(affected_stations)
                    logger.warning(
                        f"🚨 [SafetyBus] {len(safety_events)} active corridor alerts. "
                        f"Affected: {list(affected_stations)[:5]}..."
                    )
            except Exception as _sb_err:
                logger.warning(f"[SafetyBus] Check failed (non-fatal): {_sb_err}")

        # --- Phase 1: Engine Strategy Selection ---
        active_engines = []
        
        # [Task 12.3] Omniscient Asset Management (Business Tier Aware)
        from services.rapidapi_provider import rapidapi_provider
        from .constraints import DiscoveryModel
        
        model = constraints.discovery_model or DiscoveryModel.BACKBONE
        api_available = rapidapi_provider.is_healthy and not rapidapi_provider.quota_latch_active
        
        # [Load More] Expansion Logic (VYA Strategy)
        search_iteration = request.metadata.get("search_iteration", 0)
        
        if qpo_plan and qpo_plan.engine_priority:
            # QPO driven selection
            active_engines = qpo_plan.engine_priority
            # Filter by API availability if multimodal is in list
            if not api_available and "multimodal" in active_engines:
                active_engines = [e for e in active_engines if e != "multimodal"]
        elif search_iteration > 0:
            # Iteration 1+: Deep discovery, multimodal jumps, and relaxed transfer windows
            active_engines = ["multi_hop_discovery", "multimodal", "raptor"]
            request.limit = 150 
            constraints.max_transfers = min(constraints.max_transfers + 1, 5)
            constraints.transfer_window_max = 24 * 60 # 24 hours
            logger.info(f"🔍 [EXPANSION] Iteration {search_iteration}: Depth increased to {constraints.max_transfers}T.")
        else:
            if model == DiscoveryModel.BACKBONE:
                 active_engines = ["exhaustive_direct", "turbo_router"]
                 constraints.max_transfers = min(constraints.max_transfers, 1)
            elif model == DiscoveryModel.MULTIMODAL:
                 active_engines = ["exhaustive_direct", "one_hop_hub", "turbo_router", "raptor"]
                 if api_available: active_engines.append("multimodal")
            elif model == DiscoveryModel.OMNISCIENT:
                 # The "Discovery Squad" Full Stack
                 active_engines = ["exhaustive_direct", "one_hop_hub", "multi_hop_discovery", "raptor", "trip_based"]
                 if api_available: active_engines.append("multimodal")
                 
                 constraints.search_depth = "DEEP"
                 constraints.max_transfers = max(constraints.max_transfers, 5)
                 constraints.timeout_ms = max(constraints.timeout_ms, 15000)
        
        # Map QPO alias to internal engine names if needed
        qpo_map = {
            "turbo_direct": "exhaustive_direct",
            "turbo": "turbo_router",
            "fast": "fastpath_bfs",
            "hub": "one_hop_hub"
        }
        active_engines = [qpo_map.get(e, e) for e in active_engines]
        
        logger.info(f"🚀 [DISPATCH] Mode: {model} | Iteration: {search_iteration} | Engines: {active_engines}")
        if model == DiscoveryModel.OMNISCIENT:
            constraints.metadata["verification_mode"] = "ELITE_VERIFY"
            logger.info("🧠 [ORCHESTRATOR] Tier 3: ELITE / OMNISCIENT (Premium + 5-Transfer DEEP).")
             
        # [Safety Engine] Propagate passengers to constraints for scoring
        constraints.passengers = getattr(request, "passengers", [])
        
        # Constraints override
        if constraints.permitted_engines:
            active_engines = [e for e in active_engines if any(pe.lower() in e.lower() for pe in constraints.permitted_engines)]

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
            # [Safe Access] Check if engine has graph resolution capabilities
            if hasattr(self.engine, "_get_current_graph"):
                graph = await self.engine._get_current_graph(departure_date)
            else:
                from core.route_engine.engine import get_route_engine
                engine_alt = get_route_engine()
                graph = await engine_alt._get_current_graph(departure_date)
            # Ensure all graph-dependent routers have the latest graph
            self.fast_router.graph = graph
            self.raptor.graph = graph

            # [Task 126] Isolated Request Overlay (Copy-on-Write)
            # This prevents concurrent requests from corrupting shared real-time state.
            request_overlay = graph.overlay.fork()
            await request_overlay.sync_with_db(db, departure_date.date(), graph.snapshot)
            
            # [Task 12.1] Regional Topology Pruning (Nexus Fiber)
            src_region = NexusCartographer.get_region_for_station(source_code)
            dst_region = NexusCartographer.get_region_for_station(destination_code)
            required_shards = ShardRouter.get_required_shards(source_code, destination_code, src_region, dst_region)
            
            logger.info(f"🌐 [TOPOLOGY] Query: {src_region} -> {dst_region} | Required Shards: {required_shards}")
            
            # Inject isolated overlay into request metadata for engines
            request.metadata["overlay"] = request_overlay
            request.metadata["shards"] = required_shards
            
            # Fetch cancelled trips for this request scope
            date_str = departure_date.strftime("%Y-%m-%d")
            c_rows = db.execute(text("SELECT train_no FROM cancelled_trains WHERE travel_date = :dt"), {"dt": date_str}).fetchall()
            constraints.metadata["cancelled_trip_ids"] = {_safe_int(r[0]) for r in c_rows if r and r[0]}
            
            if not source_stop or not dest_stop:
                source_stop, dest_stop = await asyncio.to_thread(resolve_stations, db, source_code, destination_code)
            
            if not source_stop or not dest_stop:
                return []

            # [Task 5] Metro-Group Expansion: Resolve all stations in the metropolitan area
            from utils.station_utils import get_metro_group_codes
            
            def _resolve_cluster_ids_sync(code: str, session) -> List[int]:
                if isinstance(code, int):
                    return [code]
                c_str = str(code).upper().strip()
                codes = get_metro_group_codes(c_str)
                
                ids: Set[int] = set()
                q_stops = f"SELECT id FROM stops WHERE code IN ({','.join([':c'+str(i) for i in range(len(codes))])})"
                params = {f"c{i}": c for i, c in enumerate(codes)}
                for r in session.execute(text(q_stops), params).fetchall():
                    if r and r[0] is not None:
                        ids.add(_safe_int(r[0]))
                if not ids:
                    return []
                
                q_clusters = f"""
                    SELECT scm2.station_id 
                    FROM station_cluster_mapping scm1 
                    JOIN station_cluster_mapping scm2 ON scm1.cluster_id = scm2.cluster_id 
                    WHERE scm1.station_id IN ({','.join([':s'+str(i) for i in range(len(ids))])})
                """
                params_cl = {f"s{i}": sid for i, sid in enumerate(ids)}
                try:
                    for r in session.execute(text(q_clusters), params_cl).fetchall():
                        if r and r[0] is not None:
                            ids.add(_safe_int(r[0]))
                except Exception:
                    pass # Table might not exist
                return list(ids)

            # Resolve clusters using the primary DB session
            src_cluster_ids = [cast(int, i) for i in await asyncio.to_thread(_resolve_cluster_ids_sync, source_code, db)]
            dst_cluster_ids = [cast(int, i) for i in await asyncio.to_thread(_resolve_cluster_ids_sync, destination_code, db)]
            
            if not src_cluster_ids: src_cluster_ids = [source_stop.id]
            if not dst_cluster_ids: dst_cluster_ids = [dest_stop.id]

            # [Elite: Hub Bridge] Inject Multimodal Jumps if requested
            if getattr(request, 'multi_modal', False):
                await self._inject_multimodal_jumps(request, constraints, graph)

            # Resolved codes for engines that prefer codes
            src_cluster_codes = get_metro_group_codes(source_code)
            dst_cluster_codes = get_metro_group_codes(destination_code)

            from core.data_utils.context import request_timeout_ctx
            total_timeout = request_timeout_ctx.get() or 25.0 # Increased from 15.0 for deep discovery yield
            
            engine_limit = max(limit * 2, 50) 
            
            from database.session import SessionTransit
            
            # [Latency Fix] Streaming TTFR (Time to First Route)
            # Instead of waiting for all engines, we yield chunks of results as they arrive.
            seen_jids: Set[str] = set()
            
            async def process_and_yield(name, coro, timeout):
                # Each engine task gets its OWN session to prevent concurrent session corruption
                db_internal = SessionTransit()
                try:
                    start_time = time.perf_counter()
                    async with asyncio.timeout(timeout):
                        response = await coro

                    if not response:
                        return []

                    res = response.routes if hasattr(response, "routes") else (response if isinstance(response, list) else [])
                    if not res:
                        return []

                    # 1. Basic Validation & Metadata
                    all_routes = [r for r in res if self._is_valid_route(r)]
                    for r in all_routes:
                        r.metadata["engine"] = name.lower()

                    # 2. Parallel Foundation Filters (Optimized for Day 1)
                    all_routes = await self._filter_cancelled_trains(all_routes, departure_date, db_internal)
                    
                    # 3. [Aeon] Inject Pulse (Reliability + Social Trust)
                    await self._inject_realtime_heartbeat(all_routes, db_internal)

                    # 3.1 [Feature D] Corridor Safety Bus: Apply dynamic penalties for active alerts
                    if _SAFETY_BUS_ENABLED:
                        for r in all_routes:
                            # Collect all unique stations in this route
                            route_stations = set()
                            for seg in r.segments:
                                route_stations.add(seg.departure_code)
                                route_stations.add(seg.arrival_code)
                            
                            safety_penalty = corridor_safety_bus.get_corridor_penalty(list(route_stations))
                            if safety_penalty > 0:
                                safety_factor = (1.0 - (min(safety_penalty, 120) / 240.0))
                                r.score = (r.score or 50.0) * safety_factor
                                r.safety_score = (getattr(r, 'safety_score', 1.0) + safety_factor) / 2.0
                                r.metadata["safety_penalty_mins"] = safety_penalty
                                r.metadata["safety_status"] = "CAUTION"
                                logger.info(f"🚨 [SafetyBus] Applied {safety_penalty}m penalty to route {r.journey_id}")

                    # 3.2 [Feature C] TIS: Calculate Transfer Intelligence Score
                    if _TIS_ENABLED:
                        for r in all_routes:
                            if not r.transfers:
                                continue
                                
                            tis_scores = []
                            for i, trans in enumerate(r.transfers):
                                # Map segments to transfer
                                incoming = r.segments[i]
                                outgoing = r.segments[i+1]
                                
                                try:
                                    tis_res = await tis_service.score_transfer(
                                        incoming_train_id=incoming.train_number,
                                        outgoing_train_id=outgoing.train_number,
                                        transfer_station_code=trans.station_code,
                                        arr_minutes=tis_service._parse_time_to_min(trans.arrival_time),
                                        dep_minutes=tis_service._parse_time_to_min(trans.departure_time),
                                        db=db_internal
                                    )
                                    tis_scores.append(tis_res.score)
                                    # Inject metadata into transfer object
                                    trans.safety_score = tis_res.score
                                    if "tis" not in trans.to_dict(): # Metadata check
                                        trans.to_dict()["tis"] = {
                                            "score": tis_res.score,
                                            "risk_level": tis_res.risk_level.value,
                                            "on_time_prob": tis_res.on_time_probability,
                                            "reason": tis_res.reason
                                        }
                                except Exception as _tis_err:
                                    logger.warning(f"TIS calculation failed for route {r.journey_id}: {_tis_err}")

                            if tis_scores:
                                avg_tis = sum(tis_scores) / len(tis_scores)
                                r.reliability = (r.reliability + avg_tis) / 2.0
                                r.metadata["tis_avg"] = round(avg_tis, 2)
                                r.metadata["tis_count"] = len(tis_scores)

                    # 4. Bucketing by Transfers (Tiered Yield)
                    new_routes = []
                    for r in all_routes:
                        if r.journey_id not in seen_jids:
                            seen_jids.add(r.journey_id)
                            new_routes.append(r)

                    yield_stats = {
                        "raw": len(res),
                        "valid": len(all_routes),
                        "deduplicated": len(new_routes)
                    }
                    
                    latency_total = (time.perf_counter() - start_time) * 1000
                    for r in new_routes:
                        r.metadata["orchestrator_latency_ms"] = round(latency_total, 2)
                        r.metadata["yield_stats"] = yield_stats
                        if "tier" not in r.metadata:
                            engine_nm = r.metadata.get("engine", "default")
                            r.metadata["tier"] = 1 if "ultra" in engine_nm else (2 if "turbo" in engine_nm else 3)

                    return new_routes
                except Exception as e:
                    logger.error(f"⚠️ Engine {name} failed or timed out: {e}")
                    return []
                finally:
                    db_internal.close()

            def is_allowed(name: str) -> bool:
                if not constraints.permitted_engines: return True
                return any(e.lower() in name.lower() for e in constraints.permitted_engines)

            tasks = []
            if is_allowed("HubTier0"):
                tasks.append(asyncio.create_task(process_and_yield("HubTier0", self._search_tier_0_hubs_async(cast(int, source_stop.id), cast(int, dest_stop.id), departure_date, db), total_timeout)))
            
            # Using Strategy registry for new engines
            for name, engine in self.engines.items():
                if name in active_engines:
                    # update request with latest cluster logic
                    request.src_cluster_ids = cast(List[int], src_cluster_ids)
                    request.dst_cluster_ids = cast(List[int], dst_cluster_ids)
                    request.graph = graph
                    
                    # specific timeouts
                    t = total_timeout
                    if "fastpath" in name.lower(): t = total_timeout * 0.8
                    if "raptor" in name.lower(): t = total_timeout * 0.9
                    if "multimodal" in name.lower(): t = total_timeout * 1.5 # Allow more time for external APIs
                    
                    tasks.append(asyncio.create_task(process_and_yield(name, engine.find_routes(request), t)))

            if not tasks:
                return []

            done, pending = await asyncio.wait(tasks, timeout=total_timeout)
            for task in pending:
                task.cancel()

            merged_routes: List[Route] = []
            for task in done:
                try:
                    chunk = task.result()
                    if chunk:
                        merged_routes.extend(chunk)
                except Exception as e:
                    logger.error(f"Orchestrator task failed: {e}")

            # --- Phase 1.5: Final Merged Audit ---
            for r in merged_routes:
                logger.info(f"📍 [ORCHESTRATOR:AUDIT] JID:{r.journey_id} Segs:{len(r.segments)} Engine:{r.metadata.get('engine')}")
            
            # --- Phase 2: Multi-Modal Interlining Pass (Task 12.5) ---
            interlined_results = []
            if model in [DiscoveryModel.MULTIMODAL, DiscoveryModel.OMNISCIENT]:
                rail_routes = [r for r in merged_routes if r.metadata.get("mode", "RAIL") == "RAIL"]
                # Multimodal engine identifies segments as individual modes
                flight_routes = [r for r in merged_routes if r.metadata.get("mode") == "FLIGHT"]
                bus_routes = [r for r in merged_routes if r.metadata.get("mode") == "BUS"]
                
                if rail_routes:
                    from .interlining_engine import interlining_engine
                    # Create pools for recursive discovery
                    pools = []
                    if flight_routes: pools.append(flight_routes)
                    if bus_routes: pools.append(bus_routes)
                    
                    if pools:
                        # Start recursive stitching from Rail routes
                        stitched = await interlining_engine.find_interlined_routes(
                            rail_routes, 
                            pools[0], 
                            depth=1, 
                            all_available_pools=pools
                        )
                        interlined_results.extend(stitched)
                        logger.info(f"🧬 [ORCHESTRATOR:STITCH] Created {len(stitched)} recursive multimodal 'Jump' routes.")
            
            merged_routes.extend(interlined_results)

            # --- Phase 2.5: Demand Yield Biasing ---
            self._apply_demand_yield_boost(merged_routes, source_code, destination_code)

            # --- Phase 3: Safety & SOS Vacuuming ---
            pre_safety_count = len(merged_routes)
            merged_routes = self._filter_hazardous_routes(merged_routes)
            post_safety_count = len(merged_routes)

            # [Phase 3: Patent Optimization]
            # 1. Apply Pareto Frontier to ensure diverse, optimal choices
            pre_pareto_count = len(merged_routes)
            final_routes = pareto_optimizer.find_frontier(merged_routes, discovery_model=model)
            post_pareto_count = len(final_routes)
            
            logger.info(f"📊 [YIELD] Merge: {pre_safety_count} -> Safety: {post_safety_count} -> Pareto: {post_pareto_count}")
            
            # 2. Sort the frontier by persona preference
            if constraints.persona in (Persona.BUDGET, Persona.ECONOMY):
                final_routes.sort(key=lambda x: (x.total_cost, x.total_duration))
            elif constraints.persona == Persona.EMERGENCY:
                from core.data_utils.structures import ensure_datetime
                final_routes.sort(key=lambda x: (ensure_datetime(x.segments[0].departure_time), x.total_duration))
            elif constraints.persona in (Persona.COMFORT, Persona.PREMIUM):
                final_routes.sort(key=lambda x: (len(x.transfers), -x.score))
            else:
                final_routes.sort(key=lambda x: -x.score)

            # [Phase 6: Cross-Modal Arbitrage]
            from services.multi_layer_cache import multi_layer_cache
            cache_key = f"nexus:search:{source_code}:{destination_code}:{departure_date.strftime('%Y%m%d')}:{constraints.persona.value}"
            try:
                from services.agents.arbitrage_agent import arbitrage_agent
                await arbitrage_agent.run({"routes": final_routes, "persona": constraints.persona})
            except Exception as e:
                logger.warning(f"Arbitrage analysis failed: {e}")

            # 3. [Redistribution] Analyze for network load balancing
            # If top routes are saturated, suggest 'Wait & Flow' alternatives
            redist_options = await redistributor.analyze_and_redistribute(
                request, final_routes, search_callback=self.stream_all_tiers
            )
            if redist_options:
                logger.info(f"🔄 [REDISTRIBUTION] Generated {len(redist_options)} incentivized alternatives.")
                # We inject these into the request metadata or a dedicated response field
                # For now, we tag the routes themselves or prepare metadata for the caller
                for opt in redist_options:
                    # In a real API, this would be a separate 'suggestions' field
                    pass

            # ── [Feature C] TIS: Score transfer risk on all multi-leg routes ──────
            if _TIS_ENABLED:
                try:
                    for route in final_routes:
                        if len(route.segments) >= 2:
                            legs = []
                            for seg in route.segments:
                                legs.append({
                                    "train": getattr(seg, "train_number", ""),
                                    "to": str(getattr(seg, "to_station_code", getattr(seg, "arrival_code", ""))).upper(),
                                    "arr": str(getattr(seg, "arrival_time", "00:00:00")),
                                    "dep": str(getattr(seg, "departure_time", "00:00:00")),
                                })
                            tis_score, tis_risk = await tis_service.score_route_transfers(legs, db=db)
                            route.metadata["tis_score"] = tis_score
                            route.metadata["tis_risk"] = tis_risk.value
                            # Penalize HIGH_RISK transfers in scoring using persona-aware weights
                            if (tis_risk.value == "HIGH_RISK" or tis_score < 0.6) and route.score:
                                # Scale penalty by TIS weight (e.g., FAMILY:5.0 -> ~25%, BUDGET:1.0 -> ~5%)
                                penalty_factor = 0.05 * constraints.weights.tis
                                route.score = route.score * (1.0 - min(penalty_factor, 0.4)) 
                                logger.info(f"⚠️ [TIS] Applied {round(penalty_factor*100)}% penalty to route {route.journey_id} (Persona: {constraints.persona.value})")
                except Exception as _tis_err:
                    logger.warning(f"[TIS] Scoring failed (non-fatal): {_tis_err}")

            # ── [Feature B] QPO: Update cache TTL based on QPO plan ──────────────
            cache_ttl = 3600  # default 1 hour
            if qpo_plan:
                cache_ttl = qpo_plan.cache_ttl_seconds

            # [Day 10] Save to Multi-Layer Cache
            if final_routes and not request.force_refresh:
                await multi_layer_cache.put(cache_key, final_routes, ttl=cache_ttl, use_pickle=True)

            # [Elite Telemetry] Record latency for adaptive throttling
            total_latency_ms = (time.perf_counter() - start_time) * 1000
            from core.nexus.telemetry import nexus_telemetry
            asyncio.create_task(nexus_telemetry.record_request(total_latency_ms))
            
            # Record redistribution success if options found
            if redist_options:
                request.metadata["redistribution_options"] = redist_options
                request.metadata["redistribution_summary"] = redistributor.generate_redistribution_summary(redist_options)

            # --- Phase 4: Visible Yield Architecture (VYA) Bucketing ---
            bucketed_results = self._bucket_and_rank_results(final_routes, limit=limit)
            
            # [Phase 3] Shadow Intelligence Audit (Background)
            for bucket in bucketed_results.values():
                if isinstance(bucket, list):
                    for r in bucket:
                        asyncio.create_task(shadow_orchestrator.audit_route_intelligence(r))
            
            # [Task: Safety Tagging] Flag routes with active Sathi protection
            if constraints.women_safety_priority:
                for bucket in bucketed_results.values():
                    if isinstance(bucket, list):
                        for r in bucket:
                            r.metadata["sathi_protected"] = any(
                                constraints.station_safety_scores.get(seg.departure_stop_id, 0.5) > 0.5 or 
                                constraints.station_safety_scores.get(seg.arrival_stop_id, 0.5) > 0.5
                                for seg in r.segments
                            )

            # Return bucketed structure for VYA-compatible frontends, 
            # while maintaining a flattened list for legacy compatibility if requested.
            if request.metadata.get("vya_enabled", True):
                return {
                    "metadata": {
                        "engine_yield": pre_safety_count,
                        "visible_yield": sum(len(b) if isinstance(b, list) else 0 for b in bucketed_results.values()),
                        "search_iteration": request.metadata.get("search_iteration", 0)
                    },
                    "buckets": bucketed_results,
                    "redistribution_options": request.metadata.get("redistribution_options", [])
                }

            return final_routes[:min(limit * 5, 500)]

        except Exception as e:
            logger.error(f"Orchestrator search failed: {e}")
            # [Phase 1 Fix] Stale-cache fallback: serve cached results during engine failures
            try:
                stale_result = await multi_layer_cache.get(cache_key)
                if stale_result:
                    logger.warning(f"🔄 [FALLBACK] Serving {len(stale_result)} stale cached routes after engine failure.")
                    for r in stale_result:
                        r.metadata["stale_cache"] = True
                        r.metadata["fallback_reason"] = str(e)[:100]
                    return stale_result
            except Exception as cache_err:
                logger.error(f"Stale-cache fallback also failed: {cache_err}")
            return []
        finally:
            if _owned_session and db is not None:
                try:
                    db.close()
                except Exception:
                    pass

    def _bucket_and_rank_results(self, routes: List[Route], limit: int = 10) -> Dict[str, List[Route]]:
        """VYA: Buckets routes by transfer count and applies diversity ranking."""
        buckets = {"direct": [], "one_transfer": [], "two_transfer": [], "three_transfer": [], "advanced": []}
        
        for r in routes:
            t_count = len(r.segments) - 1
            if t_count == 0: buckets["direct"].append(r)
            elif t_count == 1: buckets["one_transfer"].append(r)
            elif t_count == 2: buckets["two_transfer"].append(r)
            elif t_count == 3: buckets["three_transfer"].append(r)
            else: buckets["advanced"].append(r)
            
        logger.info(f"🪣 [ORCHESTRATOR:BUCKET] D:{len(buckets['direct'])} 1T:{len(buckets['one_transfer'])} 2T:{len(buckets['two_transfer'])}")
        
        # Diversity Ranking: Fulfilling the 15/10/10/10 yield requirement
        return {
            "direct": sorted(buckets["direct"], key=lambda x: x.total_duration), # All direct
            "one_transfer": self._rank_by_diversity(buckets["one_transfer"], 15),
            "two_transfer": self._rank_by_diversity(buckets["two_transfer"], 10),
            "three_transfer": self._rank_by_diversity(buckets["three_transfer"], 10),
            "advanced": self._rank_by_diversity(buckets["advanced"], 10)
        }

    def _rank_by_diversity(self, routes: List[Route], k: int) -> List[Route]:
        """Ensures the top K routes in a bucket cover Fastest, Cheapest, and Safest."""
        if not routes: return []
        if len(routes) <= k: return routes
        
        selected: Dict[str, Route] = {}
        # 1. Mandatory Persona Best
        selected["fastest"] = min(routes, key=lambda x: x.total_duration)
        selected["cheapest"] = min(routes, key=lambda x: x.total_cost)
        selected["safest"] = max(routes, key=lambda x: getattr(x, 'safety_score', 0.5))
        selected["balanced"] = max(routes, key=lambda x: x.score or 0.5)
        
        # 2. Fill remaining with highest score
        unique_results = list({r.journey_id: r for r in selected.values()}.values())
        remaining = [r for r in routes if r.journey_id not in [ur.journey_id for ur in unique_results]]
        remaining.sort(key=lambda x: -(x.score or 0))
        
        return (unique_results + remaining)[:k]
