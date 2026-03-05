import mmap
import struct
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class HotspotService:
    """
    Task 50: Historical 'Danger-Hotspot' Influence.
    Uses the binary Risk Index (Task 1) to identify historically dangerous segments.
    """
    def __init__(self, index_path: str = "backend/data/risk_index.bin"):
        self.index_path = index_path
        self.record_size = 9 # [f Lat][f Lng][B Risk]

    def check_historical_risk(self, lat: float, lng: float) -> int:
        """Returns historical risk level (0-255) for a location."""
        if not os.path.exists(self.index_path):
            return 0
            
        try:
            with open(self.index_path, "rb") as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    # O(N) scan for simplicity in this MVP, 
                    # in production would use Task 1's sweep-line O(log N)
                    num_records = len(mm) // self.record_size
                    for i in range(num_records):
                        offset = i * self.record_size
                        r_lat, r_lng, risk = struct.unpack("ffB", mm[offset:offset+9])
                        
                        # 5km proximity check (~0.05 degrees)
                        if abs(r_lat - lat) < 0.05 and abs(r_lng - lng) < 0.05:
                            if risk > 150: # Threshold for 'Hotspot'
                                logger.info(f"🔥 [HOTSPOT] Historical risk of {risk} detected at {r_lat}, {r_lng}")
                                return risk
        except Exception as e:
            logger.error(f"Failed to check historical hotspots: {e}")
            
        return 0

hotspot_service = HotspotService()
