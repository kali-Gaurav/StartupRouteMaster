import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger("db-circuit-breaker")

class GhostSession:
    """
    Subtask 4.4: Write-Behind Fallback.
    Used when the primary DB is down. Queues writes to Redis instead of failing.
    """
    def __init__(self, fallback_cache):
        self.cache = fallback_cache
        self.operations = []

    async def execute(self, statement: Any, *args, **kwargs):
        logger.warning(f"👻 Ghost Session: Intercepted write - {str(statement)[:50]}...")
        self.operations.append({"sql": str(statement), "args": str(args)})
        
        # We simulate a successful DB execution but return nothing
        class DummyResult:
            def scalars(self): return []
            def scalar(self): return None
            def fetchall(self): return []
        return DummyResult()

    async def commit(self):
        if self.operations:
            logger.info(f"👻 Ghost Session: Queueing {len(self.operations)} writes to Redis for later reconciliation.")
            # Store a copy to avoid reference issues during clear()
            await self.cache.set(f"ghost_writes_{time.time()}", list(self.operations), ttl=86400)
            self.operations.clear()

    async def rollback(self):
        self.operations.clear()

    async def close(self):
        pass

class DBCircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.state = "CLOSED" # CLOSED = Normal, OPEN = Failing, HALF_OPEN = Recovering
        self.last_failure_time = 0

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.error("🚨 DB Circuit Breaker TRIPPED. Entering Ghost Mode.")

    def record_success(self):
        self.failures = 0
        if self.state != "CLOSED":
            logger.info("✅ DB Circuit Breaker RESET. Resuming normal operations.")
        self.state = "CLOSED"

    def is_open(self) -> bool:
        if self.state == "OPEN":
            if (time.time() - self.last_failure_time) > self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info("⚠️ DB Circuit Breaker HALF_OPEN. Testing connection...")
                return False # Let one through to test
            return True
        return False

db_circuit_breaker = DBCircuitBreaker()
