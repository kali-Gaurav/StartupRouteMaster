import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class ConferenceService:
    """
    Task 43: Emergency Conference Call Bridge (Mock).
    Manages high-priority audio bridges between victims and authorities.
    """
    def __init__(self):
        self.active_bridges: Dict[str, Dict[str, Any]] = {}

    async def create_bridge(self, event_id: str, participants: List[str]) -> str:
        bridge_id = f"CONF-{uuid.uuid4().hex[:8].upper()}"
        
        self.active_bridges[bridge_id] = {
            "event_id": event_id,
            "participants": participants,
            "status": "initiated",
            "started_at": datetime.utcnow().isoformat(),
            "logs": []
        }
        
        logger.info(f"📞 [BRIDGE] Created emergency conference {bridge_id} for {event_id}. Participants: {len(participants)}")
        return bridge_id

    async def add_participant(self, bridge_id: str, phone: str):
        if bridge_id in self.active_bridges:
            if phone not in self.active_bridges[bridge_id]["participants"]:
                self.active_bridges[bridge_id]["participants"].append(phone)
                self.active_bridges[bridge_id]["logs"].append(f"Joined: {phone} at {datetime.utcnow().isoformat()}")
                logger.info(f"📞 [BRIDGE] Participant {phone} joined bridge {bridge_id}")

    async def terminate_bridge(self, bridge_id: str):
        if bridge_id in self.active_bridges:
            self.active_bridges[bridge_id]["status"] = "terminated"
            self.active_bridges[bridge_id]["ended_at"] = datetime.utcnow().isoformat()
            logger.info(f"🛑 [BRIDGE] Bridge {bridge_id} terminated.")

conference_service = ConferenceService()
