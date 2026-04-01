import time
import logging
import asyncio
from enum import Enum
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Failed, bypassing engine
    HALF_OPEN = "HALF_OPEN" # Testing if engine recovered

class EngineCircuitBreaker:
    """
    [Task 40.1] Intelligent Circuit Breaker for Routing Engines.
    Designed for high-efficiency VPS environments to prevent cascading failures.
    """
    def __init__(
        self, 
        engine_id: str, 
        failure_threshold: int = 3, 
        recovery_timeout_seconds: int = 60
    ):
        self.engine_id = engine_id
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.total_calls = 0
        self.successful_calls = 0
        
        # Lock for thread-safety in async environments
        self._lock = asyncio.Lock()

    async def can_execute(self) -> bool:
        """Determines if the engine is healthy enough to be called."""
        async with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            
            if self.state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if (time.time() - self.last_failure_time) > self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    logger.info(f"🛡️ [CIRCUIT:{self.engine_id}] Moving to HALF_OPEN. Attempting recovery call...")
                    return True
                return False
            
            if self.state == CircuitState.HALF_OPEN:
                # In half-open, we usually only want one 'pilot' call. 
                # For simplicity in this orchestrator, we allow calls and first failure sends it back to OPEN.
                return True
            
            return True

    async def record_success(self):
        """Called when engine returns a valid response."""
        async with self._lock:
            self.total_calls += 1
            self.successful_calls += 1
            if self.state == CircuitState.HALF_OPEN:
                logger.info(f"✅ [CIRCUIT:{self.engine_id}] Recovery successful! Returning to CLOSED.")
            
            self.state = CircuitState.CLOSED
            self.failure_count = 0

    async def record_failure(self, reason: str = "Unknown"):
        """Called when engine fails or returns invalid data."""
        async with self._lock:
            self.total_calls += 1
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            logger.warning(f"🚨 [CIRCUIT:{self.engine_id}] Failure logged ({self.failure_count}/{self.failure_threshold}). Reason: {reason}")
            
            # Fixed: Only trip if threshold reached. HALF_OPEN needs 1 additional failure to reopen.
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.error(f"🔌 [CIRCUIT:{self.engine_id}] TRIP! Service disabled for {self.recovery_timeout}s.")
            elif self.state == CircuitState.HALF_OPEN and self.failure_count >= 1:
                # Fail fast if recovery attempt fails
                self.state = CircuitState.OPEN
                logger.error(f"🔌 [CIRCUIT:{self.engine_id}] Recovery failed! Reopening.")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "failures": self.failure_count,
            "success_rate": round(self.successful_calls / self.total_calls, 2) if self.total_calls > 0 else 1.0,
            "total_calls": self.total_calls
        }
