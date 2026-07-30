import logging
import asyncio
import time
from typing import Dict, Any, List
from services.agents.base_agent import BaseAgent, AgentPriority
from services.cache_service import cache_service
from services.communication.websocket import ws_manager

logger = logging.getLogger("agent.gateway")

class GatewaySwitcherAgent(BaseAgent):
    """
    [G4.2.1] The 'Gateway Switcher' Autonomous API Manager.
    Monitors upstream API latencies and autonomously switches search strategy
    between 'DIRECT_API', 'SCRAPED_SHADOW', and 'COLD_CACHE' modes.
    """
    name = "GatewaySwitcherAgent"
    description = "Autonomously manages API failovers and latency-based routing."
    category = "infrastructure"
    priority = AgentPriority.CRITICAL
    icon = "🔌"
    color = "#F59E0B" # Amber

    def __init__(self):
        super().__init__()
        self.LATENCY_THRESHOLD_MS = 2500  # 2.5 seconds threshold
        self.ERROR_RATE_THRESHOLD = 0.2   # 20% failure triggers failover
        self.check_interval = 15          # Fast check every 15s

    async def pulse(self):
        """Monitor Upstream Health."""
        while True:
            try:
                await self.audit_gateway_health()
            except Exception as e:
                logger.error(f"🚨 [GATEWAY] Health Audit Failure: {e}")
            await asyncio.sleep(self.check_interval)

    async def audit_gateway_health(self):
        """
        [Child G4.2.1.1] Latency Pulsar.
        """
        # Fetch metrics from Redis/Cache populated by providers
        avg_latency = float(cache_service.get("METRIC_GATEWAY_LATENCY") or 0.0)
        error_rate = float(cache_service.get("METRIC_GATEWAY_ERROR_RATE") or 0.0)
        current_mode = cache_service.get("GATEWAY_MODE") or "DIRECT_API"

        logger.info(f"📊 [GATEWAY] Latency: {avg_latency}ms | Error: {error_rate*100}% | Mode: {current_mode}")

        # 1. Decision Logic (Child G4.2.1.2)
        if (avg_latency > self.LATENCY_THRESHOLD_MS or error_rate > self.ERROR_RATE_THRESHOLD) and current_mode == "DIRECT_API":
            await self._switch_mode("SCRAPED_SHADOW", f"High Latency ({avg_latency}ms)")
        
        elif error_rate > 0.5 and current_mode == "SCRAPED_SHADOW":
            await self._switch_mode("COLD_CACHE", "Critical Upstream Failure")
            
        elif avg_latency < self.LATENCY_THRESHOLD_MS * 0.5 and error_rate < 0.05 and current_mode != "DIRECT_API":
            await self._switch_mode("DIRECT_API", "Infrastructure Restored")

    async def _switch_mode(self, new_mode: str, reason: str):
        """
        Mode Switcher (Child G4.2.1.2).
        """
        logger.critical(f"🔄 [GATEWAY] SWITCHING MODE: {new_mode} | Reason: {reason}")
        
        # 1. Update Global Config in Cache
        await cache_service.set("GATEWAY_MODE", new_mode)
        
        # 2. Update Health Sentinel
        from services.sentinel_service import health_sentinel
        health_sentinel.report_system_event(
            event_type="GATEWAY_FAILOVER",
            severity="WARNING" if new_mode == "SCRAPED_SHADOW" else "CRITICAL",
            details={"to_mode": new_mode, "reason": reason}
        )

        # 3. Notify Admin
        await ws_manager.broadcast_global(
            f"⚡ [GATEWAY] Failover triggered: Switched to {new_mode} due to {reason}.",
            "SYSTEM_NOTIFICATION"
        )
        
        # 4. (Future) Trigger physical infra changes if needed (e.g. scale scraping nodes)

gateway_switcher_agent = GatewaySwitcherAgent()
