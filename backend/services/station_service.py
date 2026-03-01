"""
Station Service - UNIFIED VERSION (SQLite & PostGIS Compatible)
Removed all PG-specific functions and replaced with platform-agnostic ones.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, text, or_
from typing import List, Dict
import math
import json
import logging

from database.models import Stop
from core.redis import redis_client

logger = logging.getLogger(__name__)

class StationService:
    def __init__(self, db: Session):
        self.db = db

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
        lon_range = radius_km / (111.0 * math.cos(math.radians(latitude)))

        stations = self.db.query(Stop).filter(
            Stop.latitude.between(latitude - lat_range, latitude + lat_range),
            Stop.longitude.between(longitude - lon_range, longitude + lon_range)
        ).limit(limit * 2).all()

        results = []
        for station in stations:
            # Haversine calculation
            dlat = math.radians(station.latitude - latitude)
            dlon = math.radians(station.longitude - longitude)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(latitude)) * math.cos(math.radians(station.latitude)) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            dist = 6371 * c # Distance in km

            if dist <= radius_km:
                results.append({
                    "id": station.id,
                    "name": station.name,
                    "code": station.stop_id,
                    "city": station.city,
                    "latitude": station.latitude,
                    "longitude": station.longitude,
                    "distance_km": round(dist, 2)
                })
        
        return sorted(results, key=lambda x: x["distance_km"])[:limit]

    def get_total_stations_count(self) -> int:
        """Return total number of configured stops."""
        return self.db.query(func.count(Stop.id)).scalar() or 0
