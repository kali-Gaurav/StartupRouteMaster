import logging
import psutil
import asyncio
from typing import Dict, Any
from sqlalchemy.orm import Session
from services.ws_manager import ws_manager

logger = logging.getLogger("agents.load_balancer")

class LoadBalancerAgent:
    """
    [Group 3] Autonomous Resource Rebalancer.
    Monitors CPU/Memory and dynamically redistributes or throttles background tasks.
    Ensures 'Shadow Searches' don't starve the primary Search API.
    """
    def __init__(self):
        self.cpu_threshold = 80.0 # 80% CPU
        self.memory_threshold = 85.0 # 85% RAM
        self.last_pressure_score = 0.0

    def get_system_pressure(self) -> float:
        """
        Calculates a unified pressure score (0.0 - 1.0).
        """
        cpu_usage = psutil.cpu_percent(interval=None)
        mem_usage = psutil.virtual_memory().percent
        
        # Max of both provides a conservative safety margin
        pressure = max(cpu_usage / 100.0, mem_usage / 100.0)
        self.last_pressure_score = pressure
        return pressure

    async def monitor_and_rebalance(self):
        """
        Periodically checks system health and issues rebalance alerts.
        """
        pressure = self.get_system_pressure()
        logger.info(f"⚖️ [REBALANCER] Global Node Pressure: {pressure:.1%}")

        if pressure > 0.9:
            logger.critical("🚨 [REBALANCER] NODE SATURATION DETECTED! Evacuating background tasks.")
            await self._issue_emergency_throttle("CRITICAL_SATURATION")
        elif pressure > self.cpu_threshold / 100.0:
            logger.warning("🟡 [REBALANCER] High Load detected. Throttling cache warmers.")
            await self._issue_emergency_throttle("HIGH_LOAD")

    async def _issue_emergency_throttle(self, reason: str):
        """Broadcasts a throttle command to all background workers."""
        payload = {
            "type": "THROTTLE_COMMAND",
            "reason": reason,
            "pressure": self.last_pressure_score,
            "action": "HALT_NON_ESSENTIAL"
        }
        # In a multi-node cluster, this would be an Inter-Process or Distributed event
        await ws_manager.broadcast_global(
            f"⚡ [REBALANCER] System Throttling {reason} | Load: {self.last_pressure_score:.1%}",
            "NEXUS_REBALANCE"
        )

    async def nominate_worker(self) -> Optional[Dict[str, Any]]:
        """Selects an alternate worker node for delegated load balancing."""
        # Placeholder cluster nomination logic.
        # In production this should query the cluster registry or service discovery.
        return None

# Global singleton
load_balancer_agent = LoadBalancerAgent()
