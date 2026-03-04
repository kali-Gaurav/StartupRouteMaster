import math
import logging
from typing import List, Dict, Any, Optional
from database.session import SessionTransit
from sqlalchemy import text

logger = logging.getLogger(__name__)

class ConnectivityService:
    def __init__(self):
        self.transit_db = SessionTransit()

    def _haversine(self, lat1, lon1, lat2, lon2):
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def check_upcoming_dead_zones(self, lat: float, lng: float, radius_km: float = 10.0) -> List[Dict[str, Any]]:
        """
        Task 33: Identify if the passenger is approaching a known signal dead zone.
        """
        if not lat or not lng:
            return []
            
        try:
            # Query all dead zones
            query = text("SELECT id, latitude, longitude, radius_km, expected_duration_mins, description FROM signal_dead_zones")
            results = self.transit_db.execute(query).fetchall()
            
            approaching_zones = []
            for row in results:
                zone_id, zone_lat, zone_lng, zone_radius, duration, desc = row
                dist = self._haversine(lat, lng, zone_lat, zone_lng)
                
                # If within user-specified buffer (default 10km)
                if dist <= (radius_km + zone_radius):
                    approaching_zones.append({
                        "id": zone_id,
                        "distance_km": round(dist, 2),
                        "radius_km": zone_radius,
                        "expected_duration_mins": duration,
                        "description": desc,
                        "is_imminent": dist <= zone_radius
                    })
            
            return approaching_zones
        except Exception as e:
            logger.error(f"Error checking dead zones: {e}")
            return []
        finally:
            self.transit_db.close()

connectivity_service = ConnectivityService()
