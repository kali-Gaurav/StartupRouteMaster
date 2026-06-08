import logging
from typing import List
from guardian_ai.models import Mission

logger = logging.getLogger("action_executor")

class ActionExecutor:
    """
    Phase 4: Action Executor
    Converts AI decisions into real-world actions (e.g. notifications, alerts, SMS).
    """

    async def execute_directives(self, mission: Mission, directives: List[str]):
        """
        Takes a list of directives from the Safety Engine and executes them.
        """
        for directive in directives:
            logger.info(f"⚡ [ACTION] Executing Directive: {directive} for Mission {mission.mission_id}")
            
            if directive == "TRIGGER_EMERGENCY_PROTOCOL":
                await self._trigger_emergency_protocol(mission)
            elif directive == "ALERT_AUTHORITIES":
                await self._alert_authorities(mission)
            elif directive == "INITIATE_VOICE_CALL":
                await self._initiate_voice_call(mission)
            elif directive == "ALERT_EMERGENCY_CONTACTS":
                await self._alert_emergency_contacts(mission)
            elif directive == "SEND_SAFETY_CHECKIN_SMS":
                await self._send_checkin_sms(mission)
            else:
                logger.warning(f"Unknown directive: {directive}")

    async def _trigger_emergency_protocol(self, mission: Mission):
        # Stub for triggering system-wide lockdown/emergency UI on user device
        logger.critical(f"🚨 EMERGENCY PROTOCOL ACTIVATED FOR USER {mission.user_id}")

    async def _alert_authorities(self, mission: Mission):
        # Stub for API call to RPF / Police
        loc = mission.location
        logger.critical(f"👮 DISPATCHING AUTHORITIES TO {loc.lat}, {loc.lng} (Station: {loc.last_known_station})")

    async def _initiate_voice_call(self, mission: Mission):
        # Stub for Twilio Voice integration
        logger.warning(f"📞 Initiating automated voice check-in for user {mission.user_id}")

    async def _alert_emergency_contacts(self, mission: Mission):
        # Stub for Twilio SMS integration
        logger.warning(f"💬 SMS Sent to emergency contacts of user {mission.user_id}")

    async def _send_checkin_sms(self, mission: Mission):
        # Stub for push notification / WhatsApp message
        logger.info(f"📱 Sending gentle safety check-in prompt to user {mission.user_id}")

action_executor = ActionExecutor()
