import logging
import time
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger("nexus.watchdog")

class NexusWatchdog:
    """
    [Task 121] Centralized Health Monitor for Nexus Background Tasks.
    Ensures that heartbeats from various workers (Redis, DB Scale, R2 Sync)
    are within safe execution windows.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NexusWatchdog, cls).__new__(cls)
            cls._instance._heartbeats = {}
            cls._instance._thresholds = {
                "redis_heartbeat": 120, # seconds
                "db_pool_scaler": 60,
                "r2_sync": 3600,
                "vacuum_worker": 24 * 3600,
            }
        return cls._instance

    def poke(self, component: str):
        """Register a heartbeat for a component."""
        self._heartbeats[component] = time.time()
        logger.debug(f"[WATCHDOG] Component '{component}' poked.")

    def get_status(self) -> Dict[str, Any]:
        """Check all components for health."""
        now = time.time()
        report = {}
        for comp, threshold in self._thresholds.items():
            last_poke = self._heartbeats.get(comp)
            if last_poke is None:
                status = "INITIALIZING"
                age = -1
            elif (now - last_poke) > threshold:
                status = "STALE"
                age = round(now - last_poke, 1)
            else:
                status = "HEALTHY"
                age = round(now - last_poke, 1)
            
            report[comp] = {
                "status": status,
                "last_poke_sec_ago": age,
                "threshold_sec": threshold
            }
        return report

nexus_watchdog = NexusWatchdog()
