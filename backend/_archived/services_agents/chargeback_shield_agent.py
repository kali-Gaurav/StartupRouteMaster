import logging
import json
from datetime import datetime
from typing import Dict, Any
from services.agents.base_agent import BaseAgent, AgentPriority

logger = logging.getLogger("agent.chargeback_shield")

class ChargebackShieldAgent(BaseAgent):
    """
    [G2.7.1] The 'Chargeback-Shield' Forensic Agent.
    Compiles immutable evidence packs for every transaction to
    defeat fraudulent chargebacks with banks.
    """
    name = "ChargebackShieldAgent"
    description = "Generates forensic evidence packs for financial dispute resolution."
    category = "finance"
    priority = AgentPriority.NORMAL
    icon = "🛡️"
    color = "#3B82F6" # Blue

    async def compile_evidence_pack(self, booking_id: str, user_id: str, request_meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        [Child G2.7.1.1] Forensic Data Gatherer.
        Aggregates all trust markers for a specific transaction.
        """
        evidence_pack = {
            "booking_id": booking_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "forensics": {
                 "ip_address": request_meta.get("ip"),
                 "user_agent": request_meta.get("user_agent"),
                 "fingerprint": request_meta.get("device_id"),
                 "geo_location": request_meta.get("location")
            },
            "intent_markers": {
                 "search_to_book_time_ms": request_meta.get("flow_duration"),
                 "previous_searches_count": request_meta.get("history_count", 0)
            },
            "status": "SEALED"
        }

        # [Child G2.7.1.2] Evidence Blob Signer
        # In production, we would sign this with a private key
        evidence_pack["signature"] = f"SIGN_{booking_id}_{user_id}"

        logger.info(f"📁 [SHIELD] Sealed Evidence Pack for Booking {booking_id}")
        
        # [Child G2.7.1.3] Save to DB (Skipped model creation for now, using log)
        return evidence_pack

chargeback_shield_agent = ChargebackShieldAgent()
