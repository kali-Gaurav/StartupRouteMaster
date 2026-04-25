"""
Resilience Patterns - Circuit Breaker, Retry, and Fallback Utilities

Provides fault tolerance patterns for external service calls including:
- Circuit Breaker pattern (open, half-open, closed states)
- Exponential backoff retry logic
- Fallback handlers
"""

import asyncio
import logging
import functools
import time
from enum import Enum
from typing import Callable, Any, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .retry import retry as _retry

logger = logging.getLogger(__name__)


def retry_with_backoff(
    retries: Optional[int] = None,
    base_delay: Optional[float] = None,
    **kwargs: Any,
) -> Callable:
    """Backward-compatible retry decorator wrapper."""
    if retries is not None and "max_attempts" not in kwargs:
        kwargs["max_attempts"] = retries
    if base_delay is not None and "initial_delay" not in kwargs:
        kwargs["initial_delay"] = base_delay
    return _retry(**kwargs)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject all requests
    HALF_OPEN = "half_open"  # Testing if service recovered

CircuitBreakerState = CircuitState # Alias for backward compatibility


@dataclass
class CircuitConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5          # Number of failures before opening
    success_threshold: int = 3           # Successes needed in half-open to close
    timeout_seconds: float = 60.0        # Time to wait before trying again
    half_open_max_calls: int = 3         # Max concurrent calls in half-open state
    monitoring_window_seconds: float = 60.0  # Window for counting failures


@dataclass
class CircuitMetrics:
    """Metrics for circuit breaker."""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    total_calls: int = 0
    total_failures: int = 0
    total_successes: int = 0
    last_state_change: Optional[datetime] = None
    current_concurrent_calls: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_success_time": self.last_success_time.isoformat() if self.last_success_time else None,
            "last_state_change": self.last_state_change.isoformat() if self.last_state_change else None,
        }


class CircuitBreaker:
    """
    Circuit Breaker implementation for external service protection.
    
    State Machine:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Calls fail immediately without executing
    - HALF_OPEN: Limited calls allowed to test recovery
    
    Usage:
        breaker = CircuitBreaker("external_api", CircuitConfig(failure_threshold=3))
        try:
            result = await breaker.execute(external_service_call)
        except CircuitOpenError:
            result = fallback()
    """

    async def __aenter__(self):
        # For use with 'async with' blocks
        # No-op, but could add metrics or checks here
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # For use with 'async with' blocks
        # No-op, but could add metrics or checks here
        pass
    
    _instances = {}
    
    def __init__(self, name: str, config: Optional[CircuitConfig] = None):
        self.name = name
        self.config = config or CircuitConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_success_time = None
        self.last_state_change = None
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
        self._window_start = datetime.utcnow()
        # Register instance
        type(self)._instances[name] = self
        
    @classmethod
    def get_instance(cls, name: str) -> Optional['CircuitBreaker']:
        """Get existing circuit breaker by name."""
        return cls._instances.get(name)
    
    @classmethod
    def get_all_instances(cls) -> Dict[str, 'CircuitBreaker']:
        """Get all registered circuit breakers."""
        return cls._instances.copy()
    
    def _check_window_reset(self) -> None:
        """Reset failure count if monitoring window has passed."""
        now = datetime.utcnow()
        if (now - self._window_start).total_seconds() >= self.config.monitoring_window_seconds:
            self.failure_count = 0
            self.success_count = 0
            self._window_start = now
            logger.debug(f"🔄 {self.name}: Monitoring window reset")
    
    def _should_open(self) -> bool:
        """Check if circuit should transition to OPEN state."""
        return self.failure_count >= self.config.failure_threshold
    
    async def _transition_to_open(self) -> None:
        """Transition circuit to OPEN state."""
        self.state = CircuitState.OPEN
        self.last_state_change = datetime.utcnow()
        self._half_open_calls = 0
        logger.warning(f"🔴 {self.name}: Circuit OPENED after {self.failure_count} failures")
    
    async def _transition_to_half_open(self) -> None:
        """Transition circuit to HALF_OPEN state."""
        self.state = CircuitState.HALF_OPEN
        self.last_state_change = datetime.utcnow()
        self._half_open_calls = 0
        logger.info(f"🟡 {self.name}: Circuit HALF_OPEN - testing recovery")
    
    async def _transition_to_closed(self) -> None:
        """Transition circuit to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.last_state_change = datetime.utcnow()
        self.failure_count = 0
        self.success_count = 0
        logger.info(f"🟢 {self.name}: Circuit CLOSED - service recovered")
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function through the circuit breaker.
        
        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result from func
            
        Raises:
            CircuitOpenError: If circuit is open
            Exception: Any exception from func
        """
        async with self._lock:
            self._check_window_reset()
            
            # Check state and reject if open
            if self.state == CircuitState.OPEN:
                # Check if timeout has passed
                if self.last_state_change:
                    elapsed = (datetime.utcnow() - self.last_state_change).total_seconds()
                    if elapsed >= self.config.timeout_seconds:
                        await self._transition_to_half_open()
                    else:
                        raise CircuitOpenError(
                            f"Circuit {self.name} is OPEN. Retry after "
                            f"{self.config.timeout_seconds - elapsed:.0f}s"
                        )
            
            # Check half-open call limit
            if self.state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitOpenError(
                        f"Circuit {self.name} is HALF_OPEN. Max concurrent calls reached."
                    )
                self._half_open_calls += 1
        
        # Execute the function
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = await result
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            async with self._lock:
                self.total_calls += 1
                self.total_successes += 1
                self.success_count += 1
                self.last_success_time = datetime.utcnow()
                
                # Reset failure count on success while closed
                if self.state == CircuitState.CLOSED:
                    self.failure_count = 0
                    self.success_count = 0

                # Transition from half-open to closed
                if self.state == CircuitState.HALF_OPEN:
                    if self.success_count >= self.config.success_threshold:
                        await self._transition_to_closed()
                
                logger.debug(f"✅ {self.name}: Call succeeded in {duration_ms:.1f}ms")
            
            return result
            
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            async with self._lock:
                self.total_calls += 1
                self.total_failures += 1
                self.failure_count += 1
                self.last_failure_time = datetime.utcnow()
                
                # Check if we should open
                if self.state == CircuitState.HALF_OPEN:
                    # Any failure in half-open goes back to open
                    await self._transition_to_open()
                elif self._should_open():
                    await self._transition_to_open()
                
                logger.warning(f"❌ {self.name}: Call failed in {duration_ms:.1f}ms - {type(e).__name__}: {e}")
            
            return None

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Backward-compatible alias for async circuit execution."""
        return await self.execute(func, *args, **kwargs)

    def execute_sync(self, func: Callable, *args, **kwargs) -> Any:
        """Synchronous version of execute."""
        # Check state and reject if open
        if self.state == CircuitState.OPEN:
            if self.last_state_change:
                elapsed = (datetime.utcnow() - self.last_state_change).total_seconds()
                if elapsed >= self.config.timeout_seconds:
                    self.state = CircuitState.HALF_OPEN
                    self.last_state_change = datetime.utcnow()
                    self._half_open_calls = 0
                else:
                    raise CircuitOpenError(
                        f"Circuit {self.name} is OPEN. Retry after "
                        f"{self.config.timeout_seconds - elapsed:.0f}s"
                    )
        
        if self.state == CircuitState.HALF_OPEN:
            if self._half_open_calls >= self.config.half_open_max_calls:
                raise CircuitOpenError(
                    f"Circuit {self.name} is HALF_OPEN. Max concurrent calls reached."
                )
            self._half_open_calls += 1

        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            self.total_calls += 1
            self.total_successes += 1
            self.success_count += 1
            self.last_success_time = datetime.utcnow()
            
            if self.state == CircuitState.CLOSED:
                self.failure_count = 0
                self.success_count = 0
            
            if self.state == CircuitState.HALF_OPEN:
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.last_state_change = datetime.utcnow()
            
            logger.debug(f"✅ {self.name}: Sync call succeeded in {duration_ms:.1f}ms")
            return result
            
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.total_calls += 1
            self.total_failures += 1
            self.failure_count += 1
            self.last_failure_time = datetime.utcnow()
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self.last_state_change = datetime.utcnow()
            elif self._should_open():
                self.state = CircuitState.OPEN
                self.last_state_change = datetime.utcnow()
            
            logger.warning(f"❌ {self.name}: Sync call failed in {duration_ms:.1f}ms - {type(e).__name__}: {e}")
            return None

    def decorate(self, func: Callable) -> Callable:
        """Decorator for either sync or async functions."""
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await self.execute(func, *args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                return self.execute_sync(func, *args, **kwargs)
            return sync_wrapper

    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current circuit metrics."""
        metrics = CircuitMetrics(
            state=self.state,
            failure_count=self.failure_count,
            success_count=self.success_count,
            last_failure_time=self.last_failure_time,
            last_success_time=self.last_success_time,
            last_state_change=self.last_state_change,
            total_calls=getattr(self, 'total_calls', 0),
            total_failures=getattr(self, 'total_failures', 0),
            total_successes=getattr(self, 'total_successes', 0),
        )
        return metrics.to_dict()

    def get_state(self) -> CircuitState:
        """Get the current circuit breaker state."""
        return self.state

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_success_time = None
        self.last_state_change = None
        self._half_open_calls = 0
        self._window_start = datetime.utcnow()
        logger.info(f"🔄 {self.name}: Circuit breaker reset")


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


class CircuitBreakerManager:
    """
    Manager for multiple circuit breakers with health monitoring.
    """
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
    
    def get_or_create(self, name: str, config: Optional[CircuitConfig] = None) -> CircuitBreaker:
        """Get existing or create new circuit breaker."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]

    get_breaker = get_or_create  # Alias for backward compatibility
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return self._breakers.get(name)
    
    def get_all_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status of all circuit breakers."""
        return {
            name: breaker.get_metrics()
            for name, breaker in self._breakers.items()
        }
    
    def get_open_circuits(self) -> Dict[str, Dict[str, Any]]:
        """Get list of circuits that are open."""
        return {
            name: breaker.get_metrics()
            for name, breaker in self._breakers.items()
            if breaker.state == CircuitState.OPEN
        }
    
    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()


# Global circuit breaker manager
circuit_manager = CircuitBreakerManager()
circuit_breaker_manager = circuit_manager

# Pre-configured circuit breakers for common services
RAPIDAPI_BREAKER = circuit_manager.get_or_create(
    "rapidapi",
    CircuitConfig(
        failure_threshold=3,
        timeout_seconds=120.0,  # Longer timeout for external APIs
        half_open_max_calls=2
    )
)

REDIS_BREAKER = circuit_manager.get_or_create(
    "redis",
    CircuitConfig(
        failure_threshold=5,
        timeout_seconds=30.0,
        success_threshold=2
    )
)

DATABASE_BREAKER = circuit_manager.get_or_create(
    "database",
    CircuitConfig(
        failure_threshold=10,
        timeout_seconds=60.0,
        success_threshold=5
    )
)


async def with_circuit_breaker(
    breaker_name: str,
    func: Callable,
    *args,
    fallback: Optional[Callable] = None,
    **kwargs
) -> Any:
    """
    Execute function with circuit breaker protection.
    
    Args:
        breaker_name: Name of the circuit breaker
        func: Async function to execute
        *args: Positional arguments
        fallback: Optional fallback function
        **kwargs: Keyword arguments
        
    Returns:
        Result from func or fallback
    """
    breaker = circuit_manager.get(breaker_name)
    if not breaker:
        logger.error(f"Unknown circuit breaker: {breaker_name}")
        return await func(*args, **kwargs)
    
    try:
        return await breaker.execute(func, *args, **kwargs)
    except CircuitOpenError:
        if fallback:
            logger.warning(f"⚠️ Circuit {breaker_name} open, using fallback")
            return await fallback(*args, **kwargs) if asyncio.iscoroutinefunction(fallback) else fallback()
        raise
