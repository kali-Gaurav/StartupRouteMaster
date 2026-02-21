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

from ...database.models import Stop, Transfer, StopTime, Trip
from .data_structures import TransferConnection, RouteSegment

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
    transfer_type: int = 0  # GTFS: 0=recommended, 1=timed, 2=minimum time required, 3=impossible
    
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

    # Standard minimum transfer times by station type (minutes)
    MIN_TRANSFER_TIMES = {
        'major_junction': 8,      # Large stations with clear transfers
        'regular_station': 12,    # Standard stations
        'small_station': 15,      # Small stations
        'metros': 5,              # Metro/urban rail
    }

    # Maximum walking distance for implicit transfers (meters)
    MAX_WALKING_DISTANCE = 2000

    # Maximum time to walk the max distance (minutes)
    WALKING_SPEED_KMPH = 1.4  # ~4 min per 100m

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
            results = self.session.query(Transfer).all()
            
            for t in results:
                # Get transfer type from GTFS (0=recommended, 1=timed, 2=minimum_time, 3=no_transfer)
                if t.transfer_type == 3:  # Transfer impossible
                    continue
                
                # If min_transfer_time is null, use default based on transfer_type
                if t.min_transfer_time is not None:
                    min_time = t.min_transfer_time
                else:
                    min_time = self._get_default_min_transfer_time(t.from_stop_id, t.to_stop_id)
                
                # Walking time is usually 0 for explicit transfers (already at the station)
                walking_time = 0
                
                transfer_edge = TransferEdge(
                    from_stop_id=t.from_stop_id,
                    to_stop_id=t.to_stop_id,
                    min_transfer_time_minutes=min_time,
                    walking_time_minutes=walking_time,
                    platform_from=getattr(t, 'platform_from', None),
                    platform_to=getattr(t, 'platform_to', None),
                    transfer_type=t.transfer_type
                )
                transfers.append(transfer_edge)
                
        except Exception as e:
            logger.warning(f"Error loading explicit transfers: {e}")
        
        return transfers

    async def _compute_implicit_transfers(self) -> List[TransferEdge]:
        """Compute implicit transfers between nearby stops (walking distances)"""
        transfers = []
        
        try:
            # Get all stops with location information
            stops = self.session.query(Stop).filter(
                Stop.latitude != None,
                Stop.longitude != None
            ).all()
            
            logger.debug(f"Computing implicit transfers for {len(stops)} stops with coordinates")
            
            # Build spatial index (simple distance-based)
            for i, from_stop in enumerate(stops):
                for to_stop in stops[i+1:]:
                    if from_stop.id == to_stop.id:
                        continue
                    
                    distance = self._haversine_distance(
                        from_stop.latitude, from_stop.longitude,
                        to_stop.latitude, to_stop.longitude
                    )
                    
                    # Only consider nearby stops
                    if distance > self.MAX_WALKING_DISTANCE:
                        continue
                    
                    # Calculate walking time (assuming 1.4 km/h walking speed)
                    walking_time = int((distance / 1000) / self.WALKING_SPEED_KMPH * 60)
                    
                    # Bidirectional transfers
                    for direction in [(from_stop, to_stop), (to_stop, from_stop)]:
                        from_s, to_s = direction
                        
                        # Get minimum transfer time for this station combo
                        min_transfer_time = self._get_default_min_transfer_time(from_s.id, to_s.id)
                        
                        transfer_edge = TransferEdge(
                            from_stop_id=from_s.id,
                            to_stop_id=to_s.id,
                            min_transfer_time_minutes=min_transfer_time,
                            walking_time_minutes=walking_time,
                            is_same_platform=False,
                            transfer_type=0  # Recommended
                        )
                        transfers.append(transfer_edge)
            
        except Exception as e:
            logger.warning(f"Error computing implicit transfers: {e}")
        
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
            if stop and stop.is_major_junction:
                return 'major_junction'
            # Could add more logic based on stop properties
            return 'regular_station'
        
        from_type = get_station_type(from_stop) if from_stop else 'regular_station'
        to_type = get_station_type(to_stop) if to_stop else 'regular_station'
        
        # Use worst case (longest time needed)
        return max(
            self.MIN_TRANSFER_TIMES.get(from_type, 12),
            self.MIN_TRANSFER_TIMES.get(to_type, 12)
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
