import math
import numpy as np
import requests
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    r = 6371 # Radius of earth in kilometers
    return c * r

def haversine_vectorized(lat1, lon1, lat2, lon2):
    """
    Vectorized Haversine distance using numpy.
    Supports scalars and arrays.
    """
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return c * 6371

class StationGeoIndex:
    """
    [7.2] High-speed Station Geo Index.
    Caches all stations in memory as NumPy arrays for sub-ms proximity scanning.
    """
    def __init__(self):
        self.station_codes = []
        self.coords = np.empty((0, 2))
        self.is_initialized = False

    def initialize(self, db):
        """[7.2] Load from SQLite to NumPy."""
        from sqlalchemy import text
        rows = db.execute(text("SELECT code, latitude, longitude FROM stops WHERE latitude IS NOT NULL")).fetchall()
        
        self.station_codes = [r[0] for r in rows]
        self.coords = np.array([[r[1], r[2]] for r in rows], dtype=np.float32)
        self.is_initialized = True
        logger.info(f"StationGeoIndex initialized with {len(self.station_codes)} stations.")

    def find_nearby_stations(self, lat: float, lon: float, radius_km: float = 50.0) -> List[Dict]:
        """
        [7.3] Sub-ms Proximity Search using Vectorized NumPy scanning.
        """
        if not self.is_initialized: return []
        
        # Calculate distances to ALL stations at once
        dists = haversine_vectorized(lat, lon, self.coords[:, 0], self.coords[:, 1])
        
        # Mask by radius
        mask = dists <= radius_km
        indices = np.where(mask)[0]
        
        results = []
        for idx in indices:
            results.append({
                "code": self.station_codes[idx],
                "distance": float(dists[idx])
            })
        
        # Sort by distance
        results.sort(key=lambda x: x["distance"])
        return results

# Singleton instance
station_geo_index = StationGeoIndex()

def is_tatkal_window() -> bool:
    """
    [27.2] Checks if current time is within IRCTC Tatkal booking window (IST).
    Broader window (10 AM to 1 PM) to account for payment delays and processing.
    """
    try:
        import pytz
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        if 10 <= now.hour <= 12:
            return True
    except: pass
    return False

def get_location_from_ip(ip_address: str) -> Dict[str, Any]:
    """
    Mock/Stub for IP-based geolocation.
    """
    if not ip_address or ip_address == "127.0.0.1":
        return {
            "lat": 28.6139,
            "lng": 77.2090,
            "city": "Delhi",
            "state": "Delhi",
            "country": "India"
        }
    try:
        res = requests.get(f"https://ipapi.co/{ip_address}/json/", timeout=2)
        data = res.json()
        return {
            "lat": data.get("latitude"),
            "lng": data.get("longitude"),
            "city": data.get("city"),
            "state": data.get("region"),
            "country": data.get("country_name")
        }
    except:
        return {"state": "Unknown"}

def get_state_from_ip(ip_address: str) -> str:
    """Returns the state name for a given IP."""
    loc = get_location_from_ip(ip_address)
    return loc.get("state", "Unknown")
