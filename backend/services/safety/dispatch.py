import logging
import uuid
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from core.infrastructure.redis_manager import async_redis_client
from services.sathi_location_service import SathiLocationService

logger = logging.getLogger("nexus.dispatch")

class SafetyDispatchManager:
    """
    [RM-P3-002] Automated Responder Dispatch Engine.
    Orchestrates the lifecycle of an SOS incident and responder assignment.
    """
    INCIDENT_KEY_PREFIX = "incident:"
    ACTIVE_INCIDENTS_SET = "active_incidents"

    @staticmethod
    async def create_incident(user_id: str, lat: float, lon: float, incident_type: str = "SOS") -> Dict[str, Any]:
        """
        Register a new safety incident and trigger initial dispatch logic.
        """
        from services.safety_audit_service import SafetyAuditService
        
        incident_id = f"inc_{uuid.uuid4().hex[:8]}"
        incident_data = {
            "id": incident_id,
            "user_id": user_id,
            "type": incident_type,
            "lat": lat,
            "lon": lon,
            "status": "triggered",
            "created_at": datetime.utcnow().isoformat(),
            "responders": []
        }

        # 1. Audit Entry
        await SafetyAuditService.log_event("INCIDENT_TRIGGERED", incident_data, user_id)

        # 2. Store incident
        await async_redis_client.setex(
            f"{SafetyDispatchManager.INCIDENT_KEY_PREFIX}{incident_id}",
            3600, # 1 hour TTL
            json.dumps(incident_data)
        )
        await async_redis_client.sadd(SafetyDispatchManager.ACTIVE_INCIDENTS_SET, incident_id)

        # 3. Find Candidate Responders
        candidates = await SafetyDispatchManager._find_responders(lat, lon, incident_type)
        
        # 4. Trigger initial alerts (Simulated Push)
        for sathi in candidates:
            await SafetyDispatchManager._notify_sathi(sathi["id"], incident_id)

        logger.info(f"🚨 Incident {incident_id} created. Alerts sent to {len(candidates)} Sathis.")
        return incident_data

    @staticmethod
    async def _find_responders(lat: float, lon: float, incident_type: str) -> List[Dict[str, Any]]:
        """
        Find best matching Sathis within a 5km radius.
        """
        nearby = await SathiLocationService.get_nearby_sathis(lat, lon, radius_km=5.0)
        
        # Filter for availability and specialization if needed
        available = [s for s in nearby if s["status"] == "available"]
        
        # Sort by distance (nearby already returns sorted by distance if using geosearch)
        return available[:5] # Notify top 5 nearest

    @staticmethod
    async def _notify_sathi(sathi_id: str, incident_id: str):
        """
        Dispatch a push notification to a specific Sathi.
        [RM-P3-001] FCM Integration
        """
        from core.integration.fcm import FCMService
        
        # In production, we fetch the Sathi's FCM token from the database
        # For now, we use sathi_id as a mock token
        token = f"token_{sathi_id}"
        
        await FCMService.send_notification(
            token=token,
            title="🚨 EMERGENCY DISPATCH",
            body="Safety assistance requested nearby. Tap to respond.",
            data={
                "type": "SAFETY_DISPATCH",
                "incident_id": incident_id,
                "click_action": "FLUTTER_NOTIFICATION_CLICK"
            }
        )
        
        # Legacy backup channel
        await async_redis_client.publish(f"sathi_notifications:{sathi_id}", json.dumps({
            "type": "SAFETY_DISPATCH",
            "incident_id": incident_id
        }))

    @staticmethod
    async def accept_dispatch(incident_id: str, sathi_id: str) -> bool:
        """
        Handle a Sathi accepting an assignment.
        """
        key = f"{SafetyDispatchManager.INCIDENT_KEY_PREFIX}{incident_id}"
        incident_raw = await async_redis_client.get(key)
        if not incident_raw: return False

        incident = json.loads(incident_raw)
        if incident["status"] == "resolved": return False

        # Add responder and update status
        if sathi_id not in incident["responders"]:
            incident["responders"].append(sathi_id)
            incident["status"] = "active"
            
            await async_redis_client.set(key, json.dumps(incident))
            
            # Audit Entry
            from services.safety_audit_service import SafetyAuditService
            await SafetyAuditService.log_event("DISPATCH_ACCEPTED", {"incident_id": incident_id}, sathi_id)
            
            logger.info(f"✅ Sathi {sathi_id} accepted Incident {incident_id}")
            return True
            
        return False

    @staticmethod
    async def resolve_incident(incident_id: str):
        """
        [RM-X-101] Resolve an incident and reward responders.
        """
        from services.honor_service import SathiHonorService
        
        key = f"{SafetyDispatchManager.INCIDENT_KEY_PREFIX}{incident_id}"
        incident_raw = await async_redis_client.get(key)
        if not incident_raw: return

        incident = json.loads(incident_raw)
        incident["status"] = "resolved"
        incident["resolved_at"] = datetime.utcnow().isoformat()
        
        # 1. Update Incident Status
        await async_redis_client.set(key, json.dumps(incident))
        await async_redis_client.srem(SafetyDispatchManager.ACTIVE_INCIDENTS_SET, incident_id)

        # 2. Audit Entry
        from services.safety_audit_service import SafetyAuditService
        await SafetyAuditService.log_event("INCIDENT_RESOLVED", incident, "SYSTEM")

        # 3. Reward Responders
        for sathi_id in incident["responders"]:
            await SathiHonorService.award_credits(
                sathi_id=sathi_id, 
                amount=50, 
                reason=f"Resolved Incident {incident_id}"
            )

        logger.info(f"🏁 Incident {incident_id} resolved. Responders rewarded.")
