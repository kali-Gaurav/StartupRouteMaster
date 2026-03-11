import requests
import logging
import time
import math
from typing import Optional, Dict, Any, List
from math import radians, cos, sin, acos

logger = logging.getLogger("data-enrichment-provider")

class EnrichmentProvider:
    """
    Interfaces with external APIs (OSM Nominatim, Overpass) 
    to fetch missing coordinates, cities, and station details.
    """
    
    NOMINATIM_URL = "https://nominatim.openstreetmap.org"
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"
    USER_AGENT = "RouteMaster-Enrichment-Engine/1.0"

    @classmethod
    def get_coordinates(cls, station_name: str, city: Optional[str] = None) -> Optional[Dict[str, float]]:
        """Fetch lat/lon for a station using Nominatim."""
        query = f"{station_name} railway station"
        if city:
            query += f" {city}"
        query += " India"

        params = {
            "q": query,
            "format": "json",
            "limit": 1
        }
        
        try:
            # Respect OSM usage policy (1 request per second)
            time.sleep(1.1) 
            r = requests.get(f"{cls.NOMINATIM_URL}/search", params=params, headers={"User-Agent": cls.USER_AGENT})
            r.raise_for_status()
            data = r.json()
            
            if data:
                return {
                    "lat": float(data[0]["lat"]),
                    "lon": float(data[0]["lon"]),
                    "display_name": data[0].get("display_name")
                }
        except Exception as e:
            logger.error(f"Nominatim lookup failed for {query}: {e}")
        
        return None

    @classmethod
    def reverse_geocode(cls, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Fetch city/address details from coordinates."""
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json"
        }
        
        try:
            time.sleep(1.1)
            r = requests.get(f"{cls.NOMINATIM_URL}/reverse", params=params, headers={"User-Agent": cls.USER_AGENT})
            r.raise_for_status()
            data = r.json()
            
            if data and "address" in data:
                address = data["address"]
                # Try to find city in different possible OSM tags
                city = address.get("city") or address.get("town") or address.get("village") or address.get("district")
                state = address.get("state")
                return {
                    "city": city,
                    "state": state,
                    "full_address": data.get("display_name")
                }
        except Exception as e:
            logger.error(f"Reverse geocoding failed for {lat},{lon}: {e}")
            
        return None

    @classmethod
    def haversine_distance(cls, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in km."""
        if not all([lat1, lon1, lat2, lon2]): return 0.0
        try:
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            # Law of cosines for better performance than full Haversine on modern CPUs
            dist = 6371 * acos(
                min(1.0, cos(lat1) * cos(lat2) * cos(lon2 - lon1) + sin(lat1) * sin(lat2))
            )
            return round(dist, 2)
        except Exception:
            return 0.0

    @classmethod
    def get_station_facilities(cls, lat: float, lon: float) -> Dict[str, Any]:
        """Fetch station facilities using Overpass API."""
        # Search in 500m radius
        query = f"""
        [out:json];
        node["railway"="station"](around:500,{lat},{lon});
        out body;
        """
        try:
            r = requests.post(cls.OVERPASS_URL, data={"data": query}, headers={"User-Agent": cls.USER_AGENT})
            r.raise_for_status()
            data = r.json()
            
            if data and "elements" in data and len(data["elements"]) > 0:
                tags = data["elements"][0].get("tags", {})
                return {
                    "wheelchair": tags.get("wheelchair"),
                    "platforms": tags.get("platforms"),
                    "operator": tags.get("operator"),
                    "amenities": [k for k in tags.keys() if k.startswith("amenity")]
                }
        except Exception as e:
            logger.error(f"Overpass facility fetch failed: {e}")
            
        return {}
