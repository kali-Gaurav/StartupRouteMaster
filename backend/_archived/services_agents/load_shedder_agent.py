import logging
import asyncio
import psutil
from services.agents.base_agent import BaseAgent, AgentPriority
from services.agents.orchestrator import swarm

logger = logging.getLogger("agent.load_shedder")

class LoadShedderAgent(BaseAgent):
    """
    [G4.3.1] The 'Gatekeeper' Load-Shedder.
    Protects platform availability by dynamically throttling background agents
    based on system resource pressure (CPU/RAM).
    """
    name = "LoadShedderAgent"
    description = "Protects core API performance by throttling low-priority background tasks during spikes."
    category = "infrastructure"
    priority = AgentPriority.CRITICAL # Always running
    icon = "🛡️"
    color = "#F43F5E" # Rose

    def __init__(self):
        super().__init__()
        self.shedding_active = False

    async def pulse(self):
        """Continuously monitors vitals and manages swarm state."""
        while True:
            try:
                await self.manage_system_load()
            except Exception as e:
                logger.error(f"⚠️ [LOAD_SHEDDER] Monitoring error: {e}")
            await asyncio.sleep(10) # High-resolution monitoring

    async def manage_system_load(self):
        """
        [Child G4.3.1.2] Swarm-Throttling Logic.
        Tiers agents by priority and sheds load as needed.
        """
        # 1. Fetch Vitals (Child G4.3.1.1)
        cpu_usage = psutil.cpu_percent()
        ram_usage = psutil.virtual_memory().percent
        
        logger.debug(f"📊 [LOAD_SHEDDER] CPU: {cpu_usage}% | RAM: {ram_usage}%")

        # 2. Decision Matrix (Child G4.3.1.3)
        if cpu_usage > 90 or ram_usage > 95:
            await self._apply_shedding(level="CRITICAL")
        elif cpu_usage > 85:
            await self._apply_shedding(level="HIGH")
        elif cpu_usage > 75:
            await self._apply_shedding(level="MEDIUM")
        elif cpu_usage < 60 and self.shedding_active:
            await self._lift_shedding()

    async def _apply_shedding(self, level: str):
        """Throttles agents based on the pressure level."""
        self.shedding_active = True
        active_agents = swarm._agents.values()
        
        logger.warning(f"🚨 [LOAD_SHEDDER] SHEDDING TRIGGERED (Level: {level}) | CPU usage critical.")

        for agent in active_agents:
            agent_priority = getattr(agent, "priority", None)
            if level == "MEDIUM" and agent_priority == AgentPriority.LOW:
                await self._suspend_agent(agent)
            elif level == "HIGH" and agent_priority in [AgentPriority.LOW, AgentPriority.NORMAL]:
                await self._suspend_agent(agent)
            elif level == "CRITICAL" and agent_priority != AgentPriority.CRITICAL:
                await self._suspend_agent(agent)

    async def _suspend_agent(self, agent):
        """Pauses a specific agent's pulse."""
        # Conceptually sets 'is_paused' flag on the agent
        # The agent's pulse loop should check this flag
        if not getattr(agent, "is_paused", False):
            agent_name = getattr(agent, "name", "unknown")
            agent_priority = getattr(agent, "priority", "unknown")
            logger.info(f"⏸️ [LOAD_SHEDDER] Suspending {agent_name} (Priority: {agent_priority})")
            setattr(agent, "is_paused", True)

    async def _lift_shedding(self):
        """Resumes all background agents."""
        logger.info("✅ [LOAD_SHEDDER] System vitals restored. Lifting all shedding.")
        self.shedding_active = False
        for agent in swarm._agents.values():
            if getattr(agent, "is_paused", False):
                agent_name = getattr(agent, "name", "unknown")
                logger.info(f"▶️ [LOAD_SHEDDER] Resuming {agent_name}")
                setattr(agent, "is_paused", False)

load_shedder_agent = LoadShedderAgent()
