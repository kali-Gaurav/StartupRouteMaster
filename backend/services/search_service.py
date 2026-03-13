import asyncio
import logging
import orjson as json
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
from fastapi import Request
import time
import hashlib
import zlib
from datetime import datetime, timedelta

from core.route_engine.engine import RailwayRouteEngine
from core.route_engine import route_engine
from core.route_engine.data_provider import DataProvider
from core.data_structures import Route
from core.pricing.fare_calculator import calculate_fare
from database.config import Config
from services.multi_layer_cache import multi_layer_cache, RouteQuery
from utils.station_utils import resolve_stations
from utils import metrics
from core.metrics import jit_metrics, SurgeLevel, DegradationManager

logger = logging.getLogger(__name__)

class SearchService:
    def __init__(self, db: Session, route_engine_instance: Optional[RailwayRouteEngine] = None):
        self.db = db 
        from database.session import SessionTransit
        self.transit_db = SessionTransit()
        self.route_engine = route_engine_instance or route_engine
        self.data_provider = DataProvider()

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
        source_stop, dest_stop = resolve_stations(self.transit_db, source, destination)
        if not source_stop: reasons.append(f"Origin station '{source}' not recognized.")
        if not dest_stop: reasons.append(f"Destination station '{destination}' not recognized.")
        
        if source_stop and dest_stop:
            # Check if ANY trains run between these stations on any day
            from sqlalchemy import text
            try:
                count = self.transit_db.execute(text(
                    "SELECT COUNT(*) FROM trips t "
                    "JOIN stop_times s1 ON t.id = s1.trip_id "
                    "JOIN stop_times s2 ON t.id = s2.trip_id "
                    "WHERE s1.stop_id = :s1 AND s2.stop_id = :s2 AND s1.stop_sequence < s2.stop_sequence"
                ), {"s1": source_stop.id, "s2": dest_stop.id}).scalar()
                
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
            await multi_layer_cache.initialize()
            if multi_layer_cache.redis:
                today = datetime.utcnow().date().isoformat()
                await multi_layer_cache.redis.hincrby(f"metrics:engine_usage:{today}", engine_name, 1)
                await multi_layer_cache.redis.hincrby(f"metrics:engine_time:{today}", engine_name, int(duration_ms))
                if success:
                    await multi_layer_cache.redis.hincrby(f"metrics:engine_success:{today}", engine_name, 1)
        except: pass

    async def search_routes(self, source: str, destination: str, travel_date: str, budget_category: Optional[str] = None, page: int = 1, limit: int = 15, quota: str = "GN", client_ip: Optional[str] = None, geo_state: Optional[str] = None, session_id: Optional[str] = None, cursor: Optional[float] = None, request: Optional[Request] = None) -> Dict[Any, Any]:
        overall_start = time.time()
        
        import gc
        gc.disable() # Subtask 2.6: Prevent GC overhead during heavy routing
        
        try:
            # 1. Normalize and Prepare Fingerprint Cache
            source = source.upper().strip()
            destination = destination.upper().strip()
            quota = quota.upper().strip()
            session_id = session_id or f"sid_{hashlib.md5(f'{source}:{destination}:{travel_date}:{budget_category}'.encode()).hexdigest()[:10]}"
            
            from database.models import RouteSearchLog
            try:
                search_date = datetime.strptime(travel_date, "%Y-%m-%d").date()
            except:
                search_date = datetime.utcnow().date()

            await multi_layer_cache.initialize()
            
            # Redis Keys for Cursor-Based Pool (Subtask 1.1 & 18.2)
            pool_key = f"search:pool:{quota}:{session_id}"
            data_key = f"search:data:{quota}:{session_id}"
            seen_key = f"search:seen:{quota}:{session_id}"
            
            # [1.1] Handle Cursor/Page 2+ via existing pool
            if multi_layer_cache.redis and (page > 1 or cursor is not None):
                return await self.load_more_routes(session_id, limit, quota=quota, cursor=cursor)

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
            
            # [FIX] Handle 'all' or unexpected budget categories gracefully
            safe_budget = budget_category.lower() if budget_category else "comfort"
            if safe_budget == "all": safe_budget = "comfort"
            
            try:
                persona = Persona(safe_budget)
            except ValueError:
                logger.warning(f"Invalid persona '{safe_budget}' requested. Falling back to COMFORT.")
                persona = Persona.COMFORT

            c = ConstraintsEngine.initialize_constraints(
                persona_str=persona.value,
                travel_date=dt.date(),
                quota=quota
            )

            # 3. GATHER ALL POSSIBLE ROUTES (Tiers 0, 1, 2, 3) - [2.1] & [2.6] Parallel Expansion
            all_unique_routes = {} 
            
            # [Subtask 4.3] Surge Level 1 Protection
            from core.metrics import jit_metrics, SurgeLevel
            skip_heavy = jit_metrics.surge_level >= SurgeLevel.ELEVATED
            if skip_heavy:
                logger.warning("🚦 Surge Level 1 Active: Skipping heavy routing engines.")

            # [2.1] Phase 1: Search Target Date (mandatory)
            search_res_target = await orchestrator.search_all_tiers(
                source_code=source,
                destination_code=destination,
                departure_date=dt,
                constraints=c,
                limit=100,
                db=self.transit_db,
                skip_heavy=skip_heavy
            )
            for r in search_res_target:
                r.metadata["day_offset"] = 0
                all_unique_routes[r.journey_id] = r
                
            # [Subtask 1.5] Disconnection Check 1
            if request and await request.is_disconnected():
                logger.warning(f"🛑 Search Aborted: Client disconnected during Phase 1 for {source}->{destination}")
                return {"journeys": [], "aborted": True}

            # [2.2] Multi-Day Expansion Engine: If yield < 5, expansion is mandatory (Task 2.2)
            expansion_triggered = False
            if len(all_unique_routes) < 5:
                from core.metrics import DegradationManager
                if DegradationManager.should_skip_heavy_expansion():
                    logger.info("Graceful Degradation: Skipping multi-day expansion due to high system load.")
                else:
                    expansion_triggered = True
                    logger.info(f"Low yield ({len(all_unique_routes)}) detected for {source}->{destination}. Expanding search serially.")

                    # Day +1
                    res_plus = await orchestrator.search_all_tiers(source, destination, dt + timedelta(days=1), c, 50, self.transit_db)
                    for r in res_plus:
                        if r.journey_id not in all_unique_routes:
                            r.metadata["day_offset"] = 1
                            r.metadata["alt_reason"] = f"Alternative: Available on {(dt + timedelta(days=1)).strftime('%b %d')}"
                            all_unique_routes[r.journey_id] = r

                    # [Subtask 1.5] Disconnection Check 2
                    if request and await request.is_disconnected():
                        logger.warning(f"🛑 Search Aborted: Client disconnected during Expansion for {source}->{destination}")
                        return {"journeys": [], "aborted": True}

                    # Day -1 (Only if still low yield)
                    if len(all_unique_routes) < 5:
                        # Don't suggest past dates if searching for today
                        if (dt - timedelta(days=1)).date() >= datetime.utcnow().date():
                            res_minus = await orchestrator.search_all_tiers(source, destination, dt - timedelta(days=1), c, 50, self.transit_db)
                            for r in res_minus:
                                if r.journey_id not in all_unique_routes:
                                    r.metadata["day_offset"] = -1
                                    r.metadata["alt_reason"] = f"Alternative: Available on {(dt - timedelta(days=1)).strftime('%b %d')}"
                                    all_unique_routes[r.journey_id] = r
            
            # [Subtask 1.5] Disconnection Check 3
            if request and await request.is_disconnected():
                return {"journeys": [], "aborted": True}

            # [6.2] Hub-Only Routing Fallback (Zero Yield)
            if len(all_unique_routes) == 0:
                logger.info(f"Zero yield for {source}->{destination}. Triggering Hub Fallback [6.4].")
                # ... (Hub Fallback Logic) ...
                from core.route_engine.hubs import get_hubs_near
                
                # Find closest hubs to source and destination
                src_hubs = get_hubs_near(source_stop.latitude, source_stop.longitude, limit=2)
                dst_hubs = get_hubs_near(dest_stop.latitude, dest_stop.longitude, limit=2)
                
                hub_tasks = []
                # Combine unique hubs
                candidate_hubs = list(set(src_hubs + dst_hubs))
                
                for hub_code in candidate_hubs:
                    # [6.4] Forced Join via Hub
                    hub_tasks.append(orchestrator.search_all_tiers(source, hub_code, dt, c, 20, self.transit_db))
                    hub_tasks.append(orchestrator.search_all_tiers(hub_code, destination, dt, c, 20, self.transit_db))
                
                hub_raw_results = await asyncio.gather(*hub_tasks)
                
                # Simple Join Heuristic: For each hub, join leg1 and leg2
                for i in range(0, len(hub_raw_results), 2):
                    leg1_list = hub_raw_results[i]
                    leg2_list = hub_raw_results[i+1]
                    hub_code = candidate_hubs[i//2]
                    
                    for l1 in leg1_list:
                        for l2 in leg2_list:
                            # [6.6] Time-Sensitive Join (1 hour buffer)
                            if l2.segments[0].departure_time > (l1.segments[-1].arrival_time + timedelta(hours=1)):
                                # Create joined route
                                merged = Route()
                                for s in l1.segments: merged.add_segment(s)
                                for s in l2.segments: merged.add_segment(s)
                                for t in l1.transfers: merged.add_transfer(t)
                                for t in l2.transfers: merged.add_transfer(t)
                                # Add hub transfer
                                from core.data_structures import TransferConnection
                                hub_tc = TransferConnection(
                                    station_id=0, # hub station id placeholder
                                    station_name=hub_code,
                                    arrival_time=l1.segments[-1].arrival_time,
                                    departure_time=l2.segments[0].departure_time,
                                    duration_minutes=int((l2.segments[0].departure_time - l1.segments[-1].arrival_time).total_seconds() / 60)
                                )
                                merged.add_transfer(hub_tc)
                                merged.metadata["engine"] = "hub_fallback"
                                merged.metadata["is_discovery"] = True # [6.7]
                                
                                all_unique_routes[merged.journey_id] = merged
                                if len(all_unique_routes) >= 10: break
                        if len(all_unique_routes) >= 10: break

            # [20.4] Intelligent Explainer for persistent Zero-Yield
            if len(all_unique_routes) == 0:
                return await self.explain_zero_results(source, destination, dt)

            # 4. [1.1] Store in Redis Sorted Set
            candidate_list = sorted(all_unique_routes.values(), key=lambda x: x.score)
            if multi_layer_cache.redis:
                await multi_layer_cache.redis.delete(pool_key, data_key, seen_key)
                
                # Use pipeline for atomicity and speed
                async with multi_layer_cache.redis.pipeline(transaction=True) as pipe:
                    for r in candidate_list:
                        # Score is the sorting cursor
                        await pipe.zadd(pool_key, {r.journey_id: r.score})
                        # Data is stored in Hash for efficient random access
                        await pipe.hset(data_key, r.journey_id, json.dumps(r.to_dict(), default=str))
                    
                    await pipe.expire(pool_key, 1800)
                    await pipe.expire(data_key, 1800)
                    await pipe.execute()

            # 5. Verify only first batch (Lazy Loading - Task 1.2)
            initial_batch = candidate_list[:limit]
            
            # [Subtask 4.4] Surge Level 2 Protection: Disable ML & Verification
            if jit_metrics.surge_level >= SurgeLevel.HIGH:
                logger.warning("🚦 Surge Level 2 Active: Skipping ML verification to save resources.")
                verified_routes = initial_batch
                for r in verified_routes:
                    r.metadata["verification_skipped"] = True
                    r.availability_probability = 0.5 # Default
            else:
                verified_routes = await self._verify_routes_parallel(initial_batch, dt, quota)

            # Mark as seen
            if multi_layer_cache.redis:
                for r in verified_routes:
                    await multi_layer_cache.redis.sadd(seen_key, r.journey_id)
                await multi_layer_cache.redis.expire(seen_key, 1800)

            # [9.2] High-Risk Detection: GN_WL > 50 or Probability < 0.5
            high_risk_count = sum(1 for r in verified_routes if r.availability_probability < 0.5)
            logger.info(f"Verification Results: {len(verified_routes)} routes, High Risk: {high_risk_count}")
            
            # [9.3] Auto-Trigger Tatkal Search
            if quota == "GN" and high_risk_count >= (len(verified_routes) / 2) and len(verified_routes) > 0:
                logger.info(f"High risk GN yield detected ({high_risk_count}). Auto-triggering Tatkal search [9.3].")
                tatkal_results = await orchestrator.search_all_tiers(source, destination, dt, c, 10, self.transit_db)
                logger.info(f"Tatkal Search found {len(tatkal_results)} candidates.")
                # Re-verify with Quota="TQ"
                verified_tq = await self._verify_routes_parallel(tatkal_results, dt, "TQ")
                logger.info(f"Verified {len(verified_tq)} Tatkal routes.")
                
                for r in verified_tq:
                    r.metadata["quota"] = "TQ"
                    r.metadata["is_alternative"] = True
                    r.metadata["is_verified"] = True 
                    r.metadata["ui_reasons"] = r.metadata.get("ui_reasons", []) + ["High Availability Alternative (Tatkal)"]
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
                
                logger.info(f"Final verified_routes count: {len(verified_routes)}")

                # [9.9] Update Redis Cache with new alternatives
                if multi_layer_cache.redis:
                    async with multi_layer_cache.redis.pipeline(transaction=True) as pipe:
                        for r in verified_tq:
                            await pipe.zadd(pool_key, {r.journey_id: r.score})
                            await pipe.hset(data_key, r.journey_id, json.dumps(r.to_dict(), default=str))
                        await pipe.execute()

            from core.route_engine.categorization import CategorizationEngine
            from services.unlock_service import UnlockService
            categories = CategorizationEngine.categorize(verified_routes, persona)
            
            # [NEW] Use the already-hydrated routes from CategorizationEngine to preserve pricing
            # We'll pull from 'alternative_sorted' or combine all buckets to get the full list
            all_hydrated_dicts = []
            seen_jids = set()
            for bucket_name, bucket_routes in categories.items():
                if isinstance(bucket_routes, list):
                    for r_dict in bucket_routes:
                        if r_dict["journey_id"] not in seen_jids:
                            all_hydrated_dicts.append(r_dict)
                            seen_jids.add(r_dict["journey_id"])

            masked_journeys = [UnlockService.mask_route(rd) for rd in all_hydrated_dicts]
            
            # [1.1] Determine Next Cursor
            next_cursor = verified_routes[-1].score if verified_routes else None

            import math
            total_pages = math.ceil(len(candidate_list) / limit) if candidate_list else 0
            from core.data_structures import PaginationMetadata
            pagination = PaginationMetadata(
                total_results=len(candidate_list),
                current_page=1,
                limit=limit,
                has_next=len(candidate_list) > limit,
                total_pages=total_pages
            )

            latency = (time.time() - overall_start) * 1000
            final_response = {
                "status": "success",
                "source": source, "destination": destination, "session_id": session_id,
                "data": {
                    "journeys": masked_journeys,
                    "grouped_journeys": {k: ([UnlockService.mask_route(r) for r in v] if isinstance(v, list) else v) for k, v in categories.items()},
                    "pagination": pagination.to_dict(),
                    "next_cursor": next_cursor
                },
                "metadata": {
                    "expansion_triggered": expansion_triggered,
                    "latency_ms": latency,
                    "total_candidates": len(candidate_list),
                    "monetization": "tier_2_masked"
                }
            }

            # Log search
            log = RouteSearchLog(src=source, dst=destination, date=search_date, latency_ms=latency, ip_address=client_ip, geo_state=geo_state)
            self.db.add(log)
            self.db.commit()
            
            logger.info(f"SEARCH SUCCESS: Found {len(masked_journeys)} journeys for {source}->{destination}. JIDs: {[j['journey_id'] for j in masked_journeys]}")
            
            return final_response
        except Exception as e:
            logger.error(f"Error in search_routes: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    async def load_more_routes(self, session_id: str, limit: int = 15, quota: str = "GN", cursor: Optional[float] = None) -> Dict[Any, Any]:
        """Subtask 1.3: Yield-Aware Load More using Cursor (Subtask 1.1)."""
        start_time = time.time()
        await multi_layer_cache.initialize()
        if not multi_layer_cache.redis:
            return {"error": "SESSION_EXPIRED", "message": "Search session expired or cache unavailable"}

        # [18.3] Quota-Specific Keys
        pool_key = f"search:pool:{quota}:{session_id}"
        data_key = f"search:data:{quota}:{session_id}"
        seen_key = f"search:seen:{quota}:{session_id}"
        
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
        await multi_layer_cache.initialize()
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
        constraints = ConstraintsEngine.initialize_constraints(persona.value, datetime.now().date())
        
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
        Subtask 12.3: Upgraded Multi-Tier Verification.
        1. Deep Verification for top 3 (All segments).
        2. Shallow Verification for remaining (Primary segment).
        """
        if not routes: return []
        
        # Sort by total duration to find the "Fastest" for deep verification
        sorted_by_speed = sorted(routes, key=lambda x: x.total_duration)
        top_fastest = sorted_by_speed[:3]
        the_rest = sorted_by_speed[3:30]
        remaining = sorted_by_speed[30:]
        
        # 1. Prepare Deep Queries (Every segment of top 3)
        deep_tasks = []
        for r in top_fastest:
            deep_tasks.append(self._verify_single_route_logic(r, travel_date, quota))
            
        # 2. Prepare Shallow Queries (First segment of the rest for batching)
        shallow_queries = []
        for r in the_rest:
            if not r.segments: continue
            s = r.segments[0]
            shallow_queries.append({
                "train_number": s.train_number,
                "from_station": s.departure_code,
                "to_station": s.arrival_code,
                "date": (travel_date + timedelta(days=r.metadata.get("day_offset", 0))).strftime("%Y-%m-%d"),
                "quota": quota,
                "journey_id": r.journey_id
            })
            
        # Execute everything in parallel
        # Deep checks are heavy, shallow are batched
        deep_results, batch_results = await asyncio.gather(
            asyncio.gather(*deep_tasks),
            self.data_provider.verify_seat_availability_batch(shallow_queries)
        )
        
        # Map batch results back to 'the_rest'
        res_map = {shallow_queries[i]["journey_id"]: batch_results[i] for i in range(len(batch_results))}
        
        verified_rest = []
        for r in the_rest:
            v_res = res_map.get(r.journey_id)
            if v_res:
                r.availability_probability = 0.95 if v_res.get("available_seats", 0) > 0 else 0.4
                r.metadata["is_verified"] = True
            verified_rest.append(r)
            
        # Combine: Deeply Verified Top 3 + Batched Rest + Unverified Remaining
        return list(deep_results) + verified_rest + remaining

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
            route.metadata["is_estimated"] = True
            route.metadata["is_verified"] = False
            return route

    async def _verify_single_route_logic(self, route: Route, travel_date: datetime, quota: str = "GN") -> Route:
        """[14.1] Verification logic with Partial Rescue retry."""
        leg_results = []
        for seg in route.segments:
            # Try verification for this leg
            res = await self._verify_leg_with_retry(seg, travel_date, route.metadata.get("day_offset", 0), quota)
            leg_results.append(res)
            
        total_fare = 0.0
        total_delay = 0
        total_prob = 1.0
        any_failed = False
        
        for seat_res, fare_res, status_res in leg_results:
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

    async def search_routes_stream(self, source: str, destination: str, travel_date: str, budget_category: Optional[str] = None, quota: str = "GN", chunk_size: int = 3):
        """
        [17.1] Streaming SSE search results.
        [17.2] Yields verified routes in batches.
        [1.13] Optimized chunk_size based on load.
        """
        # (Standard Setup Logic - identical to search_routes)
        source = source.upper().strip()
        destination = destination.upper().strip()
        try:
            dt = datetime.strptime(travel_date, "%Y-%m-%d")
        except:
            dt = datetime.now()

        from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
        from core.route_engine.constraints_engine import ConstraintsEngine
        from core.data_structures import Persona
        from services.unlock_service import UnlockService
        
        orchestrator = UnifiedRoutingOrchestrator(self.route_engine)
        persona = Persona(budget_category or "comfort")
        c = ConstraintsEngine.initialize_constraints(persona.value, dt.date(), quota=quota)

        # 1. Yield Initial 'Searching' event
        yield {"status": "searching", "message": "Discovering potential routes..."}

        # 2. Discovery Phase
        search_res = await orchestrator.search_all_tiers(source, destination, dt, c, limit=50, db=self.transit_db)
        yield {"status": "discovered", "count": len(search_res), "message": f"Found {len(search_res)} candidates. Verifying..."}

        # 3. Verification Streaming (Subtask 17.2)
        # We verify in chunks to stream faster
        for i in range(0, len(search_res), chunk_size):
            chunk = search_res[i : i + chunk_size]
            # Use the parallel helper
            verified_chunk = await self._verify_routes_parallel(chunk, dt, quota)
            
            # Mask and yield each route immediately
            masked_chunk = [UnlockService.mask_route(r.to_dict()) for r in verified_chunk if r.metadata.get("is_verified")]
            if masked_chunk:
                yield {
                    "status": "partial_results",
                    "journeys": masked_chunk,
                    "progress": round((i + len(chunk)) / len(search_res) * 100, 1)
                }
            
            # Brief sleep to allow SSE buffer flush and UI reactivity
            await asyncio.sleep(0.05)

        yield {"status": "complete", "message": "All routes verified."}

    def __del__(self):
        if hasattr(self, 'transit_db'):
            try: self.transit_db.close()
            except: pass
