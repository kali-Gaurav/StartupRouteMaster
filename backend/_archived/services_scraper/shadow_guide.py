"""
Shadow-Guide Agent: The Voice of Sovereign Intelligence
======================================================
Patent Innovation #3: Agentic guidance for the redistribution of demand.

The Shadow-Guide is not just a chatbot; it is a personalized transit concierge
that explains the "Sovereign Logic" to the user in natural language.

It takes complex EDR decisions (nudges, incentives, pressure) and transforms
them into persuasive, empathetic guidance.
"""

import logging
import random
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from core.sovereign.edr_algorithm import EDRDecision, EDRNudge, NudgeType
from core.sovereign.network_pressure import PressureLevel

logger = logging.getLogger("sovereign.shadow_guide")

@dataclass
class GuideResponse:
    """A natural language guidance package."""
    message: str
    tone: str
    action_item: Optional[str] = None
    safety_tip: Optional[str] = None
    food_recommendation: Optional[str] = None

class ShadowGuideAgent:
    """
    Sovereign AI Agent that personalizes the EDR redistribution experience.
    """

    TONES = ["EMPATHETIC", "EFFICIENT", "PROTECTIVE", "ADVENTUROUS"]

    def __init__(self):
        self.name = "RouteMaster Guide"
        logger.info("[SHADOW_GUIDE] Shadow-Guide Agent initialized")

    async def generate_guidance(
        self, 
        edr_decision: EDRDecision, 
        user_context: Dict[str, Any]
    ) -> GuideResponse:
        """
        Synthesizes EDR nudges into a conversational guide response.
        """
        pressure = edr_decision.corridor_pressure
        level = edr_decision.pressure_level
        nudges = edr_decision.nudges
        
        # Determine the narrative based on network state
        if level in [PressureLevel.HIGH, PressureLevel.CRITICAL, PressureLevel.OVERFLOW]:
            return await self._generate_congestion_guidance(edr_decision, user_context)
        elif nudges:
            return await self._generate_value_guidance(edr_decision, user_context)
        else:
            return await self._generate_standard_guidance(edr_decision, user_context)

    async def _generate_congestion_guidance(
        self, 
        decision: EDRDecision, 
        context: Dict[str, Any]
    ) -> GuideResponse:
        """Guidance when the network is under stress."""
        source = decision.source
        dest = decision.destination
        
        # Find the best nudge
        best_nudge = self._select_best_nudge(decision.nudges)
        
        if best_nudge:
            message = (
                f"I've analyzed the {source} to {dest} corridor and it's currently at "
                f"{int(decision.corridor_pressure * 100)}% capacity. To ensure you have a "
                f"comfortable journey, I've secured a special offer: {best_nudge.headline}. "
                f"{best_nudge.description} Shall I reserve this for you?"
            )
        else:
            message = (
                f"The route to {dest} is looking quite crowded today. I'm monitoring "
                "alternative connections through nearby hubs to find you a guaranteed seat. "
                "Stay tuned."
            )

        return GuideResponse(
            message=message,
            tone="PROTECTIVE",
            safety_tip="Keep your RouteMaster SOS active in crowded stations.",
            food_recommendation=self._get_food_tip(source)
        )

    async def _generate_value_guidance(
        self, 
        decision: EDRDecision, 
        context: Dict[str, Any]
    ) -> GuideResponse:
        """Guidance focused on incentives and benefits."""
        best_nudge = self._select_best_nudge(decision.nudges)
        if best_nudge:
            message = (
                f"Great news! I've found a 'Smart Route' that helps us balance the network. "
                f"If you choose {best_nudge.target_route_id}, I can credit Rs {int(best_nudge.incentive_value)} "
                "to your RouteMaster wallet immediately. It's a win-win!"
            )
        else:
            message = (
                "Great news! I've found a 'Smart Route' that helps us balance the network. "
                "If you choose the suggested route, I can credit an incentive to your RouteMaster wallet immediately. It's a win-win!"
            )
        return GuideResponse(
            message=message,
            tone="EFFICIENT",
            action_item="CLAIM_INCENTIVE",
            food_recommendation="Pre-order a 'Sovereign Meal Box' for this route."
        )

    async def _generate_standard_guidance(
        self, 
        decision: EDRDecision, 
        context: Dict[str, Any]
    ) -> GuideResponse:
        """Default guidance for normal network conditions."""
        return GuideResponse(
            message=(
                f"Welcome! The corridor to {decision.destination} is flowing smoothly. "
                "I've ranked the best options for you based on comfort and on-time performance."
            ),
            tone="EMPATHETIC",
            safety_tip="Always check your platform number in the RouteMaster app 15 mins before departure."
        )

    def _select_best_nudge(self, nudges: List[EDRNudge]) -> Optional[EDRNudge]:
        """Rank nudges by system benefit and incentive value."""
        if not nudges:
            return None
        return max(nudges, key=lambda n: n.system_benefit + (n.incentive_value / 1000))

    def _get_food_tip(self, station: str) -> str:
        """Contextual food tips based on station."""
        tips = {
            "NDLS": "The Bedmi Poori near Platform 1 is a classic, but I recommend pre-ordering via our app for hygiene.",
            "BCT": "Vada Pav is great, but try the 'Sovereign Health Platter' available at our partner lounge.",
            "MAS": "Try the Ghee Podi Idli from our verified vendors for a light travel meal.",
            "HWH": "Kolkata Biryani is famous, but ensure it's from a 'Sovereign-Certified' kitchen today."
        }
        return tips.get(station, "Check our food partner ratings before ordering.")

# Singleton
shadow_guide = ShadowGuideAgent()
