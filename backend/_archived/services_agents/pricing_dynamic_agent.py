import logging
import psutil
from typing import Dict, Any
from services.agents.base_agent import BaseAgent, AgentPriority
from services.multi_layer_cache import multi_layer_cache

logger = logging.getLogger("agent.pricing_dynamic")

class DynamicPricingAgent(BaseAgent):
    """
    [G2.6.1] The 'Revenue Opt' Dynamic Pricing Swarm.
    Adjusts platform convenience fees in real-time based on system load,
    search volume, and corridor demand.
    """
    name = "DynamicPricingAgent"
    description = "Optimizes platform revenue via dynamic convenience fee adjustments."
    category = "finance"
    priority = AgentPriority.HIGH
    icon = "💹"
    color = "#10B981" # Green

    async def calculate_convenience_fee(self, source: str, destination: str, current_occupancy: int = 0, physical_capacity: int = 100) -> Dict[str, Any]:
        """
        [Child G2.6.1.2] Dynamic Fee Engine.
        Returns the optimal fee and the reason (surge/discount).
        """
        from services.agents.overbooking_agent import overbooking_agent
        
        base_fee = 25.0
        surge_multiplier = 1.0
        reason = "Standard base fee."

        # 1. Overbooking & Capacity Analysis
        overbook_data = await overbooking_agent.calculate_overbook_limit(
            train_id=f"{source}-{destination}",
            physical_capacity=physical_capacity,
            route_features={"source": source, "destination": destination}
        )
        
        virtual_capacity = overbook_data["virtual_capacity"]
        utilization = current_occupancy / virtual_capacity if virtual_capacity > 0 else 0

        # 2. Revenue Optimization Logic
        if utilization > 0.9:
            surge_multiplier = 2.5
            reason = "Critical capacity surge (Yield Max)."
        elif utilization > 0.75:
            surge_multiplier = 1.8
            reason = "High demand surge."
        elif utilization < 0.3 and overbook_data["overbook_count"] > 0:
            surge_multiplier = 0.8
            reason = "Virtual inventory discount (Load Balance)."

        # 3. System Load Check (Perimeter Protection)
        cpu_usage = psutil.cpu_percent()
        if cpu_usage > 85:
            surge_multiplier = max(surge_multiplier, 2.0)
            reason = "Server high-load surge."

        final_fee = round(base_fee * surge_multiplier, 2)
        
        return {
            "base_fee": base_fee,
            "final_fee": final_fee,
            "surge_active": final_fee > base_fee,
            "discount_active": final_fee < base_fee,
            "reason": reason,
            "virtual_cap_applied": overbook_data["virtual_capacity"],
            "currency": "INR"
        }

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Main execution entry point."""
        src = context.get("source", "NDLS")
        dst = context.get("destination", "HWH")
        occ = context.get("current_occupancy", 50)
        cap = context.get("physical_capacity", 100)
        
        res = await self.calculate_convenience_fee(src, dst, occ, cap)
        return {
            "status": "success",
            "summary": f"Fee calculated: {res['final_fee']} INR ({res['reason']})",
            **res
        }

    async def _get_corridor_demand(self, src: str, dst: str) -> int:
        """Fetch demand metrics from Redis."""
        if not multi_layer_cache.redis:
            return 10
            
        key = f"demand:corridor:{src}:{dst}"
        # Simplified: get count for the current hour
        count = await multi_layer_cache.redis.get(key)
        return int(count) if count else 0

pricing_dynamic_agent = DynamicPricingAgent()
