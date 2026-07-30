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
from typing import Callable, Any, Optional, Dict, TypeVar, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .retry import retry as _retry

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """States for circuit breaker."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


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


CircuitBreakerState = CircuitState  # Alias for backward compatibility


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
    
    def __init__(self, name: str, config: CircuitConfig = None):
        """
        Initialize circuit breaker.
        
        Args:
            name: Circuit breaker name for identification
            config: Circuit configuration
        """
        self._name = name
        self._config = config or CircuitConfig()
        self._state = CircuitState.CLOSED
        self._lock = asyncio.Lock()
        
        # Failure tracking
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_success_time: Optional[datetime] = None
        
        # Half-open state tracking
        self._half_open_calls = 0
        
        # Metrics
        self._metrics = CircuitMetrics()
        self._metrics.state = CircuitState.CLOSED
        self._metrics.last_state_change = datetime.utcnow()
        
        logger.info(f"CircuitBreaker '{name}' initialized with config: {self._config}")
    
    @property
    def name(self) -> str:
        """Get circuit breaker name."""
        return self._name
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state
    
    @property
    def metrics(self) -> CircuitMetrics:
        """Get circuit breaker metrics."""
        return self._metrics
    
    def _should_allow_request(self) -> bool:
        """Check if request should be allowed based on current state."""
        if self._state == CircuitState.CLOSED:
            return True
        
        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self._last_failure_time:
                elapsed = (datetime.utcnow() - self._last_failure_time).total_seconds()
                if elapsed >= self._config.timeout_seconds:
                    # Transition to half-open
                    self._transition_to_half_open()
                    return True
            return False
        
        if self._state == CircuitState.HALF_OPEN:
            # Allow limited calls in half-open state
            return self._half_open_calls < self._config.half_open_max_calls
        
        return False
    
    def _transition_to_open(self) -> None:
        """Transition to open state."""
        self._state = CircuitState.OPEN
        self._last_failure_time = datetime.utcnow()
        self._metrics.state = CircuitState.OPEN
        self._metrics.last_state_change = datetime.utcnow()
        logger.warning(f"Circuit breaker '{self._name}' opened after {self._failure_count} failures")
    
    def _transition_to_half_open(self) -> None:
        """Transition to half-open state."""
        self._state = CircuitState.HALF_OPEN
        self._half_open_calls = 0
        self._metrics.state = CircuitState.HALF_OPEN
        self._metrics.last_state_change = datetime.utcnow()
        logger.info(f"Circuit breaker '{self._name}' transitioning to half-open")
    
    def _transition_to_closed(self) -> None:
        """Transition to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._metrics.state = CircuitState.CLOSED
        self._metrics.last_state_change = datetime.utcnow()
        logger.info(f"Circuit breaker '{self._name}' closed after recovery")
    
    def record_success(self) -> None:
        """Record a successful call."""
        self._metrics.successful_calls += 1
        self._success_count += 1
        self._last_success_time = datetime.utcnow()
        
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self._config.success_threshold:
                self._transition_to_closed()
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            self._failure_count = 0
    
    def record_failure(self) -> None:
        """Record a failed call."""
        self._metrics.failed_calls += 1
        self._failure_count += 1
        self._last_failure_time = datetime.utcnow()
        
        if self._state == CircuitState.HALF_OPEN:
            # Any failure in half-open state opens the circuit
            self._transition_to_open()
        elif self._state == CircuitState.CLOSED:
            # Check if we should open the circuit
            if self._failure_count >= self._config.failure_threshold:
                self._transition_to_open()
    
    def record_rejection(self) -> None:
        """Record a rejected call (circuit open)."""
        self._metrics.rejected_calls += 1
    
    def execute(self, func: Callable[[], T]) -> T:
        """
        Execute a function through the circuit breaker.
        
        Args:
            func: Function to execute
            
        Returns:
            Result of the function
            
        Raises:
            CircuitOpenError: If circuit is open
        """
        if not self._should_allow_request():
            self.record_rejection()
            raise CircuitOpenError(f"Circuit breaker '{self._name}' is open")
        
        try:
            result = func()
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise
    
    async def execute_async(self, func: Callable[[], Awaitable[T]]) -> T:
        """
        Execute an async function through the circuit breaker.
        
        Args:
            func: Async function to execute (callable that returns awaitable)
            
        Returns:
            Result of the function
            
        Raises:
            CircuitOpenError: If circuit is open
        """
        if not self._should_allow_request():
            self.record_rejection()
            raise CircuitOpenError(f"Circuit breaker '{self._name}' is open")
        
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
        
        try:
            result = await func()
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise
    
    def decorate(self, func: Callable) -> Callable:
        """
        Decorate a function with circuit breaker protection.
        
        Args:
            func: Function to decorate
            
        Returns:
            Decorated function
        """
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                return await self.execute_async(lambda: func(*args, **kwargs))
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                return self.execute(lambda: func(*args, **kwargs))
            return sync_wrapper
    
    def get_state(self) -> Dict[str, Any]:
        """Get circuit breaker state as dictionary."""
        return {
            "name": self._name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time.isoformat() if self._last_failure_time else None,
            "last_success_time": self._last_success_time.isoformat() if self._last_success_time else None,
            "metrics": self._metrics.to_dict()
        }


class CircuitOpenError(Exception):
    """Exception raised when circuit is open."""
    pass


class CircuitBreakerManager:
    """Manager for multiple circuit breakers."""
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
    
    def get_or_create(self, name: str, config: CircuitConfig = None) -> CircuitBreaker:
        """
        Get existing circuit breaker or create new one.
        
        Args:
            name: Circuit breaker name
            config: Optional configuration
            
        Returns:
            CircuitBreaker instance
        """
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return self._breakers.get(name)
    
    def get_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name (alias for get)."""
        return self._breakers.get(name)
    
    def get_all(self) -> Dict[str, CircuitBreaker]:
        """Get all circuit breakers."""
        return self._breakers.copy()
    
    def get_states(self) -> Dict[str, Dict[str, Any]]:
        """Get state of all circuit breakers."""
        return {name: breaker.get_state() for name, breaker in self._breakers.items()}


# Global circuit breaker manager
circuit_manager = CircuitBreakerManager()

# Backward-compatible alias
circuit_breaker_manager = circuit_manager


def circuit_breaker(name: str, failure_threshold: int = 5, recovery_timeout: float = 60.0):
    """
    Circuit breaker decorator factory.
    
    Args:
        name: Circuit breaker name
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Time in seconds before attempting recovery
        
    Returns:
        Decorator that wraps functions with circuit breaker protection
    """
    config = CircuitConfig(
        failure_threshold=failure_threshold,
        timeout_seconds=recovery_timeout
    )
    breaker = circuit_manager.get_or_create(name, config)
    return breaker.decorate


class TokenBucketRateLimiter:
    """Token bucket rate limiter for API calls."""
    
    def __init__(self, rate: float = 1.0, capacity: int = 10):
        """
        Initialize token bucket rate limiter.
        
        Args:
            rate: Tokens added per second
            capacity: Maximum tokens in bucket
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = datetime.utcnow()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens from the bucket.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens were acquired, False otherwise
        """
        async with self._lock:
            now = datetime.utcnow()
            elapsed = (now - self.last_update).total_seconds()
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False