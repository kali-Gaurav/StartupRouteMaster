"""
Circuit breaker implementation for the Contextual Availability Transformer (CAT) system.
Provides circuit breaker pattern for external API calls to prevent cascade failures.
"""

import logging
import time
import threading
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Any, Optional, TypeVar, Awaitable, Dict
from dataclasses import dataclass, field
import asyncio

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Circuit is open, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5  # Number of failures before opening circuit
    recovery_timeout_seconds: float = 30.0  # Time before attempting recovery
    half_open_max_calls: int = 3  # Number of calls allowed in half-open state
    failure_rate_threshold: float = 0.5  # Failure rate threshold for opening circuit
    minimum_throughput: int = 10  # Minimum requests before calculating failure rate


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    last_state_change: Optional[datetime] = None
    state: CircuitState = CircuitState.CLOSED


T = TypeVar('T')


class CircuitBreaker:
    """
    Circuit breaker for external API calls.
    
    Prevents cascade failures by opening circuit after threshold failures.
    Implements half-open state for testing recovery.
    """
    
    def __init__(
        self,
        config: CircuitBreakerConfig = None,
        name: str = "default"
    ):
        """
        Initialize the circuit breaker.
        
        Args:
            config: Circuit breaker configuration
            name: Circuit breaker name for logging
        """
        self._config = config or CircuitBreakerConfig()
        self._name = name
        self._state = CircuitState.CLOSED
        self._lock = threading.Lock()
        
        # Failure tracking
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_success_time: Optional[datetime] = None
        
        # Half-open state tracking
        self._half_open_calls = 0
        
        # Statistics
        self._stats = CircuitBreakerStats()
        self._stats.state = CircuitState.CLOSED
        self._stats.last_state_change = datetime.utcnow()
        
        logger.info(f"Circuit breaker '{name}' initialized with {self._config}")
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state
    
    @property
    def stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics."""
        return self._stats
    
    def _should_allow_request(self) -> bool:
        """Check if request should be allowed based on current state."""
        if self._state == CircuitState.CLOSED:
            return True
        
        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self._last_failure_time:
                elapsed = (datetime.utcnow() - self._last_failure_time).total_seconds()
                if elapsed >= self._config.recovery_timeout_seconds:
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
        self._stats.state = CircuitState.OPEN
        self._stats.last_state_change = datetime.utcnow()
        logger.warning(f"Circuit breaker '{self._name}' opened after {self._failure_count} failures")
    
    def _transition_to_half_open(self) -> None:
        """Transition to half-open state."""
        self._state = CircuitState.HALF_OPEN
        self._half_open_calls = 0
        self._stats.state = CircuitState.HALF_OPEN
        self._stats.last_state_change = datetime.utcnow()
        logger.info(f"Circuit breaker '{self._name}' transitioning to half-open")
    
    def _transition_to_closed(self) -> None:
        """Transition to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._stats.state = CircuitState.CLOSED
        self._stats.last_state_change = datetime.utcnow()
        logger.info(f"Circuit breaker '{self._name}' closed after recovery")
    
    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            self._stats.successful_calls += 1
            self._success_count += 1
            self._last_success_time = datetime.utcnow()
            
            if self._state == CircuitState.HALF_OPEN:
                self._transition_to_closed()
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0
    
    def record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self._stats.failed_calls += 1
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
        with self._lock:
            self._stats.rejected_calls += 1
    
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
            self._stats.rejected_calls += 1
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
            self._stats.rejected_calls += 1
            raise CircuitOpenError(f"Circuit breaker '{self._name}' is open")
        
        try:
            result = await func()
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise
    
    def get_state(self) -> Dict[str, Any]:
        """Get circuit breaker state as dictionary."""
        return {
            "name": self._name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time.isoformat() if self._last_failure_time else None,
            "last_success_time": self._last_success_time.isoformat() if self._last_success_time else None,
            "stats": {
                "total_calls": self._stats.total_calls,
                "successful_calls": self._stats.successful_calls,
                "failed_calls": self._stats.failed_calls,
                "rejected_calls": self._stats.rejected_calls
            }
        }


class CircuitOpenError(Exception):
    """Exception raised when circuit is open."""
    pass


def create_circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout_seconds: float = 30.0,
    name: str = "default"
) -> CircuitBreaker:
    """
    Factory function to create a CircuitBreaker.
    
    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout_seconds: Time before attempting recovery
        name: Circuit breaker name
    
    Returns:
        Configured CircuitBreaker instance
    """
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        recovery_timeout_seconds=recovery_timeout_seconds
    )
    return CircuitBreaker(config=config, name=name)
