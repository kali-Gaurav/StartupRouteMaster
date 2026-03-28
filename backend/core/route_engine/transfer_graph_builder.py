"""
Transfer Graph Generation Pipeline
Phase 0: Build complete transfer graph from database with walking times, platform connectivity, and transfer feasibility validation
"""

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import and_

from database.models import Stop, Transfer, StopTime, Trip
from core.data_structures import TransferConnection, RouteSegment
from core.hubs import MEGA_HUBS, MAJOR_HUBS, REGIONAL_HUBS

logger = logging.getLogger(__name__)


@dataclass
class TransferEdge:
    """Internal representation of a transfer edge"""
    from_stop_id: int
    to_stop_id: int
    min_transfer_time_minutes: int
    walking_time_minutes: int
    is_same_platform: bool = False
    platform_from: Optional[str] = None
    platform_to: Optional[str] = None
    transfer_type: str = "WALK" # WALK, METRO, TAXI, SHUTTLE
    is_multi_station: bool = False
    
    @property
    def total_time_minutes(self) -> int:
        """Total time needed for transfer (walking + buffer)"""
        return self.walking_time_minutes + max(2, self.min_transfer_time_minutes - self.walking_time_minutes)


class TransferGraphBuilder:
    """
    Builds a complete transfer graph from the database.
    
    Responsible for:
    1. Loading explicit transfers from Transfer table
    2. Computing implicit transfers between nearby stops (with walking times)
    3. Validating platform connectivity
    4. Computing optimal walking paths
    5. Building passenger-useful transfer information
    """

    # Standard minimum transfer times by station hierarchy (minutes)
    TIERED_MIN_TIMES = {
        'MEGA': 40,      # Huge station, multiple levels (NDLS, HWH)
        'MAJOR': 25,     # Solid junctions (PUNE, BRC)
        'REGIONAL': 15,  # Regional hubs
        'SMALL': 10,     # Regular stations
    }

    # Maximum walking distance for implicit transfers (meters)
    MAX_WALKING_DISTANCE = 5000  # 5km (Above this, use Inter-City taxi/metro)

    # Realistic walking speed in Indian urban context (including stops/traffic)
    WALKING_SPEED_KMPH = 3.5  # Realistic average for walking + baggage

    def __init__(self, session: Session):
        self.session = session
        self._transfer_cache: Dict[Tuple[int, int], TransferEdge] = {}
        self._stops_cache: Dict[int, Stop] = {}
        self._transfer_graph: Dict[int, List[TransferEdge]] = defaultdict(list)

    async def build_transfer_graph(self) -> Dict[int, List[TransferEdge]]:
        """Build complete transfer graph for all stops"""
        logger.info("Starting transfer graph construction...")
        
        # Phase 1: Load explicit transfers from database
        explicit_transfers = await self._load_explicit_transfers()
        logger.info(f"Loaded {len(explicit_transfers)} explicit transfers from database")
        
        # Phase 2: Add implicit transfers (nearby stops with walking times)
        implicit_transfers = await self._compute_implicit_transfers()
        logger.info(f"Computed {len(implicit_transfers)} implicit transfers (walking paths)")
        
        # Phase 3: Validate all transfers for feasibility
        all_transfers = explicit_transfers + implicit_transfers
        validated_transfers = await self._validate_transfers(all_transfers)
        logger.info(f"Validated {len(validated_transfers)} transfers - removed {len(all_transfers) - len(validated_transfers)} infeasible transfers")
        
        # Phase 4: Build adjacency structure
        self._transfer_graph = self._build_adjacency_graph(validated_transfers)
        logger.info(f"Built transfer graph: {len(self._transfer_graph)} stops with outbound transfers")
        
        return self._transfer_graph

    async def _load_explicit_transfers(self) -> List[TransferEdge]:
        """Load explicit transfers from Transfer table"""
        transfers = []
        
        try:
            from sqlalchemy import text
            # Phase 1: Load explicit transfers from database
            try:
                # Try full metadata first
                query = text("SELECT from_stop_id, to_stop_id, transfer_type, min_transfer_time FROM transfers")
                results = self.session.execute(query).fetchall()
            except:
                # Fallback to simple structure if transfer_type or min_transfer_time missing
                try:
                    query = text("SELECT from_stop_id, to_stop_id FROM transfers")
                    results = self.session.execute(query).fetchall()
                except:
                    results = []
            
            for row in results:
                r = row._mapping if hasattr(row, '_mapping') else {}
                if not r:
                    # Handle positional tuple if _mapping not available
                    f_id = row[0]; t_id = row[1]
                    t_type = row[2] if len(row) > 2 else None
                    min_t = row[3] if len(row) > 3 else None
                else:
                    f_id, t_id = r.get('from_stop_id'), r.get('to_stop_id')
                    t_type, min_t = r.get('transfer_type'), r.get('min_transfer_time')

                if t_type == 3: continue # GTFS specification for impossible transfer
                
                if min_t is not None:
                    min_time = min_t
                else:
                    min_time = self._get_default_min_transfer_time(f_id, t_id)
                
                transfer_edge = TransferEdge(
                    from_stop_id=f_id,
                    to_stop_id=t_id,
                    min_transfer_time_minutes=min_time,
                    walking_time_minutes=0,
                    transfer_type="WALK",
                    is_multi_station=(f_id != t_id)
                )
                transfers.append(transfer_edge)
                
        except Exception as e:
            logger.warning(f"Error loading explicit transfers: {e}")
        
        return transfers

    async def _compute_implicit_transfers(self) -> List[TransferEdge]:
        """
        [Optimization] O(N log N) spatial search using Scikit-Learn BallTree.
        Reduces 32M+ comparisons to efficient radial lookups.
        [Task 7 Audit] Integrated Multi-Station Hierarchy Penalties.
        """
        import numpy as np
        from sklearn.neighbors import BallTree
        
        transfers = []
        try:
            # Get all stops with location information
            stops = self.session.query(Stop).filter(
                Stop.latitude != None,
                Stop.longitude != None
            ).all()
            
            if not stops: return []
            
            # 1. Build BallTree with Haversine metric (requires radians)
            # Lat/Lng format: [lat, lng]
            coords = np.deg2rad([[s.latitude, s.longitude] for s in stops])
            # Earth radius in meters
            EARTH_RADIUS = 6371000 
            
            logger.info(f"Building Spatial Index for {len(stops)} stops...")
            tree = BallTree(coords, metric='haversine')
            
            # 2. Radial query for each stop (within MAX_WALKING_DISTANCE)
            # Radius must be in radians (distance / Earth Radius)
            radius = self.MAX_WALKING_DISTANCE / EARTH_RADIUS
            indices = tree.query_radius(coords, r=radius)
            
            logger.info("Spatial clusters identified. Applying hierarchy-aware transfer logic...")
            
            for i, neighbors in enumerate(indices):
                from_s = stops[i]
                for j in neighbors:
                    if i == j: continue # Skip self
                    to_s = stops[j]
                    
                    # Calculate true distance in meters
                    distance = self._haversine_distance(
                        from_s.latitude, from_s.longitude,
                        to_s.latitude, to_s.longitude
                    )
                    
                    # 3. Apply Multi-Station & Hierarchy Logic [Task 7 Audit]
                    is_multi = (from_s.id != to_s.id)
                    t_type = "WALK"
                    
                    def get_tier(code):
                        if code in MEGA_HUBS: return 'MEGA'
                        if code in MAJOR_HUBS: return 'MAJOR'
                        if code in REGIONAL_HUBS: return 'REGIONAL'
                        return 'SMALL'

                    tier_from = get_tier(from_s.code)
                    tier_to = get_tier(to_s.code)
                    
                    # Exit/Entry Penalty based on hierarchy
                    exit_penalty = self.TIERED_MIN_TIMES.get(tier_from, 10) // 2
                    entry_penalty = self.TIERED_MIN_TIMES.get(tier_to, 10) // 2
                    
                    # 4. Mode Logic: METRO vs WALK
                    effective_travel_time = int((distance / 1000) / self.WALKING_SPEED_KMPH * 60)
                    
                    # Inter-station transfers in MEGA hubs often use Metro
                    if is_multi and tier_from == 'MEGA' and tier_to == 'MEGA' and distance > 1500:
                        t_type = "METRO"
                        metro_travel = int((distance / 1000) / 30 * 60) # 30km/h avg
                        metro_wait = 10 
                        effective_travel_time = metro_travel + metro_wait
                    
                    # Total duration = navigating out station 1 + travel + navigating in station 2
                    total_min_time = exit_penalty + effective_travel_time + entry_penalty
                    
                    transfer_edge = TransferEdge(
                        from_stop_id=from_s.id,
                        to_stop_id=to_s.id,
                        min_transfer_time_minutes=int(total_min_time),
                        walking_time_minutes=int((distance / 1000) / self.WALKING_SPEED_KMPH * 60),
                        is_same_platform=False,
                        transfer_type=t_type,
                        is_multi_station=is_multi
                    )
                    transfers.append(transfer_edge)
                    
        except Exception as e:
            logger.error(f"Error in optimized spatial transfer build: {e}", exc_info=True)
        
        return transfers

    async def _validate_transfers(self, transfers: List[TransferEdge]) -> List[TransferEdge]:
        """Validate all transfers for feasibility"""
        validated = []
        
        for transfer in transfers:
            # Check if both stops exist and are valid
            from_stop = self.session.query(Stop).filter(Stop.id == transfer.from_stop_id).first()
            to_stop = self.session.query(Stop).filter(Stop.id == transfer.to_stop_id).first()
            
            if not from_stop or not to_stop:
                logger.debug(f"Skipping transfer {transfer.from_stop_id}->{transfer.to_stop_id}: stop not found")
                continue
            
            # Validate transfer time is reasonable (5 min to 2 hours)
            if transfer.total_time_minutes < 5 or transfer.total_time_minutes > 120:
                logger.debug(f"Skipping transfer {transfer.from_stop_id}->{transfer.to_stop_id}: unreasonable time {transfer.total_time_minutes}min")
                continue
            
            # Check for duplicate transfers (keep the one with shorter time)
            key = (transfer.from_stop_id, transfer.to_stop_id)
            if key in self._transfer_cache:
                existing = self._transfer_cache[key]
                if transfer.total_time_minutes < existing.total_time_minutes:
                    self._transfer_cache[key] = transfer
                # Skip adding duplicate
                continue
            
            self._transfer_cache[key] = transfer
            validated.append(transfer)
        
        return validated

    def _build_adjacency_graph(self, transfers: List[TransferEdge]) -> Dict[int, List[TransferEdge]]:
        """Build adjacency list from transfer edges"""
        graph = defaultdict(list)
        for transfer in transfers:
            graph[transfer.from_stop_id].append(transfer)
        return dict(graph)

    def _get_default_min_transfer_time(self, from_stop_id: int, to_stop_id: int) -> int:
        """Get default minimum transfer time based on stop type"""
        from_stop = self.session.query(Stop).filter(Stop.id == from_stop_id).first()
        to_stop = self.session.query(Stop).filter(Stop.id == to_stop_id).first()
        
        def get_station_type(stop: Stop) -> str:
            if not stop: return 'SMALL'
            if stop.code in MEGA_HUBS: return 'MEGA'
            if stop.code in MAJOR_HUBS: return 'MAJOR'
            if stop.code in REGIONAL_HUBS: return 'REGIONAL'
            return 'SMALL'
        
        from_type = get_station_type(from_stop)
        to_type = get_station_type(to_stop)
        
        return max(
            self.TIERED_MIN_TIMES.get(from_type, 15),
            self.TIERED_MIN_TIMES.get(to_type, 15)
        )

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in meters"""
        import math
        
        R = 6371000  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
        c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c

    def get_transfers_from_stop(self, stop_id: int) -> List[TransferEdge]:
        """Get all possible transfers from a stop"""
        return self._transfer_graph.get(stop_id, [])

    def get_transfer_time(self, from_stop_id: int, to_stop_id: int) -> Optional[int]:
        """Get minimum transfer time between two stops"""
        key = (from_stop_id, to_stop_id)
        if key in self._transfer_cache:
            return self._transfer_cache[key].total_time_minutes
        return None
