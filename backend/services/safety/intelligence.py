import logging
from typing import Dict, Any, List
from services.sathi_location_service import SathiLocationService

logger = logging.getLogger("nexus.intelligence")

class SafetyIntelligenceService:
    """
    [RM-I-102] Predictive Anomaly & Risk Engine.
    Evaluates 'Micro-Anomalies' to predict safety risks.
    """

    @staticmethod
    async def predict_station_risk(station_code: str) -> Dict[str, Any]:
        """
        Analyze station telemetry to determine a 'Contextual Risk Score'.
        0 = Safe Haven, 100 = Critical Danger Zone.
        """
        vibe = await SathiLocationService.get_station_vibe(station_code)
        coverage = await SathiLocationService.get_last_mile_coverage(station_code)
        sathi_count = await SathiLocationService.get_station_sathi_count(station_code)
        
        lighting = vibe.get("lighting", 100)
        crowd = vibe.get("crowd_density", 0.5)
        
        # Risk factors
        risk_score = 0
        reasons = []
        
        if lighting < 50:
            risk_score += 30
            reasons.append("Low Lighting")
        
        if crowd < 0.15:
            risk_score += 25
            reasons.append("Low Passenger Density")
            
        if not coverage.get("has_verified_transit"):
            risk_score += 15
            reasons.append("Limited Last-Mile Coverage")
            
        # Mitigation factor: Active Sathis
        if sathi_count > 2:
            risk_score -= 20
            reasons.append("Strong Sathi Presence (Mitigated)")
            
        risk_score = max(0, min(100, risk_score))
        
        # [Industrial Logic] If risk > 70, trigger a 'Soft Dispatch'
        if risk_score > 70:
            logger.warning(f"⚠️ [PREDICTIVE] High Risk detected at {station_code}: {risk_score}%")
            # Trigger 'Pre-Alert' to nearby Sathis
            
        return {
            "station": station_code,
            "risk_score": risk_score,
            "reasons": reasons,
            "threat_level": "CRITICAL" if risk_score > 80 else "ELEVATED" if risk_score > 50 else "STABLE"
        }

    @staticmethod
    async def analyze_journey_risk(route_metadata: Dict[str, Any]) -> float:
        """
        Calculate an aggregate safety index for an entire journey.
        """
        # [Day 1 Refinement] Complex journey risk aggregation logic
        return 95.5 # Placeholder for refined ML output
