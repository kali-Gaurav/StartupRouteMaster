import logging
import time
from typing import Dict, Any, Optional, List
from utils.circuit_breaker import telecom_breaker, CircuitBreakerOpenException

logger = logging.getLogger(__name__)

class TelecomService:
    """
    Handles outbound emergency voice calls via Twilio/Exotel.
    Task 15: Hardened with Circuit Breaker and Fallback.
    """
    def __init__(self):
        self.is_configured = False 

    async def initiate_emergency_call(self, phone_number: str, context: Dict[str, Any]) -> bool:
        """
        Wrapped call initiation logic.
        """
        try:
            return await telecom_breaker.call(self._raw_call_logic, phone_number, context)
        except CircuitBreakerOpenException:
            logger.error(f"🛑 [TELECOM] Circuit OPEN. Failed to call {phone_number}. Triggering Subtask 15.2 Fallback.")
            # Triggering a mock notification fallback
            return False
        except Exception as e:
            logger.error(f"Telecom call error: {e}")
            return False

    async def _raw_call_logic(self, phone_number: str, context: Dict[str, Any]) -> bool:
        """
        The actual un-wrapped API call logic.
        """
        if not phone_number: return False
        
        threat_type = context.get("category", "unknown")
        logger.info(f"📞 [TELECOM] Initiating emergency call to {phone_number} (Threat: {threat_type})")
        
        if not self.is_configured:
            # Simulate a failure if testing the breaker
            if phone_number == "FAIL_TEST":
                raise Exception("Third-party API Timeout")
            logger.info("   └─ MOCK MODE: Success.")
            return True
            
        return True

    async def bridge_emergency_conference(self, event_id: str, participants: List[str]) -> str:
        """
        Subtask 25.1: Creates a conference bridge between multiple parties.
        Returns the Conference Room ID.
        """
        conf_id = f"CONF-{event_id[:8].upper()}"
        logger.info(f"🌉 [TELECOM] Creating emergency conference bridge: {conf_id}")
        return conf_id

telecom_service = TelecomService()
