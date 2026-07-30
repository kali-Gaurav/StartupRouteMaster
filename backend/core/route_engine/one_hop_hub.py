import sqlite3
import logging
from datetime import datetime, timedelta, date
from typing import List, Set, Any, Dict
from .base import BaseRoutingEngine, RoutingRequest, RoutingResponse
from core.data_utils.structures import Route, RouteSegment

logger = logging.getLogger(__name__)

class OneHopHubEngine(BaseRoutingEngine):
    """
    [Engineer 4-6 Task]
    Goal: Find 15+ high-quality 1-transfer routes.
    Strategy: Hub-Based BFS (Depth 1).
    """

    @property
    def engine_id(self) -> str:
        return "one_hop_hub"

    DAY_COLUMNS = {
        0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday",
        4: "friday", 5: "saturday", 6: "sunday"
    }

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._hub_ids_cache = None

    def _get_hubs(self, conn) -> List[int]:
        # [Engineer 4 Task] Pre-calculate Adjacency/Hubs
        if self._hub_ids_cache is None:
            # We use Mega Hubs and Major Junctions
            q = "SELECT id FROM stops WHERE centrality_score > 0.05 OR is_major_junction = 1 LIMIT 300"
            self._hub_ids_cache = [r[0] for r in conn.execute(q).fetchall()]
        return self._hub_ids_cache

    async def find_routes(self, request: RoutingRequest) -> RoutingResponse:
        # [Engineer 5 Task] BFS Depth 1 implementation
        start_ts = datetime.now()
        import asyncio
        loop = asyncio.get_running_loop()
        routes = await loop.run_in_executor(None, self._search_sync, request)
        
        return RoutingResponse(
            engine_name=self.engine_id,
            routes=routes,
            latency_ms=(datetime.now() - start_ts).total_seconds() * 1000,
            yield_count=len(routes)
        )

    def _search_sync(self, request: RoutingRequest) -> List[Route]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            # Resolve src/dst IDs (Reusing logic or simplifying for hub discovery)
            from .exhaustive_direct import ExhaustiveDirectEngine
            resolver = ExhaustiveDirectEngine(self.db_path)
            src_ids = resolver._resolve_terminal_ids(conn, request.source_code)
            dst_ids = resolver._resolve_terminal_ids(conn, request.destination_code)
            
            if not src_ids or not dst_ids: return []
            
            hubs = self._get_hubs(conn)
            travel_date = request.departure_date.date()
            day_name = self.DAY_COLUMNS.get(travel_date.weekday())
            
            # [Engineer 5] Two-stage query to find 1-transfer routes
            # Stage 1: Trips from Source to Hubs
            # Stage 2: Trips from Hubs to Destination
            # We do a JOIN across Hubs
            
            query = f"""
                SELECT 
                    t1.id as tid1, t1.trip_id as tno1, s1a.stop_id as sid1a, s1b.stop_id as sid1b,
                    st1a.code as code1a, st1b.code as code1b, s1a.departure_timestamp as ts1a, s1b.arrival_timestamp as ts1b,
                    t2.id as tid2, t2.trip_id as tno2, s2a.stop_id as sid2a, s2b.stop_id as sid2b,
                    st2a.code as code2a, st2b.code as code2b, s2a.departure_timestamp as ts2a, s2b.arrival_timestamp as ts2b
                FROM trips t1
                JOIN calendar c1 ON t1.service_id = c1.service_id
                JOIN stop_times s1a ON t1.id = s1a.trip_id
                JOIN stop_times s1b ON t1.id = s1b.trip_id
                JOIN stops st1a ON s1a.stop_id = st1a.id
                JOIN stops st1b ON s1b.stop_id = st1b.id
                
                JOIN stop_times s2a ON s1b.stop_id = s2a.stop_id -- Transfer at Hub
                JOIN trips t2 ON s2a.trip_id = t2.id
                JOIN calendar c2 ON t2.service_id = c2.service_id
                JOIN stop_times s2b ON t2.id = s2b.trip_id
                JOIN stops st2a ON s2a.stop_id = st2a.id
                JOIN stops st2b ON s2b.stop_id = st2b.id
                
                WHERE s1a.stop_id IN ({','.join('?' for _ in src_ids)})
                  AND s2b.stop_id IN ({','.join('?' for _ in dst_ids)})
                  AND s1b.stop_id IN ({','.join('?' for _ in hubs)})
                  AND c1.{day_name} = 1 AND c2.{day_name} = 1
                  AND s2a.departure_timestamp > s1b.arrival_timestamp + 1800 -- 30m min transfer
                  AND s2a.departure_timestamp < s1b.arrival_timestamp + 21600 -- 6h max transfer
                  AND s1b.stop_sequence > s1a.stop_sequence
                  AND s2b.stop_sequence > s2a.stop_sequence
                LIMIT 30
            """
            params = src_ids + dst_ids + hubs
            rows = conn.execute(query, params).fetchall()
            
            routes = []
            for row in rows:
                rt = Route()
                # Leg 1
                rt.add_segment(RouteSegment(
                    trip_id=row['tid1'], departure_stop_id=row['sid1a'], arrival_stop_id=row['sid1b'],
                    departure_time=datetime.combine(travel_date, datetime.min.time()) + timedelta(seconds=row['ts1a']),
                    arrival_time=datetime.combine(travel_date, datetime.min.time()) + timedelta(seconds=row['ts1b']),
                    duration_minutes=(row['ts1b'] - row['ts1a']) // 60,
                    train_number=str(row['tno1']), train_name="L1", departure_code=row['code1a'], arrival_code=row['code1b']
                ))
                # Leg 2
                rt.add_segment(RouteSegment(
                    trip_id=row['tid2'], departure_stop_id=row['sid2a'], arrival_stop_id=row['sid2b'],
                    departure_time=datetime.combine(travel_date, datetime.min.time()) + timedelta(seconds=row['ts2a']),
                    arrival_time=datetime.combine(travel_date, datetime.min.time()) + timedelta(seconds=row['ts2b']),
                    duration_minutes=(row['ts2b'] - row['ts2a']) // 60,
                    train_number=str(row['tno2']), train_name="L2", departure_code=row['code2a'], arrival_code=row['code2b']
                ))
                rt.metadata["engine"] = self.engine_id
                routes.append(rt)
            return routes
        finally:
            conn.close()
