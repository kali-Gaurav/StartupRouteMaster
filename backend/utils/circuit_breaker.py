import time
import logging
import asyncio
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)

class CircuitBreakerOpenException(Exception):
    pass

class SafetyCircuitBreaker:
    """
    Task 15: Circuit Breaker for Third-Party Telecom APIs.
    Prevents system hangs when Twilio/External services are down.
    """
    def __init__(self, name: str, threshold: int = 5, recovery_timeout: int = 60):
        self.name = name
        self.threshold = threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED" # CLOSED, OPEN, HALF-OPEN

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                logger.info(f"🔄 [CIRCUIT BREAKER] {self.name} entering HALF-OPEN state.")
                self.state = "HALF-OPEN"
            else:
                raise CircuitBreakerOpenException(f"Circuit {self.name} is OPEN.")

        try:
            # Execute the actual API call
            result = await func(*args, **kwargs)
            
            # If successful in HALF-OPEN, close the circuit
            if self.state == "HALF-OPEN":
                logger.info(f"✅ [CIRCUIT BREAKER] {self.name} recovered. Closing circuit.")
                self.state = "CLOSED"
                self.failure_count = 0
                
            return result
            
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.threshold:
                logger.error(f"🚨 [CIRCUIT BREAKER] {self.name} threshold reached. Opening circuit.")
                self.state = "OPEN"
                
            raise e

# Create global breakers for telecom services
telecom_breaker = SafetyCircuitBreaker("TelecomAPI", threshold=3, recovery_timeout=30)
