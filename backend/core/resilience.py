import asyncio
import time
import logging
import functools
import random
from enum import Enum
from typing import Callable, Any, Optional

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
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: int = 30):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.last_failure_time = 0

    async def call(self, func: Callable, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                logger.info(f"🔄 Circuit {self.name} entering HALF_OPEN state.")
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception(f"🚫 Circuit {self.name} is OPEN. Call rejected.")

        try:
            result = await func(*args, **kwargs)
            if self.state == CircuitState.HALF_OPEN:
                logger.info(f"✅ Circuit {self.name} recovered. Closing.")
                self.state = CircuitState.CLOSED
                self.failures = 0
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()
            logger.error(f"❌ Circuit {self.name} failure {self.failures}/{self.failure_threshold}: {e}")
            
            if self.failures >= self.failure_threshold:
                logger.critical(f"🚨 Circuit {self.name} TRIPPED to OPEN state.")
                self.state = CircuitState.OPEN
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
