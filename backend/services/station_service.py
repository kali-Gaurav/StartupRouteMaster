from sqlalchemy.orm import Session
from typing import List, Dict

from models import Station

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
