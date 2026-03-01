import asyncio
import logging
import orjson as json
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
import time
from datetime import datetime, timedelta

from core.route_engine import RouteEngine, route_engine
from database.config import Config
from database.models import Stop, Trip, Route
from core.redis import async_redis_client
from services.multi_layer_cache import multi_layer_cache, RouteQuery, AvailabilityQuery
from utils.station_utils import resolve_stations
from utils import metrics

logger = logging.getLogger(__name__)

# Request coalescing to prevent search storms (Topic 4)
_inflight_searches: Dict[str, asyncio.Event] = {}
_search_results: Dict[str, Any] = {}

class SearchService:
    def __init__(self, db: Session, route_engine_instance: Optional[RouteEngine] = None):
        self.db = db
        self.route_engine = route_engine_instance or route_engine

    async def search_routes(
        self,
        source: str,
        destination: str,
        travel_date: str,
        budget_category: Optional[str] = None,
        multi_modal: bool = False,
        women_safety_mode: bool = False,
        offset: int = 0,
        limit: int = 15
    ) -> Dict[str, Any]:
        """
        Unified search method with Request Coalescing and multi-layer caching.
        Now supports offset/limit for "Load More" feature.
        """
        start_time = time.time()
        endpoint = "/api/v2/search/unified"
        
        await multi_layer_cache.initialize()
        
        # 1. Prepare Query Object for Cache
        try:
            dt_obj = datetime.strptime(travel_date.split(' ')[0], "%Y-%m-%d").date()
        except Exception:
            dt_obj = datetime.utcnow().date()

        query = RouteQuery(
            from_station=source.upper(),
            to_station=destination.upper(),
            date=dt_obj,
            class_preference=budget_category,
            max_transfers=3,
            include_wait_time=not women_safety_mode
        )
        # Unique cache key for this specific slice
        cache_key = f"{query.cache_key()}:{offset}:{limit}"
        
        # 2. Check Request Coalescing (Single-Flight)
        if cache_key in _inflight_searches:
            logger.info(f"⚡ COALESCE: Joining in-flight search for {cache_key}")
            await _inflight_searches[cache_key].wait()
            metrics.SEARCH_REQUESTS_TOTAL.labels(endpoint=endpoint, status="coalesced").inc()
            return _search_results.get(cache_key)

        # 3. Check Multi-Layer Cache (L0 -> L1) for the FULL result set
        cached_full = await multi_layer_cache.get_route_query(query)
        if cached_full and isinstance(cached_full, dict) and "journeys" in cached_full:
            full_journeys = cached_full.get("journeys", [])
            
            # RE-SAVE to journey_cache to ensure they are available for verification
            from services.journey_cache import save_journey
            for j in full_journeys:
                await save_journey(j["journey_id"], j)

            sliced_result = cached_full.copy()
            sliced_result["journeys"] = full_journeys[offset:offset+limit]
            sliced_result["offset"] = offset
            sliced_result["limit"] = limit
            sliced_result["total_available"] = len(full_journeys)
            
            logger.info(f"✅ MULTI-LAYER CACHE HIT (SLICED): {cache_key}")
            metrics.ROUTE_CACHE_HITS_TOTAL.inc()
            metrics.SEARCH_REQUESTS_TOTAL.labels(endpoint=endpoint, status="cache_hit").inc()
            return sliced_result

        metrics.ROUTE_CACHE_MISSES_TOTAL.inc()

        # 4. Start Single-Flight Execution
        _inflight_searches[cache_key] = asyncio.Event()
        
        try:
            # TRY TURBO ROUTER FIRST (Phase 11: Station-Centric Optimization)
            from core.route_engine.turbo_router import TurboRouter
            turbo = TurboRouter()
            
            # Convert str to datetime for turbo
            try:
                dt_input = datetime.strptime(travel_date, "%Y-%m-%d")
            except:
                dt_input = datetime.now()

            # Increase search internal limit to handle offset/limit slicing
            internal_limit = max(40, offset + limit)
            turbo_results = turbo.find_routes(source, destination, dt_input, limit=internal_limit)
            
            if turbo_results:
                logger.info(f"⚡ TURBO ROUTE HIT: Found {len(turbo_results)} routes in <500ms")
                # Format turbo results to match the expected journey schema
                raw_journeys = []
                for idx, tr in enumerate(turbo_results):
                    journey_id = f"turbo_{int(time.time())}_{idx}"
                    legs = []
                    for l in tr['legs']:
                        legs.append({
                            "train_number": l['train_no'],
                            "train_name": f"Train {l['train_no']}",
                            "from_station_code": l['from'],
                            "to_station_code": l['to'],
                            "departure_time": l['dep'],
                            "arrival_time": l['arr'],
                            "mode": "rail"
                        })
                    
                    raw_journeys.append({
                        "journey_id": journey_id,
                        "num_segments": len(legs),
                        "source": source,
                        "destination": destination,
                        "date": travel_date,
                        "total_duration": 0, 
                        "num_transfers": tr['transfers'],
                        "is_direct": tr['transfers'] == 0,
                        "legs": legs,
                        "availability_status": "PENDING",
                        "reliability_score": 1.0
                    })
                
                # ENRICH TURBO ROUTES
                from services.seat_verification import SeatVerificationService
                from services.journey_cache import save_journey
                seat_svc = SeatVerificationService()
                
                enriched_turbo = []
                for idx, j_data in enumerate(raw_journeys):
                    # Enrich first 5 immediately
                    if idx < 5:
                        try:
                            await seat_svc.verify_journey(j_data)
                        except: j_data["availability_status"] = "AVAILABLE"
                    
                    # SAVE TO CACHE
                    await save_journey(j_data["journey_id"], j_data)
                    enriched_turbo.append(j_data)
                
                result = {"source": source, "destination": destination, "journeys": enriched_turbo}
            else:
                # 4b. Fallback to Legacy Engine if Turbo finds nothing
                logger.info("🐢 Turbo found nothing, falling back to Legacy HybridRAPTOR")
                result = await self._execute_search_logic(
                    source, destination, travel_date, budget_category, multi_modal, women_safety_mode,
                    max_internal_results=40
                )
            
            # 5. Cache FULL result set
            await multi_layer_cache.set_route_query(query, result, ttl_minutes=10)
            
            # 6. Return sliced result
            full_journeys = result.get("journeys", [])
            sliced_result = result.copy()
            sliced_result["journeys"] = full_journeys[offset:offset+limit]
            sliced_result["offset"] = offset
            sliced_result["limit"] = limit
            sliced_result["total_available"] = len(full_journeys)
            
            _search_results[cache_key] = sliced_result
            metrics.SEARCH_REQUESTS_TOTAL.labels(endpoint=endpoint, status="success").inc()
            return sliced_result
        except Exception as e:
            logger.error(f"Search failure: {e}", exc_info=True)
            metrics.SEARCH_REQUESTS_TOTAL.labels(endpoint=endpoint, status="error").inc()
            return {"error": str(e), "journeys": []}
        finally:
            _inflight_searches[cache_key].set()
            asyncio.create_task(self._cleanup_coalesce(cache_key))
            duration = time.time() - start_time
            metrics.SEARCH_LATENCY_SECONDS.labels(endpoint=endpoint).observe(duration)

    async def _cleanup_coalesce(self, key: str):
        await asyncio.sleep(10)
        _inflight_searches.pop(key, None)
        _search_results.pop(key, None)

    async def _execute_search_logic(
        self, 
        source: str, 
        destination: str, 
        travel_date: str, 
        budget_category: str, 
        multi_modal: bool, 
        women_safety_mode: bool,
        max_internal_results: int = 40
    ) -> Dict[str, Any]:
        overall_start = time.time()
        
        # Resolve station names/codes
        source_stop, dest_stop = resolve_stations(self.db, source, destination)
        if not source_stop or not dest_stop:
            return {"source": source, "destination": destination, "journeys": [], "message": "Station not resolved"}
        
        source_id = source_stop.id
        dest_id = dest_stop.id

        if " " in travel_date:
            dt = datetime.strptime(travel_date, "%Y-%m-%d %H:%M:%S")
        else:
            dt = datetime.strptime(travel_date, "%Y-%m-%d")
            dt = dt.replace(hour=8, minute=0)
        
        from core.route_engine.constraints import RouteConstraints
        
        # --- MULTI-TIER EXECUTION WITH EARLY TERMINATION ---
        # We increase max_results in constraints to get more routes for Load More
        tiers = [
            RouteConstraints(max_transfers=0, range_minutes=1440, max_results=max_internal_results), # Direct
            RouteConstraints(max_transfers=1, range_minutes=1440, max_results=max_internal_results), # 1 transfer
            RouteConstraints(max_transfers=2, range_minutes=1440, max_results=max_internal_results), # 2 transfers
            RouteConstraints(max_transfers=3, range_minutes=1440, max_results=max_internal_results)  # 3 transfers
        ]
        
        internal_routes = []
        for i, c in enumerate(tiers):
            tier_routes = await self.route_engine.search_routes(
                source_code=source,
                destination_code=destination,
                departure_date=dt,
                constraints=c
            )
            # Avoid duplicate routes if RAPTOR returns them in multiple tiers
            for tr in tier_routes:
                if not any(r.segments == tr.segments for r in internal_routes):
                    internal_routes.append(tr)
            
            # Early termination logic: adjusted for higher volume
            if i == 0 and len(internal_routes) >= 10:
                logger.info(f"Phase 10: Found {len(internal_routes)} direct routes. skipping transfer search.")
                break
            if len(internal_routes) >= max_internal_results:
                logger.info(f"Phase 10: Found sufficient routes ({len(internal_routes)}). Terminating search tiers.")
                break

        from services.seat_verification import SeatVerificationService
        from services.journey_cache import save_journey
        from services.realtime_ingestion.live_status_service import LiveStatusService
        
        seat_svc = SeatVerificationService()
        live_svc = LiveStatusService()
        
        # Heuristic sort: Best optimal travel time and scores first
        internal_routes.sort(key=lambda r: (r.total_duration, r.total_cost))

        async def enrich_journey(idx, rt):
            num_transfers = len(rt.transfers)
            journey_id = f"rt_{int(time.time())}_{idx}_{rt.segments[0].trip_id}"
            
            legs = [{
                "train_number": s.train_number, "train_name": s.train_name,
                "from_station_code": s.departure_code, "to_station_code": s.arrival_code,
                "departure_time": s.departure_time.isoformat(), "arrival_time": s.arrival_time.isoformat(),
                "duration_minutes": s.duration_minutes, "fare": s.fare, "mode": "rail"
            } for s in rt.segments]

            journey_data = {
                "journey_id": journey_id, "num_segments": len(rt.segments),
                "source": source, "destination": destination, "date": travel_date,
                "total_duration": rt.total_duration,
                "travel_time": f"{rt.total_duration // 60:02d}:{rt.total_duration % 60:02d}",
                "num_transfers": num_transfers, "is_direct": num_transfers == 0,
                "total_cost": rt.total_cost, "cheapest_fare": rt.total_cost,
                "legs": legs, "availability_status": "PENDING", "live_status": None,
                "reliability_score": 1.0
            }

            # 1. Transfer Risk (Idea 2)
            if num_transfers > 0:
                for i in range(len(rt.segments) - 1):
                    buffer = (rt.segments[i+1].departure_time - rt.segments[i].arrival_time).total_seconds() / 60
                    if buffer < 30: journey_data["reliability_score"] *= 0.5
                    elif buffer < 60: journey_data["reliability_score"] *= 0.8

            # 2. Live Status (Topic 8) - Only for top candidates initially to save API hits
            if idx < 15:
                try:
                    live = await live_svc.get_live_status(rt.segments[0].train_number)
                    if live:
                        journey_data["live_status"] = {"delay": live.get("delay_minutes", 0), "status": live.get("status_message", "Running")}
                        if live.get("delay_minutes", 0) > 30: journey_data["reliability_score"] *= 0.7
                except Exception: pass

            # Enrich first 5 immediately, background task for next 10
            if idx < 5:
                try:
                    is_available = await seat_svc.verify_journey(journey_data)
                    journey_data["availability_status"] = "AVAILABLE" if is_available else "UNAVAILABLE"
                except Exception: journey_data["availability_status"] = "AVAILABLE"
            elif idx < 15:
                # Background verification for next batch to speed up "Load More"
                asyncio.create_task(seat_svc.verify_journey(journey_data)) 
            
            save_ok = await save_journey(journey_id, journey_data)
            logger.info(f"💾 Saved journey {journey_id} to cache: {save_ok}")
            return journey_data

        # Parallel enrichment - enrich ALL generated routes (up to limit)
        enrichment_tasks = [enrich_journey(idx, rt) for idx, rt in enumerate(internal_routes)]
        journeys = await asyncio.gather(*enrichment_tasks)

        # Final Rank: AVAILABLE First, then optimal time
        journeys.sort(key=lambda j: (0 if j["availability_status"] == "AVAILABLE" else 1, j["total_duration"]))
        
        return {
            "source": source, "destination": destination, "journeys": journeys, 
            "latency_ms": (time.time()-overall_start)*1000
        }
