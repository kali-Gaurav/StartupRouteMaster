import asyncio
import logging
import orjson as json
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
import time
import hashlib
import zlib
from datetime import datetime, timedelta

from core.route_engine.engine import RailwayRouteEngine
from core.route_engine import route_engine
from database.config import Config
from services.multi_layer_cache import multi_layer_cache, RouteQuery
from utils.station_utils import resolve_stations
from utils import metrics

logger = logging.getLogger(__name__)

class SearchService:
    def __init__(self, db: Session, route_engine_instance: Optional[RailwayRouteEngine] = None):
        self.db = db 
        from database.session import SessionTransit
        self.transit_db = SessionTransit()
        self.route_engine = route_engine_instance or route_engine

    async def _log_engine_metrics(self, engine_name: str, duration_ms: float, success: bool):
        try:
            await multi_layer_cache.initialize()
            if multi_layer_cache.redis:
                today = datetime.utcnow().date().isoformat()
                await multi_layer_cache.redis.hincrby(f"metrics:engine_usage:{today}", engine_name, 1)
                await multi_layer_cache.redis.hincrby(f"metrics:engine_time:{today}", engine_name, int(duration_ms))
                if success:
                    await multi_layer_cache.redis.hincrby(f"metrics:engine_success:{today}", engine_name, 1)
        except: pass

    async def search_routes(self, source: str, destination: str, travel_date: str, budget_category: Optional[str] = None, limit: int = 15) -> Dict[Any, Any]:
        overall_start = time.time()
        
        # 1. Normalize and Prepare Fingerprint Cache
        source = source.upper().strip()
        destination = destination.upper().strip()
        
        await multi_layer_cache.initialize()
        query_hash = hashlib.md5(f"{source}:{destination}:{travel_date}:{budget_category}".encode()).hexdigest()
        cache_key = f"search:unified:{query_hash}"
        logger.info(f"Checking Cache Key: {cache_key}")
        
        # Task 23.2: Aggressive Cache hit
        if multi_layer_cache.redis:
            try:
                cached_res = await multi_layer_cache.redis.get(cache_key)
                if cached_res:
                    logger.info(f"🚀 [ULTRA-FAST] Cache hit for key: {cache_key}")
                    decompressed = zlib.decompress(cached_res)
                    result = json.loads(decompressed)
                    result["latency_ms"] = (time.time() - overall_start) * 1000
                    result["source"] = "redis_fingerprint"
                    return result
                else:
                    logger.info(f"Cache miss for key: {cache_key}")
            except Exception as e:
                logger.error(f"Cache decompression error: {e}")

        # Suggestion #25: Failed Resolution Cache
        fail_key = f"fail:{source}:{destination}:{travel_date}"
        if multi_layer_cache.redis and await multi_layer_cache.redis.exists(fail_key):
            return {
                "source": source, "destination": destination, "journeys": [], 
                "status": "cached_no_route", "latency_ms": (time.time() - overall_start) * 1000
            }

        # 2. Resolve stations via Transit DB
        source_stop, dest_stop = resolve_stations(self.transit_db, source, destination)
        if not source_stop or not dest_stop:
            return {"source": source, "destination": destination, "journeys": [], "error": "Station not found"}

        try:
            dt = datetime.strptime(travel_date, "%Y-%m-%d")
        except:
            dt = datetime.now()

        from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
        from core.route_engine.constraints_engine import ConstraintsEngine
        
        orchestrator = UnifiedRoutingOrchestrator(self.route_engine)
        c = ConstraintsEngine.initialize_constraints(
            persona_str=budget_category or "comfort",
            travel_date=dt.date()
        )

        # 3. GATHER ALL POSSIBLE ROUTES (Tiers 0, 1, 2, 3)
        days_searched = 0
        all_unique_routes = {} 
        
        while len(all_unique_routes) < 100 and days_searched < 3:
            current_dt = dt + timedelta(days=days_searched)
            search_res = await orchestrator.search_all_tiers(
                source_code=source,
                destination_code=destination,
                departure_date=current_dt,
                constraints=c,
                limit=100,
                db=self.transit_db
            )
            
            for r in search_res:
                jid = r.journey_id
                if jid not in all_unique_routes:
                    r.metadata["day_offset"] = days_searched
                    all_unique_routes[jid] = r
                elif r.score < all_unique_routes[jid].score:
                    all_unique_routes[jid] = r
            
            if len(all_unique_routes) >= 50: break 
            days_searched += 1

        verified_routes = list(all_unique_routes.values())

        # 4. CATEGORIZATION
        categories = {
            "top_3_confirmed": [],
            "direct": [],
            "one_transfer": [],
            "two_plus_transfer": [],
            "fastest": [],
            "most_optimal": []
        }

        hydrated_journeys = []
        for r in verified_routes:
            rd = r.to_dict()
            # Inject 2-tier pricing
            base_fare = rd.get("total_fare", 0)
            rd["pricing"] = {
                "view_only_fee": 49.0,
                "agent_booking_fee": 10.0,
                "ticket_fare": base_fare,
                "total_agent_checkout": base_fare + 49.0 + 10.0
            }
            hydrated_journeys.append(rd)
            
            num_segments = len(r.segments)
            if num_segments == 1: categories["direct"].append(rd)
            elif num_segments == 2: categories["one_transfer"].append(rd)
            else: categories["two_plus_transfer"].append(rd)

            # Task 21: Mocked confirm logic for categorization
            if r.availability_probability > 0.8:
                categories["top_3_confirmed"].append(rd)

        # Ranking
        categories["fastest"] = sorted(hydrated_journeys, key=lambda x: x.get("total_duration", 9999))[:5]
        categories["most_optimal"] = sorted(hydrated_journeys, key=lambda x: x.get("score", 9999))[:5]
        categories["top_3_confirmed"] = sorted(categories["top_3_confirmed"], key=lambda x: x.get("total_duration", 9999))[:3]

        ids_blob = "".join([str(j.get("journey_id", "")) for j in hydrated_journeys])
        fingerprint = hashlib.sha256(ids_blob.encode()).hexdigest()[:12]

        final_response = {
            "source": source, 
            "destination": destination, 
            "journeys": hydrated_journeys,
            "grouped_journeys": categories,
            "fingerprint": fingerprint, 
            "days_expanded": days_searched,
            "latency_ms": (time.time() - overall_start) * 1000
        }

        # 5. Task 23.2: Save to Fingerprint Cache with compression
        if multi_layer_cache.redis and hydrated_journeys:
            try:
                # 1-hour TTL for search results
                import zlib
                # json.dumps (orjson) already returns bytes
                compressed = zlib.compress(json.dumps(final_response, default=str))
                logger.info(f"Saving to Cache Key: {cache_key} (Size: {len(compressed)} bytes)")
                await multi_layer_cache.redis.setex(cache_key, 3600, compressed)
                logger.info("✅ Cache save successful.")
            except Exception as e: 
                logger.error(f"❌ Cache save failed: {e}")

        return final_response

    async def search_routes_stream(self, source: str, destination: str, travel_date: str, budget_category: Optional[str] = None):
        """Streaming search results for real-time UI updates (SSE)."""
        source = source.upper().strip()
        destination = destination.upper().strip()
        try:
            dt = datetime.strptime(travel_date, "%Y-%m-%d")
        except:
            dt = datetime.now()

        from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
        from core.route_engine.constraints_engine import ConstraintsEngine
        
        orchestrator = UnifiedRoutingOrchestrator(self.route_engine)
        c = ConstraintsEngine.initialize_constraints(persona_str=budget_category or "comfort", travel_date=dt.date())

        yield {"status": "searching", "engine": "Turbo", "message": "Checking direct routes..."}
        
        turbo_direct = orchestrator.turbo_router.find_routes(source, destination, dt, limit=5)
        if turbo_direct:
            hydrated = orchestrator._standardize_turbo_results(turbo_direct, source, destination)
            yield {"status": "results", "engine": "Turbo", "journeys": hydrated}

        yield {"status": "searching", "engine": "FastRouter", "message": "Exploring 1-transfer connections..."}
        
        source_stop, dest_stop = resolve_stations(self.transit_db, source, destination)
        if source_stop and dest_stop:
            graph = await self.route_engine._get_current_graph(dt)
            orchestrator.fast_router.graph = graph
            fast_routes = orchestrator.fast_router._find_1_transfer(source_stop.id, dest_stop.id, c, dt, dt + timedelta(hours=24))
            if fast_routes:
                await orchestrator._hydrate_fares_and_score(fast_routes, c, graph, self.transit_db)
                yield {"status": "results", "engine": "FastRouter", "journeys": [r.to_dict() for r in fast_routes[:10]]}

        yield {"status": "complete", "message": "Search finished."}

    def __del__(self):
        if hasattr(self, 'transit_db'):
            try: self.transit_db.close()
            except: pass
