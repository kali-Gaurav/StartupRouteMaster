import asyncio
import logging
import orjson as json
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
import time
import hashlib
from datetime import datetime, timedelta

from core.route_engine import RouteEngine, route_engine
from database.config import Config
from services.multi_layer_cache import multi_layer_cache, RouteQuery
from utils.station_utils import resolve_stations
from utils import metrics

logger = logging.getLogger(__name__)

class SearchService:
    def __init__(self, db: Session, route_engine_instance: Optional[RouteEngine] = None):
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

    async def search_routes(self, source: str, destination: str, travel_date: str, budget_category: Optional[str] = None, limit: int = 15) -> Dict[str, Any]:
        overall_start = time.time()
        
        # Suggestion #25: Failed Resolution Cache (Fast-Exit)
        fail_key = f"fail:{source}:{destination}:{travel_date}"
        await multi_layer_cache.initialize()
        if multi_layer_cache.redis and await multi_layer_cache.redis.exists(fail_key):
            return {
                "source": source, "destination": destination, "journeys": [], 
                "status": "cached_no_route", "latency_ms": (time.time() - overall_start) * 1000
            }

        # 0. Resolve stations via Transit DB
        source_stop, dest_stop = resolve_stations(self.transit_db, source, destination)
        if not source_stop or not dest_stop:
            return {"source": source, "destination": destination, "journeys": [], "error": "Station not found"}

        try:
            dt = datetime.strptime(travel_date, "%Y-%m-%d")
        except:
            dt = datetime.now()

        results = []
        days_searched = 0
        
        # 1. EXPANDING SEARCH
        while len(results) < 3 and days_searched < 3:
            current_dt = dt + timedelta(days=days_searched)
            from core.route_engine.turbo_router import TurboRouter
            turbo = TurboRouter()
            turbo_res = turbo.find_routes(source, destination, current_dt, limit=limit)
            
            for r in turbo_res:
                r["day_offset"] = days_searched
                results.append(r)
            
            if len(results) >= 3: break
            days_searched += 1

        # 2. RAPTOR
        if len(results) < 3:
            r_start = time.perf_counter()
            from core.route_engine.constraints import RouteConstraints
            c = RouteConstraints(max_transfers=2, max_results=limit)
            raptor_res = await self.route_engine.search_routes(source, destination, dt, c, db=self.transit_db)
            
            for rt in raptor_res:
                results.append({
                    "journey_id": f"rt_{rt.segments[0].trip_id}",
                    "type": "raptor",
                    "transfers": len(rt.transfers),
                    "legs": [s.__dict__ for s in rt.segments]
                })
            await self._log_engine_metrics("raptor", (time.perf_counter()-r_start)*1000, len(raptor_res)>0)

        # 3. Fingerprinting
        ids_blob = "".join([str(j.get("journey_id", j.get("train_no", ""))) for j in results])
        
        # Suggestion #25: Store failure if found nothing after all tiers
        if not results and multi_layer_cache.redis:
            await multi_layer_cache.redis.setex(fail_key, 3600, "1")

        fingerprint = hashlib.sha256(ids_blob.encode()).hexdigest()[:12]

        return {
            "source": source, "destination": destination, "journeys": results,
            "fingerprint": fingerprint, "days_expanded": days_searched,
            "latency_ms": (time.time() - overall_start) * 1000
        }

    def __del__(self):
        if hasattr(self, 'transit_db'):
            try: self.transit_db.close()
            except: pass
