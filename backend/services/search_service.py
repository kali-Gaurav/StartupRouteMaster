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
        # db is SessionUser (user_store.db)
        self.db = db 
        # We also need SessionTransit (transit_graph.db)
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
        
        # 0. Resolve stations via Transit DB
        source_stop, dest_stop = resolve_stations(self.transit_db, source, destination)
        if not source_stop or not dest_stop:
            return {"source": source, "destination": destination, "journeys": [], "error": "Station not found"}

        # 1. Check for Auto-Throttle
        await multi_layer_cache.initialize()
        is_throttled = await multi_layer_cache.redis.get("system:low_latency_mode") if multi_layer_cache.redis else False
        
        try:
            dt = datetime.strptime(travel_date, "%Y-%m-%d")
        except:
            dt = datetime.now()

        results = []
        
        # 2. Try Turbo (SQLite index)
        t_start = time.perf_counter()
        from core.route_engine.turbo_router import TurboRouter
        turbo = TurboRouter()
        turbo_res = turbo.find_routes(source, destination, dt, limit=limit)
        t_dur = (time.perf_counter() - t_start) * 1000
        await self._log_engine_metrics("turbo", t_dur, len(turbo_res) > 0)
        results.extend(turbo_res)

        # 3. RAPTOR (Only if needed and NOT throttled)
        if len(results) < 3 and not is_throttled:
            r_start = time.perf_counter()
            from core.route_engine.constraints import RouteConstraints
            c = RouteConstraints(max_transfers=2, max_results=limit)
            # Pass our transit_db session to ensure it finds tables
            raptor_res = await self.route_engine.search_routes(source, destination, dt, c, db=self.transit_db)
            r_dur = (time.perf_counter() - r_start) * 1000
            await self._log_engine_metrics("raptor", r_dur, len(raptor_res) > 0)
            
            for rt in raptor_res:
                results.append({
                    "journey_id": f"rt_{rt.segments[0].trip_id}",
                    "type": "raptor",
                    "transfers": len(rt.transfers),
                    "legs": [s.__dict__ for s in rt.segments]
                })

        # 4. Fingerprinting
        ids_blob = "".join([str(j.get("journey_id", "")) for j in results])
        fingerprint = hashlib.sha256(ids_blob.encode()).hexdigest()[:12]

        return {
            "source": source, "destination": destination, "journeys": results,
            "fingerprint": fingerprint, "is_throttled": bool(is_throttled),
            "latency_ms": (time.time() - overall_start) * 1000
        }

    def __del__(self):
        if hasattr(self, 'transit_db'):
            self.transit_db.close()
