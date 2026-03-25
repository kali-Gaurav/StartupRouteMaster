import asyncio
import time
import logging
from typing import Callable, Coroutine, Any, Optional

logger = logging.getLogger("resilience.breaker")

class CircuitBreakerOpenError(Exception):
    pass

class AsyncCircuitBreaker:
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(self,
                 failure_threshold: int = 5,
                 reset_timeout: float = 60.0,
                 expected_exception: type = Exception,
                 name: str = "circuit_breaker"):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.expected_exception = expected_exception
        self.name = name
        self.state = self.CLOSED
        self.failures = 0
        self.last_failure_time = 0.0
        self.half_open_successes = 0
        self.half_open_success_threshold = 2

    def _record_success(self):
        self.failures = 0
        self.half_open_successes = 0
        if self.state == self.HALF_OPEN:
            logger.info(f"Breaker '{self.name}' [HALF-OPEN -> CLOSED]")
            self.state = self.CLOSED

    def _record_failure(self):
        self.last_failure_time = time.time()
        print(f"DEBUG_BREAKER: '{self.name}' failure recorded. Count: {self.failures + 1}")
        if self.state == self.HALF_OPEN:
            logger.warning(f"Breaker '{self.name}' [HALF-OPEN -> OPEN]")
            self.state = self.OPEN
            self.failures = self.failure_threshold
        else:
            self.failures += 1
            if self.failures >= self.failure_threshold:
                print(f"DEBUG_BREAKER: '{self.name}' threshold reached. Switching to OPEN.")
                logger.error(f"Breaker '{self.name}' [CLOSED -> OPEN] threshold reached.")
                self.state = self.OPEN

    def _can_transition(self) -> bool:
        return (time.time() - self.last_failure_time) >= self.reset_timeout

    def __call__(self, func):
        async def wrapper(*args, **kwargs):
            if self.state == self.OPEN:
                if self._can_transition():
                    logger.info(f"Breaker '{self.name}' [OPEN -> HALF-OPEN]")
                    self.state = self.HALF_OPEN
                else:
                    raise CircuitBreakerOpenError(f"Breaker '{self.name}' is OPEN")

            try:
                result = await func(*args, **kwargs)
                if self.state == self.HALF_OPEN:
                    self.half_open_successes += 1
                    if self.half_open_successes >= self.half_open_success_threshold:
                        self._record_success()
                elif self.state == self.CLOSED:
                    self._record_success()
                return result
            except self.expected_exception as e:
                self._record_failure()
                raise e
            except Exception as e:
                raise e
        return wrapper
