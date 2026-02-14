from sqlalchemy.orm import Session
from typing import List, Dict
from geoalchemy2.functions import ST_MakePoint, ST_DWithin # Import PostGIS functions
from geoalchemy2.types import Geography # Import Geography type for explicit casting if needed
from sqlalchemy import func # Import func from sqlalchemy for generic functions

from backend.models import Station

class StationService:
    def __init__(self, db: Session):
        self.db = db

    def search_stations_by_name(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Searches for stations by name, returning the top matches.
        """
        if not query or len(query) < 2:
            return []
            
        # A simple ILIKE search. Can be enhanced with fuzzy matching or ranking later.
        stations = self.db.query(Station).filter(
            Station.name.ilike(f"%{query}%")
        ).limit(limit).all()

        return [
            {"name": station.name, "code": station.id, "city": station.city}
            for station in stations
        ]

    def get_stations_near_me(self, latitude: float, longitude: float, radius_km: float, limit: int = 10) -> List[Dict]:
        """
        Finds stations within a specified radius (in kilometers) of a given latitude and longitude,
        using PostGIS ST_DWithin for efficient geospatial queries.
        """
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError("Invalid latitude or longitude.")
        if radius_km <= 0:
            raise ValueError("Radius must be a positive number.")

        # Create a PostGIS POINT object for the given coordinates
        # SRID 4326 is for WGS 84 (latitude/longitude)
        reference_point = ST_MakePoint(longitude, latitude).ST_SetSRID(4326)

        # Query stations within the specified radius (in meters)
        stations = self.db.query(Station).filter(
            func.ST_DWithin(
                Station.geom,
                reference_point,
                radius_km * 1000 # Convert km to meters
            )
        ).order_by(
            func.ST_Distance(Station.geom, reference_point) # Order by distance
        ).limit(limit).all()

        return [
            {
                "id": station.id,
                "name": station.name,
                "city": station.city,
                "latitude": station.latitude,
                "longitude": station.longitude,
                "distance_km": round(func.ST_Distance(station.geom, reference_point).cast(Float) / 1000, 2)
            }
            for station in stations
        ]
