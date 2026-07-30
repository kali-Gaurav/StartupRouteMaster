import math
import logging
import os
import mmap
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class ConnectivityService:
    def __init__(self):
        self.bitmap_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'deadzones.bmp')
        
        # Must match builder exactly
        self.MIN_LAT = 8.0
        self.MAX_LAT = 38.0
        self.MIN_LNG = 68.0
        self.MAX_LNG = 98.0
        self.GRID_SIZE_LAT = int((self.MAX_LAT - self.MIN_LAT) * 111)
        self.GRID_SIZE_LNG = int((self.MAX_LNG - self.MIN_LNG) * 111)

    def check_upcoming_dead_zones(self, lat: float, lng: float, radius_km: float = 10.0) -> List[Dict[str, Any]]:
        """
        Task 2: Identify if the passenger is in/approaching a known signal dead zone using O(1) bitmasks.
        """
        if not lat or not lng: return []
        if not (self.MIN_LAT <= lat <= self.MAX_LAT and self.MIN_LNG <= lng <= self.MAX_LNG):
            return [] # Outside India bounding box

        try:
            if not os.path.exists(self.bitmap_path):
                logger.warning("Dead-zone bitmap not found.")
                return []

            with open(self.bitmap_path, "rb") as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    
                    # Convert lat/lng to grid cell
                    lat_idx = int((lat - self.MIN_LAT) * 111)
                    lng_idx = int((lng - self.MIN_LNG) * 111)
                    
                    # Check immediate vicinity (3x3 grid = ~3km)
                    for d_lat in range(-3, 4):
                        for d_lng in range(-3, 4):
                            y = lat_idx + d_lat
                            x = lng_idx + d_lng
                            
                            if 0 <= y < self.GRID_SIZE_LAT and 0 <= x < self.GRID_SIZE_LNG:
                                cell_idx = y * self.GRID_SIZE_LNG + x
                                byte_idx = cell_idx // 8
                                bit_offset = cell_idx % 8
                                
                                # O(1) Bitwise AND
                                if mm[byte_idx] & (1 << bit_offset):
                                    # Found a dead zone!
                                    return [{
                                        "id": "mapped-zone",
                                        "distance_km": round(math.sqrt(d_lat**2 + d_lng**2), 2),
                                        "expected_duration_mins": 10, # Generic fallback
                                        "description": "Known Signal Dead-Zone Grid",
                                        "is_imminent": True
                                    }]
            return []
        except Exception as e:
            logger.error(f"Error checking dead zone bitmap: {e}")
            return []

connectivity_service = ConnectivityService()
