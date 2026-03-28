import logging
import asyncio
import json
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any

logger = logging.getLogger("nexus.financial.recovery")

class SagaRecoveryEngine:
    """
    [Task 44] Ghost-Mode Recovery.
    Identifies and unwinds orphaned transactions from nexus_sagas.db on startup.
    Ensures financial integrity even after a hard crash or SIGKILL.
    """
    
    def __init__(self, db_path: str = "nexus_sagas.db"):
        self.db_path = db_path

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    async def scan_and_recover(self):
        """[Task 44.1] Scan for 'STARTED' sagas that are older than 5 minutes."""
        logger.info("🧟 [NEXUS:RECOVERY] Scanning for orphaned financial sagas...")
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # [Nexus Fix] Ensure table exists before querying
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sagas (
                tx_id TEXT PRIMARY KEY,
                status TEXT,
                metadata TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.commit()
        
        # Sagas older than 5 mins are considered 'Ghosts'
        cutoff = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
        
        cursor.execute(
            "SELECT tx_id, status, metadata FROM sagas WHERE status = 'STARTED' AND created_at < ?",
            (cutoff,)
        )
        orphans = cursor.fetchall()
        
        if not orphans:
            logger.info("✅ No orphaned sagas found.")
            conn.close()
            return

        logger.warning(f"🧟 Found {len(orphans)} orphaned sagas. Initiating Ghost-Mode Recovery...")
        
        from .rollback import orchestrate_rollback
        
        for tx_id, status, metadata_json in orphans:
             metadata = json.loads(metadata_json)
             logger.warning(f"   Recovery: Unwinding Tx {tx_id} (Reason: CRASH_RECOVERY)")
             
             # 1. Orchestrate Rollback
             try:
                  await orchestrate_rollback(tx_id, metadata)
                  
                  # 2. Mark as Rolled Back in WAL
                  cursor.execute(
                      "UPDATE sagas SET status = 'ROLLED_BACK', updated_at = ? WHERE tx_id = ?",
                      (datetime.utcnow().isoformat(), tx_id)
                  )
                  conn.commit()
                  logger.info(f"   ✅ Tx {tx_id} recovered and voided.")
             except Exception as e:
                  logger.error(f"   ❌ Failed to recover Tx {tx_id}: {e}")

        conn.close()
        logger.info("🧟 [NEXUS:RECOVERY] Ghost-Mode Recovery Cycle Complete.")

saga_recovery = SagaRecoveryEngine()
