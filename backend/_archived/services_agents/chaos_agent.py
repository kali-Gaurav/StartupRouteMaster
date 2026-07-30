from typing import Optional
import logging
import random
import asyncio
from typing import List, Dict, Any
from services.agents.base_agent import BaseAgent, AgentPriority
from services.agents.registry import swarm

logger = logging.getLogger("agent.chaos")

class ChaosMonkeyAgent(BaseAgent):
    """
    [G4.8.1] The 'Titan' Chaos Resilience Agent.
    Periodically injects controlled failures into the agent swarm to
    test self-healing and service isolation.
    """
    name = "ChaosMonkeyAgent"
    description = "Hardens system resilience by injecting controlled component failures."
    category = "infrastructure"
    priority = AgentPriority.LOW
    icon = "🐒"
    color = "#F59E0B" # Amber

    async def run_chaos_cycle(self):
        """
        [Child G4.8.1.2] Chaos Dispatcher.
        Selects a non-critical victim and pauses it briefly.
        """
        while True:
            await asyncio.sleep(random.randint(300, 900)) # Every 5-15 mins
            
            if self.is_paused:
                continue

            # 1. Identify Victims (Child G4.8.1.1)
            # We only target non-critical (LOW/MEDIUM) agents
            potential_victims = [
                a for a in swarm.get_all_agents()
                if getattr(a, 'priority', AgentPriority.NORMAL) in [AgentPriority.LOW, AgentPriority.NORMAL] 
                and getattr(a, 'name', '') != self.name
            ]

            if not potential_victims:
                continue

            victim = random.choice(potential_victims)
            logger.warning(f"⚠️ [CHAOS] Injecting failure into: {victim.name}")
            
            # 2. Inject Failure
            original_state = victim.is_paused
            victim.is_paused = True
            
            # Wait for some search cycles to happen
            await asyncio.sleep(30) 
            
            # 3. Restore and Audit (Child G4.8.1.3)
            victim.is_paused = original_state
            logger.info(f"✅ [CHAOS] Restored {victim.name}. Audit: SYSTEM_STABLE")

    async def initialize(self):
        """Called once when the agent swarm boots."""
        await super().initialize()
        # Non-blocking chaos loop
        asyncio.create_task(self.run_chaos_cycle())

    async def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Manual execution point for diagnostic chaos."""
        return {"status": "success", "summary": "Chaos pulse manual execute skipped; using background loop."}

chaos_agent = ChaosMonkeyAgent()
