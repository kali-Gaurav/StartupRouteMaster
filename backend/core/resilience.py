import asyncio
import time
import logging
import functools
import random
from enum import Enum
from typing import Callable, Any, Optional, List, Dict

logger = logging.getLogger("routemaster.resilience")

class CircuitState(Enum):
    CLOSED = "CLOSED"     # Normal operation
    OPEN = "OPEN"         # Failure threshold reached, blocking calls
    HALF_OPEN = "HALF_OPEN" # Testing if service recovered

class CircuitBreaker:
    """
    Task 7.8: Distributed Circuit Breaker (Hystrix Pattern).
    Prevents cascading failures by 'tripping' when a service is failing.
    """
    _registry: List['CircuitBreaker'] = []

    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: int = 30):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.last_failure_time = 0
        CircuitBreaker._registry.append(self)

    @classmethod
    def get_all_statuses(cls) -> List[Dict[str, Any]]:
        """[Task 22] Master Circuit Triage."""
        return [
            {
                "name": cb.name,
                "state": cb.state.value,
                "failures": cb.failures,
                "threshold": cb.failure_threshold,
                "last_failure": cb.last_failure_time
            } for cb in cls._registry
        ]

    def toggle_chaos(self, enabled: bool):
        """[Task 25.10] Enable/Disable Chaos-induced threshold tightening."""
        if enabled:
             self.failure_threshold = 2 # Tightened for heavy stress tests
             logger.warning(f"⚠️ [RESILIENCE:CHAOS] Circuit '{self.name}' THRESHOLD TIGHTENED to {self.failure_threshold}")
        else:
             self.failure_threshold = 5 # Baseline
             logger.info(f"🛡️ [RESILIENCE] Circuit '{self.name}' RECALIBRATED to baseline.")

    async def call(self, func: Callable, *args, **kwargs):
        from utils.integrity import integrity_engine
        
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                logger.info(f"🔄 Circuit {self.name} entering HALF_OPEN state.")
                self.state = CircuitState.HALF_OPEN
                integrity_engine.record(f"circuit.{self.name}", "HALF_OPEN", severity="WARNING")
            else:
                raise Exception(f"🚫 Circuit {self.name} is OPEN. Call rejected.")

        if self.state == CircuitState.HALF_OPEN:
            # [Gap 2] Proportional Probing: only allow 10% of traffic
            import random
            if random.random() > 0.1:
                 raise Exception(f"🔄 Circuit {self.name} is HALF_OPEN (Probing). Call shed.")

        try:
            result = await func(*args, **kwargs)
            if self.state == CircuitState.HALF_OPEN:
                logger.info(f"✅ Circuit {self.name} recovered. Closing.")
                self.state = CircuitState.CLOSED
                self.failures = 0
                integrity_engine.record(f"circuit.{self.name}", "RECOVERED", severity="SUCCESS")
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()
            logger.error(f"❌ Circuit {self.name} failure {self.failures}/{self.failure_threshold}: {e}")
            
            if self.failures >= self.failure_threshold:
                logger.critical(f"🚨 Circuit {self.name} TRIPPED to OPEN state.")
                self.state = CircuitState.OPEN
                integrity_engine.record(f"circuit.{self.name}", "TRIPPED", severity="CRITICAL", details={"reason": str(e)})
            raise e

def retry_with_backoff(retries: int = 3, base_delay: float = 0.5):
    """
    Task 7.9: Exponential Backoff Retry Policy.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_err = None
            for i in range(retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    delay = base_delay * (2 ** i) + random.uniform(0, 0.1)
                    logger.warning(f"⏳ Retry {i+1}/{retries} for {func.__name__} after {delay:.2f}s...")
                    await asyncio.sleep(delay)
            raise last_err
        return wrapper
    return decorator
