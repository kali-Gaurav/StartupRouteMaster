"""
Station Service - UNIFIED VERSION (SQLite & PostGIS Compatible)
Removed all PG-specific functions and replaced with platform-agnostic ones.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, text, or_
from typing import List, Dict
import math

from backend.models import Stop as Station # Use Stop as alias

class StationService:
    def __init__(self, db: Session):
        self.db = db

    def search_stations_by_name(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Unified search for stations by name.
        Uses standard LIKE for generic compatibility. Fuzziness handled by client or resolver.
        """
        if not query or len(query) < 2:
            return []
            
        stations = self.db.query(Station).filter(
            or_(
                Station.name.ilike(f"%{query}%"),
                Station.stop_id.ilike(f"%{query}%"),
                Station.city.ilike(f"%{query}%")
            )
        ).limit(limit).all()

        return [
            {"name": station.name, "code": station.stop_id, "city": station.city, "id": station.id}
            for station in stations
        ]

    def get_stations_near_me(self, latitude: float, longitude: float, radius_km: float, limit: int = 10) -> List[Dict]:
        """
        Finds stations within a radius.
        Uses Haversine approximation for database compatibility.
        """
        # SQLite doesnt support math functions like COS directly in SQL without extensions.
        # We fetch a bounding box of stations first, then filter in memory.
        
        # Approx 111km per degree latitude
        lat_range = radius_km / 111.0
        # Approx 111km * cos(lat) per degree longitude
        lon_range = radius_km / (111.0 * math.cos(math.radians(latitude)))

        stations = self.db.query(Station).filter(
            Station.latitude.between(latitude - lat_range, latitude + lat_range),
            Station.longitude.between(longitude - lon_range, longitude + lon_range)
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
                    "city": station.city,
                    "latitude": station.latitude,
                    "longitude": station.longitude,
                    "distance_km": round(dist, 2)
                })
        
        return sorted(results, key=lambda x: x["distance_km"])[:limit]
