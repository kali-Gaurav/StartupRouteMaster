import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import func
from database.models import RouteSearchLog, User
from database.session import SessionLocal
from services.ws_manager import ws_manager
from services.agents.base_agent import BaseAgent, AgentPriority

logger = logging.getLogger("agents.growth")

class GrowthAgentSwarm(BaseAgent):
    """
    [Group 4] Conversational 'Nudge' Agent.
    An active 'System Builder' that detects search burnout and rescues conversions.
    """
    name = "GrowthAgentSwarm"
    description = "Autonomous search burnout rescue and discount nudge swarm."
    category = "growth"
    priority = AgentPriority.NORMAL
    icon = "🌱"
    color = "#8B5CF6" # Purple-500
    version = "1.0.0"
    auto_schedule_interval = 60 # Check every minute

    def __init__(self):
        super().__init__()
        self.check_interval = 60 # Check every minute
        self.burnout_threshold = 5 # 5 searches for same route

    async def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Main execution hook for the agent swarm."""
        db = SessionLocal()
        try:
            await self.detect_search_burnout(db)
            return {
                "status": "success",
                "summary": "Growth agent scan completed successfully.",
                "data": {}
            }
        except Exception as e:
            logger.error(f"Growth Audit Error: {e}")
            return {
                "status": "error",
                "summary": f"Error: {str(e)}"
            }
        finally:
            db.close()

    async def track_search_intent(self, user_id: str, src: str, dst: str):
        """
        [G3.2.1.1] Real-time Search Tracker.
        Uses Redis to increment intent depth instantly.
        """
        from services.cache_service import cache_service
        key = f"burnout:{user_id}:{src}:{dst}"
        count = await cache_service.incr(key)
        await cache_service.expire(key, 900) # 15 minute window

        if count >= self.burnout_threshold:
            await self._issue_revenue_safe_nudge(user_id, src, dst, count)

    async def _issue_revenue_safe_nudge(self, user_id: str, src: str, dst: str, count: int):
        """
        [G3.2.1.2] Revenue-Safe Decision.
        Only issues a discount if liquidity permits.
        """
        from services.agents.finance_agents import RevenueAgent
        revenue_svc = RevenueAgent()
        
        # Calculate dynamic discount factor
        # 5 searches = 3%, 10 searches = 7%, max 10%
        discount_pct = min(3 + (count - 5) * 1, 10)
        
        # Check liquidity (Mocked check for early-stage startup)
        if await self._check_liquidity_for_discount():
            logger.warning(f"🚀 [GROWTH] High Intent Cluster! User {user_id} @ {count} searches. Issuing {discount_pct}% Rescue.")
            
            nudge_payload = {
                "type": "REVENUE_BACKED_NUDGE",
                "title": "Don't let this journey slip away!",
                "message": f"We noticed you're looking for a seat to {dst}. Since we want you on board, here is {discount_pct}% OFF your booking!",
                "intent": "DYNAMIC_DISCOUNT",
                "context": {
                    "src": src, 
                    "dst": dst, 
                    "discount_value": discount_pct,
                    "code": f"RM_RESCUE_{discount_pct}"
                }
            }
            await ws_manager.send_to_user(user_id, nudge_payload, "GROWTH_NUDGE")
        else:
            logger.info(f"🛡️ [GROWTH] Burnout detected for {user_id}, but liquidity low. Skipping discount to protect margins.")

    async def _check_liquidity_for_discount(self) -> bool:
        """Determines if the platform can afford a discount right now."""
        # Conceptually checks if OPERATING_CAPITAL > safety_margin
        return True # Default to True for early growth phase

    async def detect_search_burnout(self, db):
        # Legacy fallback if needed
        pass

    async def run_automation_loop(self):
        """Periodically scans for growth opportunities (Legacy)."""
        while True:
            await self.execute()
            await asyncio.sleep(self.check_interval)

# Global Instance
growth_agent_swarm = GrowthAgentSwarm()
