from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
import logging
from datetime import datetime, time
from services.agents.base_agent import BaseAgent, AgentPriority
from core.data_structures import Route, Persona

logger = logging.getLogger("agent.guardian")

class GuardianAgent(BaseAgent):
    """
    [Point 22] Safety & Experience Orchestrator.
    Responsible for 'Persona-Safe' routing, nighttime hub evaluation, 
    and proactive passenger safety guarantees.
    """
    name = "GuardianAgent"
    description = "Enforces persona-based safety constraints and proactive passenger protection."
    category = "safety"
    priority = AgentPriority.CRITICAL
    icon = "🛡️"
    color = "#10B981" # Emerald Green
    version = "1.2.0"

    def __init__(self):
        super().__init__()
        # Safety Data (In a real system, these would be in DB/GIS)
        self.station_infrastructure = {
            "NDLS": {"safety_score": 0.95, "amenities": ["Retiring Room", "Lounge", "24/7 Police"]},
            "BOM": {"safety_score": 0.98, "amenities": ["Lounge", "Hotel", "Safe Zone"]},
            "ALD": {"safety_score": 0.75, "amenities": ["Retiring Room"]},
            "GZB": {"safety_score": 0.60, "amenities": ["Waiting Room"]},
            "BE": {"safety_score": 0.50, "amenities": []} # Remote hub
        }

    async def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Input: List of routes, persona context.
        Output: Augmented routes with safety scores and warnings.
        """
        routes = context.get("routes", [])
        persona = context.get("persona", Persona.ECONOMY)
        
        if not routes:
            return {"status": "success", "summary": "No routes to evaluate.", "routes": []}

        scored_routes = []
        for route in routes:
            safety_analysis = await self._analyze_route_safety(route, persona)
            route.metadata["safety_analysis"] = safety_analysis
            route.safety_score = safety_analysis["total_score"]
            
            # Proactive "Safe-Haven" suggestion
            if safety_analysis.get("requires_safe_haven"):
                route.metadata["ui_reasons"].append("Safe-Haven Suggestion Available 🏨")
                route.metadata["guardian_note"] = "Transfer at remote station at night. Recommend IRCTC Retiring Room."
            
            scored_routes.append(route)

        return {
            "status": "success",
            "summary": f"Evaluated safety for {len(routes)} routes for persona {persona}.",
            "routes": scored_routes
        }

    async def _analyze_route_safety(self, route: Any, persona: Persona) -> Dict[str, Any]:
        """
        Deep safety analysis based on persona norms.
        """
        total_score = 1.0
        warnings = []
        requires_safe_haven = False
        station_info = {"safety_score": 0.6}
        
        # Check Hub Transfers
        for transfer in getattr(route, 'transfers', []):
            hub_code = transfer.station_name
            arrival_at_hub = transfer.arrival_time
            wait_time = transfer.duration_minutes
            
            # 1. Night-Time Penalty (11 PM - 5 AM)
            is_night = 23 <= arrival_at_hub.hour or arrival_at_hub.hour <= 5
            
            # 2. Infrastructure lookup
            station_info = self.station_infrastructure.get(transfer.station_name, {"safety_score": 0.6})
            base_score = station_info["safety_score"]
            
            if is_night:
                total_score *= 0.7 # 30% penalty for night arrivals
                if base_score < 0.7: # Poorly lit/remote station at night
                    total_score *= 0.5 # Massive 50% penalty
                    warnings.append(f"Remote station {hub_code} at night ⚠️")
                    
                    if persona in [Persona.FAMILY, Persona.ECONOMY]: # Use Family/Economy as safe-haven sensitive personas
                         requires_safe_haven = True
            
            # 3. Transfer Buffer check
            if is_night and wait_time > 180: # > 3 hours at night
                 requires_safe_haven = True
                 warnings.append("Long nighttime hub wait. Security risk.")

        # Deduct score for warnings
        total_score -= (len(warnings) * 0.1)
        total_score = max(0.1, total_score)

        return {
            "total_score": round(total_score, 2),
            "warnings": warnings,
            "requires_safe_haven": requires_safe_haven,
            "station_data": station_info
        }

    async def monitor_fraud_clusters(self, db: Session):
        """
        [Task 45.10] Financial Protection: Monitors for systemic 'Fraud Clusters'.
        If one device/IP generates multiple alerts, the Guardian locks the platform.
        """
        from database.models import FraudAlert
        from datetime import timedelta
        
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        
        # Aggregate alerts by metadata (Fingerprint or IP)
        recent_alerts = db.query(FraudAlert).filter(
            FraudAlert.created_at >= one_hour_ago,
            FraudAlert.status == "OPEN"
        ).all()
        
        clusters = {}
        for alert in recent_alerts:
            ident = alert.metadata_json.get("fingerprint") or alert.metadata_json.get("ip")
            if ident:
                clusters[ident] = clusters.get(ident, 0) + 1
                
        for ident, count in clusters.items():
            if count >= 5:
                logger.critical(f"🛡️ [GUARDIAN] FRAUD CLUSTER DETECTED: {ident} | Hits: {count}")
                await self.emergency_lockdown(ident, f"Consolidated Fraud Cluster ({count} alerts in 60m)")

    async def emergency_lockdown(self, identifier: str, reason: str):
        """
        [Task 4.5] Triggers a global Financial Lock AND a Network Block.
        Final Step: Blackhole the malicious source via the Traffic Guardian.
        """
        from services.cache_service import cache_service
        from services.emergency.firewall_service import firewall_guardian
        
        logger.critical(f"🛑 [GUARDIAN] EMERGENCY LOCKDOWN TRIGGERED: {reason} | Source: {identifier}")
        
        # 1. Platform-wide Financial Halt
        cache_service.set("PLATFORM_FINANCIAL_LOCK", "TRUE", ttl_seconds=3600)
        
        # 2. Network-Layer Blackhole (Traffic Guardian)
        firewall_guardian.issue_block(identifier, reason, duration=86400) # 24-hour block for fraud clusters
        
        # 3. Broadcast Alert
        from services.ws_manager import ws_manager
        await ws_manager.broadcast_global(f"🚨 EMERGENCY: Financial Lockdown Active due to Fraud Cluster from {identifier[:8]}...", "CRITICAL_ALERT")
