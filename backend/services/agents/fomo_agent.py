import logging
import random
from typing import Dict, Any, List
from services.agents.base_agent import BaseAgent, AgentPriority
from services.multi_layer_cache import multi_layer_cache

logger = logging.getLogger("agent.fomo")

class FOMOAgent(BaseAgent):
    """
    [G3.6.1] The 'FOMO' (Fear Of Missing Out) Engine.
    Converts 'Browsers' to 'Bookers' by highlighting inventory scarcity
    and real-time social interest.
    """
    name = "FOMOAgent"
    description = "Drives conversion via scarcity signals and real-time social proof."
    category = "growth"
    priority = AgentPriority.NORMAL
    icon = "🔥"
    color = "#F43F5E" # Rose

    async def get_conversion_signals(self, route_id: str, current_availability: int) -> Dict[str, Any]:
        """
        [Child G3.6.1.1 & G3.6.1.2]
        Calculates FOMO signals for a specific route.
        """
        signals = []
        
        # 1. Scarcity Monitor (Child G3.6.1.1)
        if current_availability > 0 and current_availability <= 5:
            signals.append({
                "type": "SCARCITY",
                "message": f"Only {current_availability} seats left at this price!",
                "level": "CRITICAL"
            })
        
        # 2. Social Interest Tracker (Child G3.6.1.2)
        # Uses Redis to track how many people searched this route in the last 10 mins
        interest_count = await self._get_realtime_interest(route_id)
        if interest_count > 3:
            signals.append({
                "type": "SOCIAL_PROOF",
                "message": f"{interest_count} others are viewing this trip right now.",
                "level": "HIGH"
            })

        return {
            "route_id": route_id,
            "has_high_fomo": len(signals) > 0,
            "signals": signals,
            "interest_score": min(1.0, interest_count / 20.0)
        }

    async def _get_realtime_interest(self, route_id: str) -> int:
        """Fetches live intent from Redis."""
        if not multi_layer_cache.redis:
            return random.randint(1, 5) # Mock for local dev
            
        key = f"intent:route:{route_id}"
        # Increment and get
        count = await multi_layer_cache.redis.incr(key)
        await multi_layer_cache.redis.expire(key, 600) # 10 minute window
        return count

fomo_agent = FOMOAgent()
