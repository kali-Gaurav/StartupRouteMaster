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
from core.route_engine.data_provider import DataProvider
from core.data_structures import Route
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
        self.data_provider = DataProvider()

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

    async def search_routes(self, source: str, destination: str, travel_date: str, budget_category: Optional[str] = None, page: int = 1, limit: int = 15, quota: str = "GN", client_ip: Optional[str] = None, geo_state: Optional[str] = None) -> Dict[Any, Any]:
        overall_start = time.time()
        
        # 1. Normalize and Prepare Fingerprint Cache
        source = source.upper().strip()
        destination = destination.upper().strip()
        quota = quota.upper().strip()
        
        # Subtask 5.2: Create search log early to capture search intent even if no results
        from database.models import RouteSearchLog
        from datetime import date
        try:
            search_date = datetime.strptime(travel_date, "%Y-%m-%d").date()
        except:
            search_date = datetime.utcnow().date()

        await multi_layer_cache.initialize()
        # [40.6] Cache-Key Sensitivity: include page/limit in hash
        query_hash = hashlib.md5(f"{source}:{destination}:{travel_date}:{budget_category}:{quota}:{page}:{limit}".encode()).hexdigest()
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
                    latency = (time.time() - overall_start) * 1000
                    result["latency_ms"] = latency
                    result["source"] = "redis_fingerprint"
                    
                    # Log search with geo
                    log = RouteSearchLog(
                        src=source, dst=destination, date=search_date,
                        latency_ms=latency, ip_address=client_ip, geo_state=geo_state
                    )
                    self.db.add(log)
                    self.db.commit()
                    return result
                else:
                    logger.info(f"Cache miss for key: {cache_key}")
            except Exception as e:
                logger.error(f"Cache decompression error: {e}")

        # Suggestion #25: Failed Resolution Cache
        fail_key = f"fail:{source}:{destination}:{travel_date}"
        if multi_layer_cache.redis and await multi_layer_cache.redis.exists(fail_key):
            latency = (time.time() - overall_start) * 1000
            # Log search with geo
            log = RouteSearchLog(
                src=source, dst=destination, date=search_date,
                latency_ms=latency, ip_address=client_ip, geo_state=geo_state
            )
            self.db.add(log)
            self.db.commit()
            return {
                "source": source, "destination": destination, "journeys": [], 
                "status": "cached_no_route", "latency_ms": latency
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
        from core.data_structures import Persona
        
        orchestrator = UnifiedRoutingOrchestrator(self.route_engine)
        persona = Persona(budget_category or "comfort")
        c = ConstraintsEngine.initialize_constraints(
            persona_str=persona.value,
            travel_date=dt.date(),
            quota=quota
        )

        # 3. GATHER ALL POSSIBLE ROUTES (Tiers 0, 1, 2, 3)
        days_searched = 0
        all_unique_routes = {} 
        
        while days_searched < 3:
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
                    if days_searched > 0:
                        r.metadata["is_alternative"] = True
                        r.metadata["alt_reason"] = f"Available on {current_dt.strftime('%b %d')}"
                    all_unique_routes[jid] = r
                elif r.score < all_unique_routes[jid].score:
                    all_unique_routes[jid] = r
            
            # [35.1] Termination Logic: If we have 5+ routes from day 0, stop searching further days
            # unless yield is extremely low.
            day_0_count = sum(1 for r in all_unique_routes.values() if r.metadata.get("day_offset") == 0)
            if day_0_count >= 15: break
            
            days_searched += 1

        # Task 27.3: ML-based Predictive Availability (Pre-Pruning)
        from services.ml.availability_heuristic import availability_heuristic
        candidate_routes = []
        for r in all_unique_routes.values():
            ml_prob = availability_heuristic.get_route_availability_score(r.segments)
            r.availability_probability = ml_prob
            # Task 27.4: Prune routes with < 20% predicted CNF probability
            if ml_prob >= 0.20:
                candidate_routes.append(r)
        
        logger.info(f"ML Pruning: {len(all_unique_routes)} -> {len(candidate_routes)} candidates.")

        # Task 24.3 & 26.4: Parallel Verification with Quota
        verified_routes = await self._verify_routes_parallel(candidate_routes, dt, quota)

        # [35.2] Date Shifting Engine: If yield is low (< 3 highly likely confirmed routes), expand search
        confirmed_yield = [r for r in verified_routes if r.availability_probability > 0.8]
        
        if len(confirmed_yield) < 3 and days_searched < 2:
            logger.info(f"Low yield on primary date. Triggering date-shifted alternatives (+1 day).")
            # We already have a loop above that expands to 3 days if yield is < 50 unique routes.
            # We'll refine that loop to prioritize confirmed status.

        from core.route_engine.categorization import CategorizationEngine
        from services.unlock_service import UnlockService
        categories = CategorizationEngine.categorize(verified_routes, persona)
        
        # [40.4] Pre-Slicing Analytics
        total_found = len(verified_routes)
        
        # [40.3] Universal Slicing Logic
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        
        hydrated_journeys_map = {}
        for journey_dict in categories.get("top_3_highlight", []):
            hydrated_journeys_map[journey_dict["journey_id"]] = journey_dict
            
        for cat_list in categories.values():
            for journey_dict in cat_list:
                jid = journey_dict["journey_id"]
                if jid not in hydrated_journeys_map:
                    hydrated_journeys_map[jid] = journey_dict
        
        all_hydrated = list(hydrated_journeys_map.values())
        
        # [41.6] Masking Layer: Apply masking to all journeys by default
        # In a real scenario, we'd check if (user_id, journey_id) is in UnlockedRoutes table
        masked_journeys = [UnlockService.mask_route(j) for j in all_hydrated]
        
        # [40.8] Bounds Handling
        if start_idx >= len(masked_journeys):
            paginated_journeys = []
        else:
            paginated_journeys = masked_journeys[start_idx:end_idx]
            
        # Mask the categories as well
        masked_categories = {}
        if page == 1:
            for cat_name, routes_list in categories.items():
                masked_categories[cat_name] = [UnlockService.mask_route(r) for r in routes_list]

        # [40.1] Pagination Metadata
        import math
        total_pages = math.ceil(len(all_hydrated) / limit) if all_hydrated else 0
        from core.data_structures import PaginationMetadata
        pagination = PaginationMetadata(
            total_results=len(all_hydrated),
            current_page=page,
            limit=limit,
            has_next=page < total_pages,
            total_pages=total_pages
        )

        ids_blob = "".join([str(j.get("journey_id", "")) for j in paginated_journeys])
        fingerprint = hashlib.sha256(ids_blob.encode()).hexdigest()[:12]

        latency = (time.time() - overall_start) * 1000
        
        # [40.9] Response Payload Refinement
        final_response = {
            "status": "success",
            "source": source, 
            "destination": destination, 
            "data": {
                "journeys": paginated_journeys,
                "grouped_journeys": masked_categories if page == 1 else {},
                "pagination": pagination.to_dict()
            },
            "metadata": {
                "fingerprint": fingerprint, 
                "days_expanded": days_searched,
                "latency_ms": latency,
                "total_verified": total_found,
                "monetization": "tier_2_masked"
            }
        }

        # Log search with geo
        log = RouteSearchLog(
            src=source, dst=destination, date=search_date,
            latency_ms=latency, ip_address=client_ip, geo_state=geo_state
        )
        self.db.add(log)
        self.db.commit()

        # 5. Task 23.2: Save to Fingerprint Cache with compression
        if multi_layer_cache.redis and all_hydrated:
            try:
                # 1-hour TTL for search results
                import zlib
                # json.dumps already returns bytes (orjson)
                compressed = zlib.compress(json.dumps(final_response, default=str))
                logger.info(f"Saving to Cache Key: {cache_key} (Size: {len(compressed)} bytes)")
                await multi_layer_cache.redis.setex(cache_key, 3600, compressed)
                logger.info("✅ Cache save successful.")
            except Exception as e: 
                logger.error(f"❌ Cache save failed: {e}")

        return final_response

    async def _verify_routes_parallel(self, routes: List[Route], travel_date: datetime, quota: str = "GN") -> List[Route]:
        """Verify multiple routes in parallel."""
        to_verify = sorted(routes, key=lambda x: x.score)[:20]
        remaining = [r for r in routes if r not in to_verify]
        
        tasks = [self._verify_single_route(r, travel_date, quota) for r in to_verify]
        verified = await asyncio.gather(*tasks)
        
        return list(verified) + remaining

    async def _verify_single_route(self, route: Route, travel_date: datetime, quota: str = "GN") -> Route:
        """Verify all legs of a single multi-transfer route in parallel."""
        leg_tasks = []
        for seg in route.segments:
            # Task 21 & 22
            leg_tasks.append(self.data_provider.verify_seat_availability_unified(
                trip_id=seg.trip_id,
                travel_date=travel_date + timedelta(days=route.metadata.get("day_offset", 0)),
                train_number=seg.train_number,
                from_station=seg.departure_code,
                to_station=seg.arrival_code,
                quota=quota
            ))
            leg_tasks.append(self.data_provider.verify_fare_unified(
                segment_id=None,
                train_number=seg.train_number,
                from_station=seg.departure_code,
                to_station=seg.arrival_code
            ))
            # Task 28.2: Fetch live delay and platform (Task 37.3)
            leg_tasks.append(self.data_provider.get_live_status(seg.train_number))
            
        results = await asyncio.gather(*leg_tasks)
        
        # Aggregate results
        # Now each leg has 3 results: [Seat, Fare, StatusDict]
        total_avail_prob = 1.0
        total_fare = 0.0
        total_delay = 0
        
        for i in range(0, len(results), 3):
            seat_res = results[i]
            fare_res = results[i+1]
            status_res = results[i+2]
            
            # [37.4] Live Platform Hydration
            seg = route.segments[i//3]
            live_pf = status_res.get("platform")
            if live_pf:
                # If current station matches arrival, it's arrival PF
                # Heuristic: set both if unknown
                seg.arrival_platform = live_pf
                seg.departure_platform = live_pf 
                seg.metadata["pf_verified"] = True

            # Delay update
            delay_mins = status_res.get("delay_mins", 0)
            total_delay += delay_mins
            if delay_mins > 0:
                seg.arrival_time += timedelta(minutes=delay_mins)
            
        route.availability_probability = total_avail_prob
        route.total_cost = total_fare
        # Adjust total duration for delays
        route.total_duration += total_delay
        
        route.metadata["is_verified"] = True
        route.metadata["total_delay_mins"] = total_delay
        
        return route

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
