from sqlalchemy.orm import Session
from typing import List, Dict
from geoalchemy2.functions import ST_MakePoint, ST_DWithin # Import PostGIS functions
from geoalchemy2.types import Geography # Import Geography type for explicit casting if needed
from sqlalchemy import func, text # Import func from sqlalchemy for generic functions, and text for raw SQL

from models import Station

class StationService:
    def __init__(self, db: Session):
        self.db = db

    def search_stations_by_name(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Searches for stations by name, returning the top matches using pg_trgm for fuzzy matching.
        """
        if not query or len(query) < 2:
            return []
            
        # Ensure 'pg_trgm' extension is enabled in your PostgreSQL database.
        # This is typically done via a migration or manually if you have superuser privileges.
        # For development, you might uncomment the line below to ensure it's created.
        # self.db.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;")) 
        
        # Use pg_trgm for fuzzy matching and order by similarity
        # A similarity threshold can be configured, e.g., 0.3
        similarity_threshold = 0.3 # You can adjust this value based on desired fuzziness

        stations = self.db.query(Station).filter(
            func.similarity(Station.name, query) > similarity_threshold
        ).order_by(
            func.similarity(Station.name, query).desc(), # Order by relevance
            Station.name # Secondary sort for consistent results
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
