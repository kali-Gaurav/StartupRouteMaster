import asyncio
import time
import logging
import sqlite3
import os
import sys

# Ensure we can import from backend
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import with_db_retry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-2.8")

DB_PATH = "lock_test.db"

@with_db_retry(max_retries=10, initial_delay=0.1)
async def concurrent_write(worker_id):
    """Simulates a write that might fail due to SQLite locking."""
    # We use raw sqlite here to easily simulate locks
    # By opening a connection and not closing it quickly
    conn = sqlite3.connect(DB_PATH, timeout=1) # Low timeout to trigger lock faster
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO test_lock (val) VALUES (?)", (f"worker_{worker_id}",))
        # Simulate some processing time while holding lock
        await asyncio.sleep(0.05)
        conn.commit()
        # logger.info(f"Worker {worker_id} success.")
        return True
    except Exception as e:
        # logger.error(f"Worker {worker_id} failed: {e}")
        raise e
    finally:
        conn.close()

async def run_lock_test(count=20):
    if os.path.exists(DB_PATH): os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE test_lock (val TEXT)")
    conn.close()

    logger.info(f"Launching {count} concurrent workers to stress-test SQLite locks...")
    start = time.time()
    
    # We use a mix of tasks
    tasks = [concurrent_write(i) for i in range(count)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    duration = time.time() - start
    success_count = sum(1 for r in results if r is True)
    
    logger.info(f"Test complete in {duration:.2f}s. Successes: {success_count}/{count}")
    
    if success_count == count:
        logger.info("✅ Database Lock Recovery Verified. All concurrent writes recovered via retry.")
    else:
        logger.error(f"❌ Recovery failed. Errors: {[r for r in results if r is not True]}")

    if os.path.exists(DB_PATH): os.remove(DB_PATH)

if __name__ == "__main__":
    asyncio.run(run_lock_test())
