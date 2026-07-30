import asyncio
import time
import psutil
import logging
from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger("nexus.triage")

class SystemStatus(str, Enum):
    STABLE = "STABLE"       # All systems nominal
    LAGGING = "LAGGING"     # Performance jitter detected
    CONGESTED = "CONGESTED" # Resource pressure is high
    SEVERED = "SEVERED"     # Core infrastructure is unreachable
    FAILED = "FAILED"       # Critical error in health monitoring

@dataclass
class HealthMetric:
    domain: str
    status: str
    value: float
    description: str

class TriageEngine:
    """
    [Task 28] The 'X-Ray' Diagnostic Brain for the Nexus Fiber.
    Heuristically analyzes system pressure points to prevent cascading failure.
    """
    def __init__(self):
        self.last_analysis_time = 0
        self._cached_report = None
        self._backoff_factor = 0.0 # 0.0 (Stable) to 1.0 (Severed/Total Block)
        self._smoothing = 0.3      # Exponential moving average factor
        
    @property
    def current_backoff(self) -> float:
        """Reactive signal for adaptive throttling [Task 29.1]"""
        return self._backoff_factor

    async def report_latency(self, latency_ms: int) -> None:
        """Report artificial latency to the triage engine and nudge backoff."""
        if latency_ms <= 0:
            return
        self._backoff_factor = min(1.0, self._backoff_factor + min(0.15, latency_ms / 60000.0))
        logger.debug(f"[TRIAGE] Reported latency {latency_ms}ms, backoff now {self._backoff_factor:.3f}")

    def _calculate_raw_backoff(self, status: SystemStatus) -> float:
        """Determines target backoff level based on triage [Task 29.1]"""
        mapping = {
            SystemStatus.STABLE: 0.0,
            SystemStatus.LAGGING: 0.3,
            SystemStatus.CONGESTED: 0.7,
            SystemStatus.SEVERED: 1.0,
            SystemStatus.FAILED: 1.0
        }
        return mapping.get(status, 1.0)

    async def get_deep_diagnostics(self) -> Dict[str, Any]:
        """
        Polls Distributed Layers and performs Heuristic Triage.
        [Task 28.1/28.2 / Task 29.1]
        """
        now = time.time()
        # Non-blocking diagnostic refresh
        if self._cached_report and (now - self.last_analysis_time < 0.5):
             return self._cached_report

        metrics = []
        
        # 1. Cache Layer Triage (Task 5 & 26)
        try:
            from services.multi_layer_cache import multi_layer_cache
            l2_healthy = await multi_layer_cache.health_check()
            metrics.append(HealthMetric(
                domain="cache_l2",
                status="OK" if l2_healthy else "SEVERED",
                value=1.0 if l2_healthy else 0.0,
                description="Redis L2 Connectivity"
            ))
        except: pass

        # 2. Persistence Layer Triage (Task 27)
        try:
            from core.nexus.financial.rollback import nexus_saga
            orphans = await nexus_saga.list_all_orphaned()
            zombie_count = len(orphans)
            metrics.append(HealthMetric(
                domain="saga_registry",
                status="NOMINAL" if zombie_count < 5 else "CONGESTED",
                value=float(zombie_count),
                description=f"{zombie_count} pending rollbacks"
            ))
        except: pass

        # 3. Compute/Memory Triage (Task 24)
        try:
             from core.nexus.cache.mmap_cortex import nexus_cortex
             ram_percent = nexus_cortex.get_ram_percent()
             metrics.append(HealthMetric(
                 domain="compute_ram",
                 status="STABLE" if ram_percent < 90 else "PRESSURE",
                 value=float(ram_percent),
                 description=f"RSS Memory: {ram_percent}% (Hostinger Plan Limit Check)"
             ))
        except: pass

        # 4. Chaos Mesh Status (Task 25)
        try:
            from core.nexus.audit.chaos import nexus_chaos
            is_chaos_active = len(nexus_chaos.active_traps) > 0
            metrics.append(HealthMetric(
                domain="chaos_mesh",
                status="ACTIVE" if is_chaos_active else "IDLE",
                value=float(len(nexus_chaos.active_traps)),
                description=f"{len(nexus_chaos.active_traps)} active faults injected"
            ))
        except: pass

        # --- HEURISTIC TRIAGE [Task 28.2] ---
        overall_status = SystemStatus.STABLE
        
        # Check for Severance
        if any(m.domain == "cache_l2" and m.status == "SEVERED" for m in metrics):
             overall_status = SystemStatus.SEVERED
        
        # Check for Congestion (High load/Memory)
        elif any(m.status in ["PRESSURE", "CONGESTED"] for m in metrics):
             overall_status = SystemStatus.CONGESTED
             
        # Check for Lags (If chaos mesh is armed)
        elif any(m.domain == "chaos_mesh" and m.status == "ACTIVE" for m in metrics):
             overall_status = SystemStatus.LAGGING

        # [Task 29.11] Predictive Garbage Collection under pressure
        if overall_status in [SystemStatus.CONGESTED, SystemStatus.SEVERED]:
             import gc
             gc.collect()
             logger.warning("🧹 [TRIAGE:GC] High pressure detected. Forcing Garbage Collection.")

        # [Task 29.2] Apply Exponential Smoothing to prevent Rapid Backoff Flickering
        target_backoff = self._calculate_raw_backoff(overall_status)
        self._backoff_factor = (target_backoff * self._smoothing) + (self._backoff_factor * (1.0 - self._smoothing))

        report = {
            "node_status": overall_status,
            "backoff_factor": round(self._backoff_factor, 3), # 0.0 to 1.0 exposed to search/scrapers
            "timestamp": now,
            "metrics": [asdict(m) for m in metrics],
            "recommendation": self._get_recommendation(overall_status)
        }
        
        self._cached_report = report
        self.last_analysis_time = now
        return report

    def _get_recommendation(self, status: SystemStatus) -> str:
        """[Task 28.2] Explanatory advice for SRE/Admins."""
        if status == SystemStatus.STABLE:
             return "SYSTEM_NOMINAL: All fibers performing at premium level."
        elif status == SystemStatus.LAGGING:
             return "PREDICTIVE_ACTION: Jitter detected. Warming cache layers."
        elif status == SystemStatus.CONGESTED:
             return "ADAPTIVE_LOAD_SHEDDING: Reducing non-premium search depth."
        elif status == SystemStatus.SEVERED:
             return "SURVIVAL_GHOST_MODE: Trading freshness for zero-latency availability."
        return "DIAGNOSTIC_FAILURE: Internal monitoring error."

# Global Sentinel instance
nexus_triage = TriageEngine()
