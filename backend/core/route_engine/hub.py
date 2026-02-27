from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime
import logging

from sqlalchemy import or_

from database.models import Stop

from utils.graph_utils import haversine_distance
from .graph import TimeDependentGraph

logger = logging.getLogger(__name__)

@dataclass
class HubToHubConnection:
    """Precomputed best travel time between two hubs"""
    source_hub_id: int
    dest_hub_id: int
    min_travel_time: int
    best_trip_id: Optional[int] = None
    frequency_per_day: int = 0


class HubConnectivityTable:
    """Precomputed hub-to-hub connectivity (Step 2: Precompute Hub Distances)"""

    def __init__(self):
        self.connections: Dict[Tuple[int, int], HubToHubConnection] = {}

    def add_connection(self, conn: HubToHubConnection):
        self.connections[(conn.source_hub_id, conn.dest_hub_id)] = conn

    def get_min_time(self, source_hub: int, dest_hub: int) -> Optional[int]:
        conn = self.connections.get((source_hub, dest_hub))
        return conn.min_travel_time if conn else None


class HubManager:
    """Manages hub station selection and lookup"""
    
    # Major hubs (Step 1: Select Hub Stations)
    MAJOR_HUB_CODES = ['NDLS', 'CSMT', 'MAS', 'HWH', 'SBC', 'PNBE', 'LKO', 'ADI', 'BCT']

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.hub_ids: Set[int] = set()
        self.hub_id_to_code: Dict[int, str] = {}

    def initialize_hubs(self):
        """Load hub information from DB using the fastest available session."""
        from .builder import TransitSessionLocal
        session = TransitSessionLocal()
        try:
            try:
                hubs = session.query(Stop).filter(
                    or_(
                        Stop.is_major_junction == True,
                        Stop.code.in_(self.MAJOR_HUB_CODES)
                    )
                ).all()
            except Exception as e:
                # Fallback to Postgres if SQLite fails or is unprepared
                logger.warning(f"SQLite hub query failed ({e}), falling back to Postgres")
                session.close()
                session = self.session_factory()
                hubs = session.query(Stop).filter(
                    or_(
                        Stop.is_major_junction == True,
                        Stop.code.in_(self.MAJOR_HUB_CODES)
                    )
                ).all()

            self.hub_ids = {h.id for h in hubs}
            self.hub_id_to_code = {h.id: h.code for h in hubs}
            logger.info(f"Initialized {len(self.hub_ids)} hub stations.")
        finally:
            session.close()

    def is_hub(self, stop_id: int) -> bool:
        return stop_id in self.hub_ids

    def get_nearest_hubs(self, stop_id: int, graph: 'TimeDependentGraph', max_hubs: int = 3) -> List[Tuple[int, int]]:
        """
        Find nearest hubs and travel time to them.
        Step 3: Hub Search Flow - Identification
        """
        if self.is_hub(stop_id):
            return [(stop_id, 0)]

        # Find hubs within a reasonable distance using haversine or graph search
        stop = graph.stop_cache.get(stop_id)
        if not stop:
            return []

        hubs_with_dist = []
        for hub_id in self.hub_ids:
            hub_stop = graph.stop_cache.get(hub_id)
            if not hub_stop:
                continue
            
            # Simple distance-based proximity
            dist = haversine_distance(stop.latitude, stop.longitude, 
                                    hub_stop.latitude, hub_stop.longitude)
            if dist < 250: # 250km radius for hubs
                hubs_with_dist.append((hub_id, int(dist * 1.5))) # 1.5 min per km approx

        hubs_with_dist.sort(key=lambda x: x[1])
        return hubs_with_dist[:max_hubs]

    async def precompute_hub_connectivity(self, graph: 'TimeDependentGraph', date: datetime):
        """
        Precompute best travel time between all hubs.
        Step 2: Precompute Hub Distances
        """
        # Lazy import to avoid circular dependency
        from .raptor import OptimizedRAPTOR
        from .constraints import RouteConstraints
        
        raptor = OptimizedRAPTOR(max_initial_departures=50)
        # Topic 2: Performance optimization - use a single departure time for hubs
        constraints = RouteConstraints(
            max_transfers=1,
            range_minutes=0 # ONLY check the specific time
        )
        
        hub_list = list(self.hub_ids)
        table = HubConnectivityTable()
        
        logger.info(f"Precomputing connectivity for {len(hub_list)} hubs...")
        
        for i, src_hub in enumerate(hub_list):
            for j, dst_hub in enumerate(hub_list):
                if i == j: continue
                
                # Run a limited RAPTOR between hubs
                routes = await raptor._compute_routes(src_hub, dst_hub, date, constraints, graph=graph)
                if routes:
                    best_route = routes[0]
                    conn = HubToHubConnection(
                        source_hub_id=src_hub,
                        dest_hub_id=dst_hub,
                        min_travel_time=best_route.total_duration,
                        best_trip_id=best_route.segments[0].trip_id if best_route.segments else None,
                        frequency_per_day=len(routes)
                    )
                    table.add_connection(conn)
            
            if i % 10 == 0:
                logger.info(f"Hub Connectivity Progress: {i}/{len(hub_list)} hubs processed")
                
        return table
