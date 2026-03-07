import math
import numpy as np
import requests
import logging
from datetime import datetime
from typing import Optional, Dict, Any

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

def is_tatkal_window() -> bool:
    """
    Subtask 13.1: Tatkal Window Detection.
    Returns True if current IST time is within the peak Tatkal windows.
    """
    try:
        import pytz
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        # AC Window: 10:00 AM - 10:30 AM
        if now.hour == 10 and 0 <= now.minute <= 30:
            return True
        
        # Non-AC Window: 11:00 AM - 11:30 AM
        if now.hour == 11 and 0 <= now.minute <= 30:
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
