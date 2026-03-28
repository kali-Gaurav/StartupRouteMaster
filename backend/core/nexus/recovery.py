import asyncio
import logging
import time
from typing import Dict, List, Optional
from core.nexus.node import NexusNode, NodeStatus
from core.nexus.state import SystemState

logger = logging.getLogger("nexus.recovery")

class AutoRecoverySentinel:
    """
    [Task 21] Auto-Recovery Sentinel.
    Proactively monitors the 'Nexus Fiber' health and background loops.
    If a critical node fails or a heart-beat is lost, it triggers a controlled recovery.
    """
    def __init__(self, bootstrapper):
        self.boot = bootstrapper
        self._monitoring_task: Optional[asyncio.Task] = None
        self._last_heartbeat: Dict[str, float] = {}
        self._restart_counts: Dict[str, int] = {}
        self.MAX_RESTARTS_PER_NODE = 5
        self.CHECK_INTERVAL = 60 # 1 Minute

    def start(self):
        """Launch the background monitor."""
        if not self._monitoring_task or self._monitoring_task.done():
            logger.info("Auto-Recovery Sentinel: Activating Watchdog (Task 21)...")
            self._monitoring_task = asyncio.create_task(self._monitor_loop())

    def stop(self):
        """Graceful shutdown of the monitor."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            logger.info("Auto-Recovery Sentinel: Deactivated.")

    def record_heartbeat(self, node_name: str):
        """Nodes can call this to signal they are alive."""
        self._last_heartbeat[node_name] = time.time()

    async def _monitor_loop(self):
        """Infinite loop checking for zombie or failed nodes / background tasks."""
        while True:
            await asyncio.sleep(self.CHECK_INTERVAL)
            
            # Skip recovery if the whole system is booting or stopping
            if self.boot.state not in [SystemState.READY, SystemState.DEGRADED]:
                continue

            # 1. Check Nexus Nodes (Spine infrastructure)
            for name, node in self.boot.nodes.items():
                if node.status == NodeStatus.FAILED:
                    logger.warning(f"Auto-Recovery: Node '{name}' found in FAILED state. Triggering recovery...")
                    await self._recover_node(node)
                
                # Internal Heartbeat Check (if the node supports it)
                if name in self._last_heartbeat:
                    elapsed = time.time() - self._last_heartbeat[name]
                    if elapsed > 300: # 5 Minutes without sign of life
                        logger.error(f"Auto-Recovery: Node '{name}' HEARTBEAT LOST ({elapsed:.0f}s). Forcing restart...")
                        await self._recover_node(node)

            # 2. Check Background Managed Tasks (Legacy Orchestrator)
            try:
                from core.orchestrator import orchestrator
                for task_name, task in orchestrator.tasks.items():
                    hb_key = f"bg_task_{task_name}"
                    if hb_key in self._last_heartbeat:
                        elapsed = time.time() - self._last_heartbeat[hb_key]
                        # Background tasks get slightly more slack (10 mins)
                        if elapsed > 600:
                            logger.error(f"Auto-Recovery: Background Task '{task_name}' ZOMBIFIED ({elapsed:.0f}s). Re-starting managed loop...")
                            task.start()
                            # Reset heartbeat so we don't spam restarts
                            self._last_heartbeat[hb_key] = time.time()
            except Exception as e:
                logger.error(f"Auto-Recovery: Error during background task monitoring: {e}")

    async def _recover_node(self, node: NexusNode):
        """Attempt to reboot a specific node without halting the whole spine."""
        self._restart_counts[node.name] = self._restart_counts.get(node.name, 0) + 1
        
        if self._restart_counts[node.name] > self.MAX_RESTARTS_PER_NODE:
             logger.critical(f"Auto-Recovery: Node '{node.name}' exceeded MAX_RESTARTS ({self.MAX_RESTARTS_PER_NODE}). Escalating to System SAFE_MODE.")
             self.boot.state = SystemState.SAFE_MODE
             return

        try:
            logger.info(f"Auto-Recovery: Restarting {node.name} (Attempt {self._restart_counts[node.name]})...")
            # 1. Stop if possible (cleanup)
            await node.stop()
            # 2. Re-Init
            success = await node.start()
            
            if success:
                logger.info(f"Auto-Recovery: Node {node.name} RECOVERED.")
                # Reset heartbeat
                if node.name in self._last_heartbeat:
                    self._last_heartbeat[node.name] = time.time()
            else:
                logger.error(f"Auto-Recovery: Node {node.name} RECOVERY FAILED.")
        except Exception as e:
            logger.error(f"Auto-Recovery: Exception during recovery of {node.name}: {e}")
