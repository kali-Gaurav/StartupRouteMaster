import asyncio
import logging
from core.nexus.node import NexusNode
from core.nexus.state import nexus_state_manager, NexusState

logger = logging.getLogger("nexus.pulse")

class NexusHeartbeat(NexusNode):
    """[Task 6.1] Real-Time System Pulse for Nexus V3 Monitoring."""
    
    def __init__(self, bootstrapper, interval: int = 60):
        super().__init__("pulse", dependencies=[])
        self._boot = bootstrapper
        self._interval = interval
        self._running = False
        self._pulse_task = None
        
    async def on_start(self):
        """Start the background monitoring pulse."""
        self._running = True
        self._pulse_task = asyncio.create_task(self._pulse_loop())
        logger.info(f"💓 [PULSE] System Heartbeat active (Interval: {self._interval}s).")
        
    async def on_stop(self):
        """Stop the background monitoring pulse."""
        self._running = False
        if self._pulse_task:
            self._pulse_task.cancel()
        logger.info("💓 [PULSE] Heartbeat stopped.")

    async def _pulse_loop(self):
        """Main background loop to audit node health and system state."""
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                
                # Check all other nodes
                all_healthy = True
                failed_nodes = []
                
                for name, node in self._boot._nodes.items():
                    if name == "pulse": continue
                    if not node.is_healthy:
                        all_healthy = False
                        failed_nodes.append(name)
                        
                # Update System State based on audit
                if not all_healthy:
                    logger.warning(f"⚠️ [PULSE] Degraded operations detected: {', '.join(failed_nodes)} nodes failed.")
                    if nexus_state_manager.current_state == NexusState.READY:
                        nexus_state_manager.set_state(NexusState.DEGRADED, reason=f"Nodes failed: {failed_nodes}")
                elif nexus_state_manager.current_state == NexusState.DEGRADED:
                    logger.info("✅ [PULSE] All nodes recovered. Restoring READY state.")
                    nexus_state_manager.set_state(NexusState.READY)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"⚠️ [PULSE] Monitoring Error: {e}")

# Note: This is registered by the bootstrapper in Phase 1 Integration
