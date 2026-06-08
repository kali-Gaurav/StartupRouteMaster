import tracemalloc
import logging
import time
import asyncio
import gc
from typing import Dict, List, Any, Optional

logger = logging.getLogger("nexus.audit.mem_profiler")

class MemoryLeakProfiler:
    """
    [Task 24] Advanced Memory Leak Profiler.
    Uses tracemalloc to analyze heap growth and detect slow-leak patterns.
    Designed for Hostinger KVM 2 to prevent OOM crashes from background workers.
    """
    
    def __init__(self, snapshot_interval: int = 3600): # Hourly snapshots by default
        self.snapshot_interval = snapshot_interval
        self._snapshots: List[tracemalloc.Snapshot] = []
        self._is_active = False
        self._loop_task: Optional[asyncio.Task] = None
        self._leak_incidents: List[Dict[str, Any]] = []
        
        # Performance Thresholds (RSS MB)
        self.LEAK_GROWTH_THRESHOLD_MB = 10.0 # Alert if >10MB growth between snapshots
        
    def start(self):
        """Begin memory instrumentation."""
        if not tracemalloc.is_tracing():
            logger.info("🛡️ [NEXUS:MEM] Initializing tracemalloc profiling (Task 24)...")
            tracemalloc.start()
            self._is_active = True
            self._loop_task = asyncio.create_task(self._profiler_loop())

    def stop(self):
        """Graceful shutdown of profiler."""
        self._is_active = False
        if self._loop_task:
            self._loop_task.cancel()
        if tracemalloc.is_tracing():
            tracemalloc.stop()
        logger.info("🛡️ [NEXUS:MEM] Profiler deactivated.")

    async def _profiler_loop(self):
        """Background worker for periodic heap analysis."""
        while self._is_active:
            try:
                await asyncio.sleep(self.snapshot_interval)
                await self.take_snapshot()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[NEXUS:MEM] Profiler Loop Error: {e}")

    async def take_snapshot(self) -> Dict[str, Any]:
        """Captures a heap snapshot and performs differential analysis."""
        if not tracemalloc.is_tracing():
             return {"error": "tracemalloc not active"}
             
        snapshot = tracemalloc.take_snapshot()
        self._snapshots.append(snapshot)
        
        # Keep only the last 3 snapshots for comparison to save RAM
        if len(self._snapshots) > 3:
            self._snapshots.pop(0)
            
        report = self.analyze_growth()
        return report

    def analyze_growth(self) -> Dict[str, Any]:
        """Compares the last two snapshots to find leaking objects."""
        if len(self._snapshots) < 2:
            return {"status": "AWAITING_INITIAL_SNAPSHOT"}
            
        # Filter filters (ignore profiler itself and internal libraries if needed)
        # However, for a generic leak check, we compare all.
        stats = self._snapshots[-1].compare_to(self._snapshots[-2], 'lineno')
        
        total_diff = sum(stat.size_diff for stat in stats)
        total_diff_mb = total_diff / (1024 * 1024)
        
        top_diffs = []
        for stat in stats[:5]: # Top 5 growing locations
             top_diffs.append({
                 "file": stat.traceback[0].filename,
                 "line": stat.traceback[0].lineno,
                 "diff_kb": round(stat.size_diff / 1024, 2)
             })

        analysis = {
            "delta_mb": round(total_diff_mb, 2),
            "top_growth": top_diffs,
            "timestamp": time.time()
        }

        if total_diff_mb > self.LEAK_GROWTH_THRESHOLD_MB:
             logger.warning(f"⚠️ [NEXUS:MEM] MEMORY LEAK DETECTED! Growth: {total_diff_mb:.2f}MB in {self.snapshot_interval}s.")
             self._leak_incidents.append(analysis)
             # Emergency GC
             gc.collect()
        
        return analysis

    def get_stats(self) -> Dict[str, Any]:
        """Provides raw metrics for the Nexus Dashboard."""
        return {
            "active": self._is_active,
            "snapshots_captured": len(self._snapshots),
            "leak_incidents": len(self._leak_incidents),
            "current_leak_risk": "HIGH" if len(self._leak_incidents) > 0 else "LOW",
            "last_incident": self._leak_incidents[-1] if self._leak_incidents else None
        }

mem_profiler = MemoryLeakProfiler()
