import time
import logging
from collections import deque
from typing import Dict, Any, Deque
from core.nexus.state import SystemState

logger = logging.getLogger("nexus.database.watchdog")

class DatabaseLockWatchdog:
    """
    [Task 23] Database Lock Watchdog.
    Proactively detects and tracks SQLite 'BUSY' / 'LOCKED' states.
    If the 'Lock Density' (events per minute) exceeds safe thresholds,
    it triggers an automatic pool disposal to shed backlogged sessions.
    """
    
    def __init__(self):
        self._lock_events: Deque[float] = deque(maxlen=200) # Track last 200 events
        self._last_event_time: float = 0
        self.LOCK_DENSITY_THRESHOLD = 50 # 50 locks per minute is CRITICAL
        self.LOCK_WARNING_THRESHOLD = 15 # 15 locks per minute is WARNING
        
    def report_lock_event(self, name: str, error_type: str = "BUSY"):
        """Called by session utilities when a lock is encountered."""
        now = time.time()
        self._lock_events.append(now)
        self._last_event_time = now
        
        density = self.get_lock_density()
        from utils.integrity import integrity_engine
        
        # [Gap 3] Integrity Recording
        if density > self.LOCK_WARNING_THRESHOLD:
             integrity_engine.record("database.watchdog", "LOCK_THRESHOLD", severity="WARNING", details={"density": density})

        if density > self.LOCK_DENSITY_THRESHOLD:
             logger.critical(f"🚨 DB_LOCK_WATCHDOG: Critical Density reached ({density:.1f} epm)! Shedding Pools...")
             integrity_engine.record("database.watchdog", "POOL_SHED", severity="CRITICAL")
             from database.session import _dispose_all_pools
             import asyncio
             asyncio.create_task(_dispose_all_pools())
             
        # [Gap 4] WAL Checkpoint Hygiene
        if len(self._lock_events) % 50 == 0:
             asyncio.create_task(self._force_checkpoint())

    async def _force_checkpoint(self):
        """Forces SQLite to merge the WAL into the main database."""
        try:
            from database.session import async_engine_user, async_engine_transit
            from sqlalchemy import text
            for eng in [async_engine_user, async_engine_transit]:
                 async with eng.begin() as conn:
                      await conn.execute(text("PRAGMA wal_checkpoint(PASSIVE);"))
            logger.info("🛡️ [DB:WATCHDOG] WAL Checkpoint protocol complete.")
        except Exception as e:
            logger.error(f"Checkpoint failed: {e}")

    def get_lock_density(self) -> float:
        """Returns the average number of lock events per minute in the last window."""
        now = time.time()
        # Filter for events in the last 60s
        recent_events = [t for t in self._lock_events if now - t < 60]
        return float(len(recent_events))

    def get_stats(self) -> Dict[str, Any]:
        """Provides raw metrics for the Nexus Dashboard."""
        density = self.get_lock_density()
        return {
            "lock_density_epm": round(density, 2),
            "total_incidents": len(self._lock_events),
            "last_incident": round(time.time() - self._last_event_time, 1) if self._last_event_time > 0 else -1,
            "status": "HEALTHY" if density < self.LOCK_WARNING_THRESHOLD else "WARNING" if density < self.LOCK_DENSITY_THRESHOLD else "CRITICAL"
        }

database_watchdog = DatabaseLockWatchdog()
