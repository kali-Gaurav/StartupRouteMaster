import logging
from typing import Dict, Any
from services.agents.base_agent import BaseAgent, AgentPriority
from services.agents.cancellation_prediction_agent import cancellation_prediction_agent

logger = logging.getLogger("agent.overbooking")

class OverbookingAgent(BaseAgent):
    """
    [Phase 5] Predictive Overbooking Agent.
    Manages virtual seat inventory by allowing bookings beyond physical capacity
    based on predicted cancellation risk.
    """
    name = "OverbookingAgent"
    description = "Manages virtual seat capacity and overbooking limits."
    category = "allocation"
    priority = AgentPriority.HIGH
    icon = "🎫"
    color = "#8B5CF6" # Violet

    async def calculate_overbook_limit(self, train_id: str, physical_capacity: int, route_features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determines how many extra seats can be sold.
        """
        # 1. Get Cancellation Probability
        cancel_prob = await cancellation_prediction_agent.predict_probability(route_features)
        
        # 2. Define Risk Multiplier (Conservative for MVP)
        # We only overbook by 80% of the predicted cancellations to ensure safety
        risk_buffer = 0.8 
        
        expected_cancellations = int(physical_capacity * cancel_prob * risk_buffer)
        
        # 3. Apply Hard Caps
        # Never overbook by more than 15% of total capacity
        max_overbook = int(physical_capacity * 0.15)
        safe_overbook = min(expected_cancellations, max_overbook)
        
        total_virtual_capacity = physical_capacity + safe_overbook
        
        logger.info(f"🎫 [OVERBOOK] Train {train_id}: Cap {physical_capacity} -> Virtual {total_virtual_capacity} (+{safe_overbook})")
        
        return {
            "train_id": train_id,
            "physical_capacity": physical_capacity,
            "virtual_capacity": total_virtual_capacity,
            "overbook_count": safe_overbook,
            "risk_level": "LOW" if safe_overbook < (physical_capacity * 0.05) else "MEDIUM",
            "cancellation_probability": cancel_prob
        }

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Main execution entry point."""
        train_id = context.get("train_id", "MOCK_TRAIN")
        cap = context.get("physical_capacity", 100)
        res = await self.calculate_overbook_limit(train_id, cap, context)
        return {
            "status": "success",
            "summary": f"Virtual capacity set to {res['virtual_capacity']} (+{res['overbook_count']})",
            **res
        }

overbooking_agent = OverbookingAgent()
