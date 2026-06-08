import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from sqlalchemy import text
from typing import List, Optional, Any

from .base import BaseRoutingEngine, RoutingRequest, RoutingResponse
from core.data_utils.structures import Route, RouteSegment

logger = logging.getLogger(__name__)

class HubRoutingEngine(BaseRoutingEngine):
    """
    [Task 121] Backbone Route Engine (Hub-to-Hub Precomputed Paths)
    Responsible for fetching and hydrating tier-0 connections stored 
    in the `hub_connectivity_index` table.
    """
    @property
    def engine_id(self) -> str:
        return "hub_tier_0"

    def _parse_turbo_time(self, time_str: str, base_date: datetime) -> datetime:
        # Simple helper to parse time strings like "HH:MM" relative to a base date
        try:
            if not time_str: return base_date
            parts = time_str.split(":")
            return base_date.replace(hour=int(parts[0]), minute=int(parts[1]), second=0, microsecond=0)
        except Exception:
            return base_date

    def _search_tier_0_hubs(self, src_ids: List[int], dst_ids: List[int], date: datetime, db) -> List[Route]:
        if not db or not src_ids or not dst_ids:
            return []
            
        try:
            results = []
            # We iterate over all pairs in the cluster
            for src_id in src_ids:
                for dst_id in dst_ids:
                    row = db.execute(
                        text("SELECT trains_json FROM hub_connectivity_index WHERE src_hub_id = :src AND dst_hub_id = :dst"), 
                        {"src": src_id, "dst": dst_id}
                    ).fetchone()
                    
                    if not row: continue
                    
                    train_data = row[0]
                    if isinstance(train_data, str):
                        trains = json.loads(train_data)
                    else:
                        trains = train_data # Already a list if using some dialects
                        
                    for t in trains: 
                        rt = Route()
                        tid = t.get('tid', 0)
                        tno = t.get('tno', str(tid))
                        
                        seg = RouteSegment(
                            trip_id=tid, 
                            departure_stop_id=src_id, 
                            arrival_stop_id=dst_id,
                            departure_time=self._parse_turbo_time(t.get('dep', ''), date),
                            arrival_time=self._parse_turbo_time(t.get('arr', ''), date),
                            duration_minutes=int(t.get('duration', 0)), 
                            distance_km=float(t.get('dist', 0.0)), 
                            train_number=tno,
                            train_name=t.get('tname', ""),
                            departure_code=t.get('scode', ""),
                            arrival_code=t.get('dcode', ""),
                            fare=0.0, 
                            service_mask=127, 
                            metadata={"tier": 0}
                        )
                        rt.add_segment(seg)
                        rt.metadata["engine"] = self.engine_id
                        rt.metadata["tier"] = 0
                        results.append(rt)
            return results
        except Exception as e:
            logger.error(f"HubRoutingEngine failed to search hubs: {e}")
            if db:
                db.rollback()
            return []

    async def find_routes(self, request: RoutingRequest) -> RoutingResponse:
        start_time = time.perf_counter()
        
        try:
            # Note: HubRouter returns a list of Route objects
            routes = await asyncio.to_thread(
                self._search_tier_0_hubs, 
                request.src_cluster_ids, 
                request.dst_cluster_ids, 
                request.departure_date, 
                request.db_session
            )
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            # Apply standard metadata
            for r in routes:
                if "engine" not in r.metadata:
                    r.metadata["engine"] = self.engine_id
            
            return RoutingResponse(
                engine_name=self.engine_id,
                routes=routes,
                latency_ms=latency_ms,
                yield_count=len(routes)
            )

        except Exception as e:
            logger.error(f"HubRoutingEngine Failure: {e}", exc_info=True)
            return RoutingResponse(
                engine_name=self.engine_id, 
                routes=[], 
                latency_ms=(time.perf_counter() - start_time) * 1000, 
                yield_count=0,
                triage_status="FAILED",
                metadata={"error": str(e)}
            )
