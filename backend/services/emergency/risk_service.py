import math
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from database.session import SessionTransit
from sqlalchemy import text

logger = logging.getLogger(__name__)

class RiskService:
    def __init__(self):
        self.transit_db = SessionTransit()

    def _haversine(self, lat1, lon1, lat2, lon2):
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def check_area_risk(self, lat: float, lng: float) -> Dict[str, Any]:
        """
        Task 49: Predictive Danger Scoring.
        Checks if current coordinates are near historical high-risk zones.
        """
        if not lat or not lng:
            return {"risk_level": "low", "score": 0}
            
        try:
            query = text("SELECT id, latitude, longitude, risk_level, description FROM risk_zones")
            results = self.transit_db.execute(query).fetchall()
            
            max_risk_score = 1 # Baseline
            nearby_zones = []
            
            for row in results:
                zid, zlat, zlng, zlevel, desc = row
                dist = self._haversine(lat, lng, zlat, zlng)
                
                if dist <= 5.0: # 5km radius
                    score = 5 if zlevel == "high" else 3
                    if score > max_risk_score: max_risk_score = score
                    nearby_zones.append({"description": desc, "distance_km": round(dist, 2)})
            
            # Subtask 49.1: Night-Bias Escalation
            now = datetime.now()
            is_night = now.hour >= 23 or now.hour <= 4
            if is_night:
                max_risk_score *= 2
                logger.warning("🌙 [RISK] Night-bias escalation applied to risk score.")
            
            risk_label = "low"
            if max_risk_score >= 8: risk_label = "critical"
            elif max_risk_score >= 5: risk_label = "high"
            elif max_risk_score >= 3: risk_label = "medium"
            
            return {
                "risk_level": risk_label,
                "score": max_risk_score,
                "is_night_active": is_night,
                "nearby_risk_zones": nearby_zones,
                "suggest_guardian_mode": max_risk_score >= 5 # Subtask 49.2
            }
        except Exception as e:
            logger.error(f"Error checking risk zones: {e}")
            return {"risk_level": "unknown", "score": 0}
        finally:
            self.transit_db.close()

risk_service = RiskService()
