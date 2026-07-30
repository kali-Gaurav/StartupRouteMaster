import logging
from typing import List, Optional

from guardian_ai.models import Mission, RiskLevel
from guardian_ai.behavior_analyzer import behavior_analyzer
from guardian_ai.mission_manager import mission_manager

logger = logging.getLogger("safety_engine")

class SafetyEngine:
    """
    Phase 3: Safety Intelligence Engine
    Combines mission context, location data, and behavioral analysis 
    to make escalation decisions.
    """

    async def process_user_message(self, user_id: str, message: str) -> Optional[Mission]:
        """
        Processes a user message, runs behavior analysis, and updates the mission.
        """
        mission = await mission_manager.get_current_mission(user_id)
        if not mission:
            logger.warning(f"Message received from user {user_id} but no active mission found.")
            return None

        # 1. Behavior Analysis
        analysis = await behavior_analyzer.analyze_text(message)
        
        # 2. Contextual Amplification
        # E.g. If the user is at a known dangerous station at night, amplify the risk.
        # This is where the True "Brain" logic lives.
        final_delta = analysis["risk_delta"]
        
        if analysis["detected"]:
            # Evaluate time context (Night amplifies risk)
            hour = mission.updated_at.hour
            if hour >= 22 or hour <= 4:
                logger.info(f"Night-time risk amplification applied to mission {mission.mission_id}")
                final_delta *= 1.5
                
            # Log the event
            mission = await mission_manager.log_safety_event(
                mission_id=mission.mission_id,
                category=analysis["category"],
                description=f"User Message: '{message}' | {analysis['description']}",
                risk_delta=final_delta
            )
            
        return mission

    async def evaluate_mission_state(self, mission: Mission) -> List[str]:
        """
        Evaluates the current state of a mission and determines if action is required.
        Returns a list of action directives.
        """
        actions = []
        
        if mission.risk_level == RiskLevel.CRITICAL:
            actions.append("TRIGGER_EMERGENCY_PROTOCOL")
            actions.append("ALERT_AUTHORITIES")
        elif mission.risk_level == RiskLevel.HIGH:
            actions.append("INITIATE_VOICE_CALL")
            actions.append("ALERT_EMERGENCY_CONTACTS")
        elif mission.risk_level == RiskLevel.MODERATE:
            actions.append("SEND_SAFETY_CHECKIN_SMS")
            
        return actions

safety_engine = SafetyEngine()
