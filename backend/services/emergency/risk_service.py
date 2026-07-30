import math
import logging
import os
import mmap
import struct
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class RiskService:
    def __init__(self):
        self.index_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'risk_index.bin')
        self.top_danger_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'top_danger.bin')
        self.record_size = 9 # float32 + float32 + uint8
        self._mm = None
        self._mm_top = None
        self._f = None
        self._f_top = None
        self._last_mtime = 0
        self._last_mtime_top = 0

    def _haversine(self, lat1, lon1, lat2, lon2):
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def _load_indices(self):
        """Internal method to map/re-map both indices if changed."""
        try:
            # 1. Main Index
            if os.path.exists(self.index_path):
                current_mtime = os.path.getmtime(self.index_path)
                if current_mtime > self._last_mtime:
                    if self._mm: self._mm.close()
                    if self._f: self._f.close()
                    self._f = open(self.index_path, "rb")
                    self._mm = mmap.mmap(self._f.fileno(), 0, access=mmap.ACCESS_READ)
                    self._last_mtime = current_mtime
            
            # 2. Top-100 Fast Path Index (Task 8)
            if os.path.exists(self.top_danger_path):
                current_mtime_top = os.path.getmtime(self.top_danger_path)
                if current_mtime_top > self._last_mtime_top:
                    if self._mm_top: self._mm_top.close()
                    if self._f_top: self._f_top.close()
                    self._f_top = open(self.top_danger_path, "rb")
                    self._mm_top = mmap.mmap(self._f_top.fileno(), 0, access=mmap.ACCESS_READ)
                    self._last_mtime_top = current_mtime_top
                    
            return self._mm is not None
        except Exception as e:
            logger.error(f"Failed to load risk indices: {e}")
            return False

    def _finalize_risk(self, max_risk_score: int, nearby_zones: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Shared logic to format the risk response."""
        now = datetime.now()
        is_night = now.hour >= 23 or now.hour <= 4
        if is_night:
            max_risk_score *= 2
        
        risk_label = "low"
        if max_risk_score >= 8: risk_label = "critical"
        elif max_risk_score >= 5: risk_label = "high"
        elif max_risk_score >= 3: risk_label = "medium"
        
        return {
            "risk_level": risk_label,
            "score": max_risk_score,
            "is_night_active": is_night,
            "nearby_risk_zones": nearby_zones,
            "suggest_guardian_mode": max_risk_score >= 5
        }

    def _binary_search_lat(self, mm: mmap.mmap, target_lat: float, total_records: int) -> int:
        """Finds the first index where latitude >= target_lat"""
        low, high = 0, total_records - 1
        best = high
        while low <= high:
            mid = (low + high) // 2
            lat_val = struct.unpack('f', mm[mid * self.record_size : mid * self.record_size + 4])[0]
            if lat_val >= target_lat:
                best = mid
                high = mid - 1
            else:
                low = mid + 1
        return best

    def check_area_risk(self, lat: float, lng: float) -> Dict[str, Any]:
        if not lat or not lng: return {"risk_level": "low", "score": 0}
        if not self._load_indices(): return {"risk_level": "unknown", "score": 0}

        max_risk_score = 1
        nearby_zones = []
        
        # 1. Fastest Path (Top 100)
        if self._mm_top:
            total_top = len(self._mm_top) // self.record_size
            for i in range(total_top):
                offset = i * self.record_size
                zlat, zlng, zlevel = struct.unpack('ffB', self._mm_top[offset:offset+self.record_size])
                dist = self._haversine(lat, lng, zlat, zlng)
                if dist <= 5.0:
                    if zlevel > max_risk_score: max_risk_score = zlevel
                    nearby_zones.append({"description": "TOP_CRITICAL_ZONE", "distance_km": round(dist, 2)})
            if max_risk_score >= 5: return self._finalize_risk(max_risk_score, nearby_zones)

        # 2. Slow Path (Main Index)
        try:
            total_records = len(self._mm) // self.record_size
            lat_margin = 0.045
            start_idx = self._binary_search_lat(self._mm, lat - lat_margin, total_records)
            for i in range(start_idx, total_records):
                zlat, zlng, zlevel = struct.unpack('ffB', self._mm[i*self.record_size : (i+1)*self.record_size])
                if zlat > lat + lat_margin: break
                dist = self._haversine(lat, lng, zlat, zlng)
                if dist <= 5.0:
                    if zlevel > max_risk_score: max_risk_score = zlevel
                    nearby_zones.append({"distance_km": round(dist, 2)})
            
            return self._finalize_risk(max_risk_score, nearby_zones)
        except Exception as e:
            logger.error(f"Error checking binary risk zones: {e}")
            return {"risk_level": "unknown", "score": 0}

risk_service = RiskService()
