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
                 cpu_threshold_warning=80, 
                 cpu_threshold_critical=95,
                 ram_threshold_warning=85,
                 ram_threshold_critical=95):
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

    def get_resource_budget(self) -> float:
        """[Task 16.2] Calculate search budget multiplier (0.1 to 1.0) with KVM Awareness."""
        stats = self.get_stats()
        cpu = stats["cpu_percent"]
        ram = stats["ram_percent"]
        cpu_steal = stats.get("cpu_steal", 0.0)
        swap_percent = stats.get("swap_percent", 0.0)
        
        # 1. Critical Fail-Safe (Hard limit for KVM/VPS)
        if cpu > 95 or ram > 95 or cpu_steal > 15.0 or swap_percent > 30.0:
            return 0.1 # Absolute minimum
            
        # 2. Virtual Core Pressure (KVM Steal)
        steal_penalty = 1.0 - (cpu_steal / 20.0)
        
        # 3. Standard CPU/RAM Decay (relaxed for development/VPS)
        budget = 1.0
        if cpu > 80:
            range_val = 95 - 80
            offset = cpu - 80
            budget = min(budget, 1.0 - (offset / range_val) * 0.7)
            
        if ram > 85:
            range_val = 95 - 85
            offset = ram - 85
            budget = min(budget, 1.0 - (offset / range_val) * 0.7)
            
        return max(0.3, budget * steal_penalty)

    def _update_stats(self):
        now = time.time()
        if now - self._last_check_time < 2.0:
            return

        process = psutil.Process()
        cpu_times = psutil.cpu_times_percent(interval=None)
        self._current_stats["cpu_percent"] = psutil.cpu_percent(interval=None)
        self._current_stats["cpu_steal"] = getattr(cpu_times, 'steal', 0.0)
        
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        self._current_stats["ram_percent"] = mem.percent
        self._current_stats["swap_percent"] = swap.percent
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
        """[Point 16] Return True if system is under pressure."""
        return self.get_surge_level() != SurgeLevel.NORMAL

    def get_health_report(self) -> Dict[str, Any]:
        stats = self.get_stats()
        surge = self.get_surge_level()
        return {
            "cpu": f"{stats['cpu_percent']}%",
            "ram": f"{stats['ram_percent']}%",
            "status": stats["state"],
            "surge_level": surge.name,
            "recommendation": "LOAD_SHED" if surge != SurgeLevel.NORMAL else "HEALTHY"
        }

# Global Instance
resource_monitor = ResourceMonitor()
