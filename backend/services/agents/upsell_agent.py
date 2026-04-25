import logging
from typing import List, Dict, Any
from services.agents.base_agent import BaseAgent, AgentPriority

logger = logging.getLogger("agent.upsell")

class AdaptiveUpsellAgent(BaseAgent):
    """
    [G1.9.1] The 'Friction to Value' Upsell Agent.
    Identifies stress points in travel routes (long waits, late arrivals)
    and offers targeted addons (Lounge, Porter, Taxi).
    """
    name = "AdaptiveUpsellAgent"
    description = "Converts travel friction into revenue by suggesting targeted addon services."
    category = "growth"
    priority = AgentPriority.LOW
    icon = "🎁"
    color = "#8B5CF6" # Violet

    async def get_route_addons(self, route_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        [Child G1.9.1.1 & G1.9.1.2]
        Analyzes route for friction and matches appropriate addons.
        """
        addons = []
        
        # 1. Friction Detection: Long Layover (Child G1.9.1.1)
        transfers = route_data.get("transfers") or []
        for t in transfers:
            duration = t.get("duration_minutes", 0)
            if duration > 120:
                addons.append({
                    "id": "STATION_LOUNGE",
                    "title": "Station Executive Lounge",
                    "reason": f"{duration} min wait? Wait in comfort with AC, Wi-Fi & Food.",
                    "price": 249,
                    "target_station": t.get("station_code")
                })
        
        # 2. Friction Detection: Night Arrival
        arrival_time_str = route_data.get("arrival_time") # format ISO
        # Simplified time check
        if arrival_time_str and ("T23:" in arrival_time_str or "T00:" in arrival_time_str):
             addons.append({
                "id": "SECURE_TAXI",
                "title": "Verified Night Pickup",
                "reason": "Late arrival? Pre-book a secure, verified taxi for peace of mind.",
                "price": 350,
                "target_station": route_data.get("destination_code")
            })

        return addons

upsell_agent = AdaptiveUpsellAgent()
