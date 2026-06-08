"""
Station Service - UNIFIED VERSION (SQLite & PostGIS Compatible)
Removed all PG-specific functions and replaced with platform-agnostic ones.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, text, or_
from typing import List, Dict, Optional
import math
import json
import logging

from database.models import Stop
from core.infrastructure.redis_manager import redis_client

logger = logging.getLogger(__name__)

class StationService:
    def __init__(self, db: Session):
        self.db = db

    def get_station(self, code: str) -> Optional[Dict]:
        """Retrieve a station by its code or stop_id."""
        try:
            row = self.db.execute(
                text(
                    """
                    SELECT id, stop_id, code, name, city, state, latitude, longitude
                    FROM stops
                    WHERE UPPER(code) = UPPER(:code) OR UPPER(stop_id) = UPPER(:code)
                    LIMIT 1
                    """
                ),
                {"code": code},
            ).mappings().first()
            if not row:
                return None
            return {
                "name": row["name"],
                "code": row["code"],
                "city": row["city"],
                "state": row["state"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
            }
        except Exception as e:
            logger.warning(f"Error querying station {code}: {e}")
            try: self.db.rollback()
            except: pass
            return None

    def search_stations_by_name(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Unified search for stations by name or code using high-performance engine (transit_graph.db).
        """
        if not query or len(query) < 2:
            return []
            
        from services.station_search_service import station_search_engine
        
        suggestions = station_search_engine.suggest(query, limit=limit)
        return [
            {
                "name": s.name,
                "code": s.code,
                "city": s.city,
                "state": s.state
            }
            for s in suggestions
        ]

    def get_stations_near_me(self, latitude: float, longitude: float, radius_km: float, limit: int = 10) -> List[Dict]:
        """
        Finds stations within a radius using the GTFS 'stops' table.
        Uses Haversine approximation for database compatibility.
        """
        # Approx 111km per degree latitude
        lat_range = radius_km / 111.0
        # Approx 111km * cos(lat) per degree longitude
        try:
            cos_lat = math.cos(math.radians(latitude))
            if abs(cos_lat) < 1e-6:
                lon_range = 0.0
            else:
                lon_range = radius_km / (111.0 * cos_lat)

            stations = self.db.execute(
                text(
                    """
                    SELECT id, stop_id, code, name, city, latitude, longitude
                    FROM stops
                    WHERE latitude BETWEEN :min_lat AND :max_lat
                      AND longitude BETWEEN :min_lon AND :max_lon
                    LIMIT :limit
                    """
                ),
                {
                    "min_lat": latitude - lat_range,
                    "max_lat": latitude + lat_range,
                    "min_lon": longitude - lon_range,
                    "max_lon": longitude + lon_range,
                    "limit": limit * 2,
                },
            ).mappings().all()

            results = []
            for station in stations:
                # Haversine calculation
                try:
                    station_lat = float(station["latitude"])
                    station_lon = float(station["longitude"])
                    dlat = math.radians(station_lat - float(latitude))
                    dlon = math.radians(station_lon - float(longitude))
                    a = math.sin(dlat/2)**2 + math.cos(math.radians(float(latitude))) * math.cos(math.radians(station_lat)) * math.sin(dlon/2)**2
                    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                    dist = 6371 * c # Distance in km
                except Exception as e:
                    logger.warning(f"Error in Haversine calculation: {e}")
                    continue

                if dist <= radius_km:
                    results.append({
                        "id": station["id"],
                        "name": station["name"],
                        "code": station["stop_id"],
                        "city": station["city"],
                        "latitude": station_lat,
                        "longitude": station_lon,
                        "distance_km": round(dist, 2)
                    })
            results.sort(key=lambda x: x["distance_km"])
            return results[:limit]
        except Exception as e:
            logger.warning(f"Error finding stations near me: {e}")
            try: self.db.rollback()
            except: pass
            return []

    def get_total_stations_count(self) -> int:
        """Return total number of configured stops."""
        return self.db.query(func.count(Stop.id)).scalar() or 0
