import asyncio
import logging
import time
from typing import Dict, Any, Optional
from sqlalchemy import text
from services.multi_layer_cache import multi_layer_cache
from database.session import SessionLocal
from services.agents.base_agent import BaseAgent, AgentPriority

logger = logging.getLogger("sentinel.db_pulse")

class DBSentinelAgent(BaseAgent):
    """
    [Group 1] Self-Healing Database Pulse Agent.
    An active 'System Builder' that preserves database integrity by hunting zombies.
    """
    name = "DatabaseGuardian"
    description = "Self-Healing Database Pulse Agent hunting zombie queries and managing load"
    category = "infrastructure"
    priority = AgentPriority.CRITICAL
    icon = "🛡️"
    color = "#F87171" # Red-400
    version = "1.0.0"
    auto_schedule_interval = 15 # Sample every 15s

    def __init__(self):
        super().__init__()
        self.check_interval = 15 # Sample every 15s
        self.load_threshold = 85.0 # 85% connection usage
        self.zombie_timeout = 60 # Kil sessions holding locks for > 60s

    async def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Main execution hook for the agent swarm.
        """
        db = SessionLocal()
        zombies_killed = 0
        try:
            stats = await self.get_db_stats(db)
            
            # 1. Kill Zombies if necessary
            if stats.get("waiting_locks", 0) > 0:
                zombies_killed = await self.kill_zombie_sessions(db)

            # 2. Manage Operation Mode
            if not stats.get("is_healthy", True):
                logger.critical(f"🔥 [DB_SENTINEL] PRESSURE CRITICAL | Load: {stats.get('active_connections_pct')}%")
                await self._activate_defensive_mode(stats)
            else:
                current_mode = await multi_layer_cache.get_raw("DB:OPERATION_MODE")
                if current_mode == "READ_ONLY":
                    logger.info("🌤️ [DB_SENTINEL] Stability Restored. Resuming Normal Mode.")
                    await multi_layer_cache.set_raw("DB:OPERATION_MODE", "NORMAL")
            
            return {
                "status": "success",
                "summary": f"DB Health check complete. Zombies killed: {zombies_killed}",
                "data": {
                    "stats": stats,
                    "zombies_killed": zombies_killed
                }
            }
        except Exception as e:
            logger.error(f"DB Sentinel Pulse Error: {e}")
            return {
                "status": "error",
                "summary": f"Pulse Error: {str(e)}"
            }
        finally:
            db.close()

    async def get_db_stats(self, db):
        """Fetches internal Postgres telemetry."""
        try:
            conn_query = text("SELECT count(*), (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') as max FROM pg_stat_activity")
            locking_query = text("SELECT count(*) FROM pg_locks WHERE NOT granted")
            
            conn_res = db.execute(conn_query).fetchone()
            lock_res = db.execute(locking_query).fetchone()
            
            active_pct = (conn_res[0] / conn_res[1]) * 100 if conn_res and conn_res[1] > 0 else 0
            
            return {
                "active_connections_pct": active_pct,
                "waiting_locks": lock_res[0] if lock_res else 0,
                "is_healthy": active_pct < self.load_threshold and (lock_res[0] if lock_res else 0) < 5
            }
        except Exception as e:
            logger.error(f"Failed to fetch DB stats: {e}")
            return {"is_healthy": False, "error": str(e)}

    async def kill_zombie_sessions(self, db):
        """
        [Task 1.1] Identifies and terminates long-running lock holders.
        """
        logger.info("🕵️ [DB_SENTINEL] Searching for zombie sessions...")
        zombie_query = text("""
            SELECT pid, now() - query_start as duration, query
            FROM pg_stat_activity
            WHERE state = 'active'
            AND (now() - query_start) > interval '60 seconds'
        """)
        
        zombies = db.execute(zombie_query).fetchall()
        for pid, duration, query in zombies:
            logger.warning(f"🔨 [DB_SENTINEL] Terminating zombie session {pid} | Duration: {duration} | Query: {query[:50]}")
            db.execute(text(f"SELECT pg_terminate_backend({pid})"))
        
        db.commit()
        return len(zombies)

    async def run_pulse(self):
        """Continuous watchdog and maintenance loop (Legacy)."""
        while True:
            await self.execute()
            await asyncio.sleep(self.check_interval)

    async def _activate_defensive_mode(self, stats: Dict[str, Any]):
        """Triggers defensive throttling."""
        await multi_layer_cache.set_raw("DB:OPERATION_MODE", "READ_ONLY", ttl=300)
        from services.ws_manager import ws_manager
        await ws_manager.broadcast_global(
            "🛑 SYSTEM: Database High Pressure. Non-critical writes throttled.",
            "DB_SHIELD_ACTIVE"
        )

# Global Instance
db_sentinel_agent = DBSentinelAgent()
