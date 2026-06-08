import asyncio
import json
import logging
import sqlite3
import time
import functools
import os
from typing import Dict, Any, List, Optional, Callable, Awaitable

logger = logging.getLogger("nexus.saga")

# [Task 27.1] Persistent Saga SQLite Configuration
# Using individual registries for each node to prevent SQLite lock contention.
SAGA_DB_PATH = "nexus_sagas.db"


class SagaRegistry:
    """[Task 27.1/27.3] Persistent Write-Ahead-Log for Saga Transactions."""
    
    def __init__(self):
        # We perform init in a way that creates the schema if it doesn't exist
        with sqlite3.connect(SAGA_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS saga_logs (
                    tx_id TEXT,
                    step_name TEXT,
                    compensation_data BLOB,
                    order_index INTEGER,
                    status TEXT DEFAULT 'PENDING',
                    created_at REAL,
                    PRIMARY KEY (tx_id, step_name)
                )
            """)
            conn.commit()
        self._current_tx_id = None
        
    def start_transaction(self, tx_id: str):
        self._current_tx_id = tx_id
        logger.debug(f"📜 [SAGA:START] TX: {tx_id}")

    async def add_step(self, step_name: str, undo_data: Dict[str, Any], order: int):
        """[Task 27.1] Record compensating action before primary execution."""
        def _exec():
            # For Hostinger VPS: SQLite connections are cheap. Open-use-close ensures thread safety.
            with sqlite3.connect(SAGA_DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO saga_logs (tx_id, step_name, compensation_data, order_index, created_at) VALUES (?, ?, ?, ?, ?)",
                    (self._current_tx_id, step_name, json.dumps(undo_data), order, time.time())
                )
                conn.commit()
        
        await asyncio.to_thread(_exec)

    async def mark_completed(self, tx_id: str):
        """[Task 27.7] Finalize transaction and drop undo logs."""
        def _exec():
            with sqlite3.connect(SAGA_DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM saga_logs WHERE tx_id = ?", (tx_id,))
                conn.commit()
        
        await asyncio.to_thread(_exec)
        self._current_tx_id = None
        logger.debug(f"✅ [SAGA:COMMIT] TX: {tx_id} - Logs Purged.")

    async def purge_stale_logs(self):
        """[Gap Fix] Clean logs older than 24 hours."""
        def _exec():
            with sqlite3.connect(SAGA_DB_PATH) as conn:
                cursor = conn.cursor()
                cutoff = time.time() - 86400
                cursor.execute("DELETE FROM saga_logs WHERE created_at < ?", (cutoff,))
                conn.commit()
        
        await asyncio.to_thread(_exec)
        logger.info("🧹 [SAGA:CLEANUP] Stale transaction logs purged.")

    async def get_pending_compensations(self, tx_id: str) -> List[Dict[str, Any]]:
        def _exec():
            with sqlite3.connect(SAGA_DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT step_name, compensation_data FROM saga_logs WHERE tx_id = ? ORDER BY order_index DESC", (tx_id,))
                return [{"step": row[0], "data": json.loads(row[1])} for row in cursor.fetchall()]
        
        return await asyncio.to_thread(_exec)

    async def list_all_orphaned(self) -> List[str]:
        """[Task 27.8] Identifies transactions left after a crash."""
        def _exec():
            with sqlite3.connect(SAGA_DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT tx_id FROM saga_logs")
                return [row[0] for row in cursor.fetchall()]
            
        return await asyncio.to_thread(_exec)

# Global Singleton for the VPS Node
nexus_saga = SagaRegistry()

def atomic_fiber(transaction_domain: str):
    """
    [Task 27.2/Gap Fix] Master Decorator with Node-Unique TX IDs.
    """
    def decorator(func: Callable[..., Awaitable[Any]]):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Combined with os.getpid() to prevent collisions during parallel VPC/VPS scaling
            tx_id = f"{transaction_domain}:{os.getpid()}:{time.time_ns()}"
            nexus_saga.start_transaction(tx_id)
            
            # Atomic context for the current request
            setattr(asyncio.current_task(), "nexus_saga_tx_id", tx_id)
            setattr(asyncio.current_task(), "nexus_saga_steps", 0)
            
            try:
                result = await func(*args, **kwargs)
                # If success, clear logs
                await nexus_saga.mark_completed(tx_id)
                return result
            except (Exception, asyncio.CancelledError) as e:
                logger.error(f"🚨 [SAGA:FAILURE] Operation Failed: {e}. Orchestrating ROLLBACK for {tx_id}")
                await orchestrate_rollback(tx_id)
                raise e
        return wrapper
    return decorator

async def register_undo_step(name: str, undo_payload: Dict[str, Any]):
    """[Task 27.1] Core API to add a compensating action during a live transaction."""
    task = asyncio.current_task()
    tx_id = getattr(task, "nexus_saga_tx_id", None)
    if not tx_id:
        return # Not in an atomic fiber
        
    order = getattr(task, "nexus_saga_steps", 0) + 1
    # Ensure serializable [Gap Fix]
    try:
        payload_str = json.dumps(undo_payload) # Test serialization early
    except:
        logger.error(f"Saga Serialization Error for '{name}'. Using empty payload.")
        undo_payload = {"error": "non_serializable_data"}
        
    await nexus_saga.add_step(name, undo_payload, order)
    setattr(task, "nexus_saga_steps", order)
    logger.debug(f"🛡️ [SAGA:STEP] Recorded Undo for '{name}' (TX: {tx_id})")

async def orchestrate_rollback(tx_id: str, max_retries: int = 3):
    """
    [Task 27.4/27.5/Gap Fix] The Ultimate 'Undo Button' with Retry Recovery.
    """
    from core.nexus.audit.chaos import integrity_engine
    
    compensations = await nexus_saga.get_pending_compensations(tx_id)
    if not compensations:
        return

    logger.warning(f"🧟 [SAGA:RECOVERY] UNWINDING {len(compensations)} STEPS for TX: {tx_id}")
    integrity_engine.record("saga_orchestrator", "ROLLBACK_INITIATED", severity="WARNING", details={"tx_id": tx_id})

    for comp in compensations:
        step_name = comp["step"]
        data = comp["data"]
        
        attempt = 0
        while attempt < max_retries:
            try:
                 # Standard Layer Compensations (Task 27.4 & 27.5 & 27.6)
                 if step_name == "CACHE_WRITE":
                      from services.multi_layer_cache import multi_layer_cache
                      multi_layer_cache.lru.delete(data["key"])
                      if multi_layer_cache.redis:
                           await multi_layer_cache.redis.delete(data["key"])
                 
                 elif step_name == "SCRAPER_ACQUIRED":
                      from services.scraper_sentinel import scraper_sentinel
                      if "context_id" in data:
                           await scraper_sentinel.release_context({"id": data["context_id"]}, status="failure")
                 
                 elif step_name == "LEDGER_INTENT":
                      from services.ledger_service import ledger_service
                      from database.session import SessionUser
                      # Require local session context for rollback
                      logger.warning(f"   Saga: VOIDING FINANCIAL INTENT {data.get('entry_id')}")
                      with SessionUser() as db:
                           ledger_service.void_transaction(db, data.get("entry_id"), reason=f"SAGA_ROLLBACK:{tx_id}")
                 
                 logger.info(f"   ✅ Rollback Completed: {step_name}")
                 break # Step success
                 
            except Exception as e:
                 attempt += 1
                 logger.error(f"   ❌ ROLLBACK STEP FAILED ATTEMPT {attempt}: {step_name}: {e}")
                 await asyncio.sleep(0.5 * attempt) # Exponential backoff for rollback
                 if attempt == max_retries:
                      integrity_engine.record("saga_orchestrator", "ROLLBACK_FATAL_STEP", severity="CRITICAL", details={"tx_id": tx_id, "step": step_name})

    # Once all steps are (attempted) removed, purge the tx logs
    await nexus_saga.mark_completed(tx_id)
    integrity_engine.record("saga_orchestrator", "ROLLBACK_COMPLETE", severity="INFO", details={"tx_id": tx_id})
def perform_rollback(tx_id: str):
    """Convenient sync wrapper for orchestrating rollback for testing.
    This function is used by the chaos test script to trigger a rollback
    for a given transaction ID without needing to await the async function.
    """
    # Run the async rollback orchestrator in a new event loop.
    asyncio.run(orchestrate_rollback(tx_id))

