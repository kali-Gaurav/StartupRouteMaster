import psutil
import time
import logging
from typing import Dict, Any
from enum import Enum

logger = logging.getLogger("routemaster.resource_monitor")

class SurgeLevel(Enum):
    NORMAL = 0
    WARNING = 1
    CRITICAL = 2

class ResourceMonitor:
    def __init__(self, 
                 cpu_threshold_warning=70, 
                 cpu_threshold_critical=90,
                 ram_threshold_warning=75,
                 ram_threshold_critical=90):
        self.cpu_threshold_warning = cpu_threshold_warning
        self.cpu_threshold_critical = cpu_threshold_critical
        self.ram_threshold_warning = ram_threshold_warning
        self.ram_threshold_critical = ram_threshold_critical
        
        self._last_check_time = 0
        self._current_stats = {
            "cpu_percent": 0.0,
            "ram_percent": 0.0,
            "state": "HEALTHY"
        }

    def get_surge_level(self) -> SurgeLevel:
        """[Analysis Only] Determine current surge level without affecting logic."""
        stats = self.get_stats()
        cpu = stats["cpu_percent"]
        ram = stats["ram_percent"]
        
        if cpu > self.cpu_threshold_critical or ram > self.ram_threshold_critical:
            return SurgeLevel.CRITICAL
        if cpu > self.cpu_threshold_warning or ram > self.ram_threshold_warning:
            return SurgeLevel.WARNING
        return SurgeLevel.NORMAL

    def _update_stats(self):
        now = time.time()
        if now - self._last_check_time < 2.0:
            return

        process = psutil.Process()
        self._current_stats["cpu_percent"] = psutil.cpu_percent(interval=None)
        
        mem = psutil.virtual_memory()
        self._current_stats["ram_percent"] = mem.percent
        self._current_stats["process_rss_mb"] = process.memory_info().rss / (1024 * 1024)
        
        # Determine state for logging/analysis
        cpu = self._current_stats["cpu_percent"]
        ram = self._current_stats["ram_percent"]
        
        if cpu > self.cpu_threshold_critical or ram > self.ram_threshold_critical:
            self._current_stats["state"] = "CRITICAL"
        elif cpu > self.cpu_threshold_warning or ram > self.ram_threshold_warning:
            self._current_stats["state"] = "WARNING"
        else:
            self._current_stats["state"] = "HEALTHY"
            
        self._last_check_time = now

    def get_stats(self) -> Dict[str, Any]:
        self._update_stats()
        return self._current_stats

    def should_allow_request(self) -> bool:
        """Always allow - completeness requirement."""
        return True

    def should_throttle_tasks(self) -> bool:
        """Always return False - do not throttle based on load."""
        return False

    def get_health_report(self) -> Dict[str, Any]:
        stats = self.get_stats()
        return {
            "cpu": f"{stats['cpu_percent']}%",
            "ram": f"{stats['ram_percent']}%",
            "status": stats["state"],
            "recommendation": "LOG_ONLY" # No load shedding
        }

# Global Instance
resource_monitor = ResourceMonitor()
