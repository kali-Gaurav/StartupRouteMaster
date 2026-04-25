import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime
from resilience.circuit_breaker import circuit_breaker, CircuitState
from resilience.retry_policy import retry_policy, RetryStrategy
from resilience.metrics import track_metrics, MetricsClient

class TransportType(Enum):
    RAIL = "rail"
    BUS = "bus"
    FLIGHT = "flight"
    TAXI = "taxi"

class BaseProvider(ABC):
    """
    [G8.1.1] Universal Provider Bridge.
    Abstract base class defining the contract for all transport providers.
    Ensures RouteMaster is multimodal-ready by design.
    """
    
    def __init__(self, provider_id: str, transport_type: TransportType):
        self.provider_id = provider_id
        self.transport_type = transport_type
        self.logger = logging.getLogger(f"provider.{provider_id}")
        
        # Circuit breaker for provider operations
        self._provider_circuit_breaker = circuit_breaker(
            name=f"provider_{provider_id}",
            failure_threshold=5,
            recovery_timeout=60.0
        )
        # Retry policy
        self._provider_retry_policy = retry_policy(
            max_attempts=3,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            base_delay=0.5,
            max_delay=10.0
        )
        # Metrics tracking
        self._metrics = MetricsClient(
            service_name=f"provider_{provider_id}",
            default_tags={"component": "provider", "transport_type": transport_type.value}
        )
        self._metrics.gauge("circuit_breaker_state", lambda: self._provider_circuit_breaker.state.value)
        self._metrics.counter("search_requests_total")
        self._metrics.counter("search_requests_success")
        self._metrics.counter("search_requests_failed")
        self._metrics.counter("verify_requests_total")
        self._metrics.counter("book_requests_total")
        self._metrics.counter("cancel_requests_total")
        self._metrics.counter("status_requests_total")
        self._metrics.histogram("request_duration_seconds")

    @abstractmethod
    @track_metrics(service="provider", operation="search")
    async def search(self, src: str, dst: str, date: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search for travel candidates."""
        pass

    @abstractmethod
    @track_metrics(service="provider", operation="verify")
    async def verify(self, candidate_id: str) -> Dict[str, Any]:
        """Verify real-time availability and price before booking."""
        pass

    @abstractmethod
    @track_metrics(service="provider", operation="book")
    async def book(self, candidate_id: str, passenger_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Finalize the booking with the upstream provider."""
        pass

    @abstractmethod
    @track_metrics(service="provider", operation="cancel")
    async def cancel(self, booking_id: str) -> bool:
        """Handle cancellation and refund logic."""
        pass

    @abstractmethod
    @track_metrics(service="provider", operation="get_status")
    async def get_status(self, booking_id: str) -> str:
        """Fetch real-time status (PNR Status, Ride Status, etc)."""
        pass

    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics for monitoring."""
        return {
            "service": f"provider_{self.provider_id}",
            "circuit_breaker_state": self._provider_circuit_breaker.state.name,
            "circuit_breaker_failures": self._provider_circuit_breaker.failure_count,
            "search_requests_total": self._metrics.get_counter("search_requests_total"),
            "search_requests_success": self._metrics.get_counter("search_requests_success"),
            "search_requests_failed": self._metrics.get_counter("search_requests_failed"),
            "verify_requests_total": self._metrics.get_counter("verify_requests_total"),
            "book_requests_total": self._metrics.get_counter("book_requests_total"),
            "cancel_requests_total": self._metrics.get_counter("cancel_requests_total"),
            "status_requests_total": self._metrics.get_counter("status_requests_total"),
            "request_duration_p50": self._metrics.get_percentile("request_duration_seconds", 50),
            "request_duration_p95": self._metrics.get_percentile("request_duration_seconds", 95),
        }

    def health_check(self) -> Dict[str, Any]:
        """Health check endpoint data."""
        return {
            "status": "healthy" if self._provider_circuit_breaker.state == CircuitState.CLOSED else "degraded",
            "service": f"provider_{self.provider_id}",
            "circuit_breaker": self._provider_circuit_breaker.state.name,
            "transport_type": self.transport_type.value,
            "timestamp": datetime.utcnow().isoformat()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker to closed state."""
        self._provider_circuit_breaker.reset()
        self.logger.info(f"🔄 [PROVIDER] Circuit breaker reset for {self.provider_id}")
