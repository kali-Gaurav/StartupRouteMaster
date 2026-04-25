import logging
from typing import List, Dict, Set, Tuple, cast
from sqlalchemy.orm import Session
from database.models import Stop
from utils.geo_utils import haversine_distance
from core.data_structures import TransferConnection
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class StationClusterManager:
    """
    Task 11: Station Spatial Clustering.
    Groups nearby stations into virtual hubs and manages walking transfers.
    """
    
    # 5km radius for clustering
    CLUSTER_RADIUS_KM = 5.0
    # Average walking speed 4km/h -> 1km in 15 mins
    WALKING_SPEED_KMH = 4.0

    def __init__(self, db: Session):
        self.db = db

    def get_nearby_stations(self, stop_id: int) -> List[Tuple[int, float]]:
        """Finds all stations within the cluster radius."""
        target = self.db.query(Stop).filter(Stop.id == stop_id).first()
        if target is None or target.latitude is None or target.longitude is None:
            return []
        
        # In production, use spatial index (PostGIS/R-Tree). 
        # For now, we do a bounded search or simple scan for demo.
        # Let's mock common Delhi/Mumbai clusters if the DB is small.
        all_stops = self.db.query(Stop).all()
        nearby = []
        
        for s in all_stops:
            if int(cast(int, s.id)) == stop_id: continue
            if s.latitude is None or s.longitude is None:
                continue
            
            dist = haversine_distance(
                float(cast(float, target.latitude)),
                float(cast(float, target.longitude)),
                float(cast(float, s.latitude)),
                float(cast(float, s.longitude)),
            )
            if dist <= self.CLUSTER_RADIUS_KM:
                nearby.append((s.id, dist))
                
        return nearby

    def inject_walking_transfers(self, stop_id: int, arrival_time: datetime) -> List[TransferConnection]:
        """Task 12: Walkable Transfer Logic. Converts nearby stations into transfer edges."""
        nearby = self.get_nearby_stations(stop_id)
        walking_transfers = []
        
        for near_id, dist in nearby:
            # Calculate time needed to walk/cab between stations
            walking_min = int((dist / self.WALKING_SPEED_KMH) * 60) + 15 # +15 min buffer
            
            # Earliest we can depart from the nearby station
            earliest_dep = arrival_time + timedelta(minutes=walking_min)
            
            tr = TransferConnection(
                station_id=near_id,
                station_code=str(near_id),
                arrival_time=arrival_time,
                departure_time=earliest_dep,
                duration_minutes=walking_min,
                station_name=f"Walk to {near_id}", # Real name in prod
                facilities_score=0.0,
                safety_score=50.0,
                platform_from=None,
                platform_to=None,
                is_multi_station=False,
                transfer_type="WALK"
            )
            walking_transfers.append(tr)
            
        return walking_transfers
