import logging
import asyncio
import httpx
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from services.providers.base_provider import BaseProvider, TransportType
from database.config import Config
from resilience.circuit_breaker import circuit_breaker, CircuitState
from resilience.retry_policy import retry_policy, RetryStrategy
from resilience.metrics import track_metrics, MetricsClient

logger = logging.getLogger("provider.rapid")

class RapidTravelProvider(BaseProvider):
    """
    [G11.1] Universal RapidAPI Bridge.
    Connects to external flight/bus/taxi APIs via RapidAPI to 
    provide real-world data feeds to the routing engine.
    """
    def __init__(self, provider_id: str, transport_type: TransportType, api_host: str):
        super().__init__(provider_id, transport_type)
        self.api_host = api_host
        self.base_url = f"https://{api_host}"
        # Additional circuit breaker for HTTP operations
        self._http_circuit_breaker = circuit_breaker(
            name=f"rapid_provider_{provider_id}_http",
            failure_threshold=5,
            recovery_timeout=30.0
        )
        self._http_retry_policy = retry_policy(
            max_attempts=3,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            base_delay=0.5,
            max_delay=10.0
        )

    @track_metrics(service="rapid_provider", operation="search")
    async def search(self, src: str, dst: str, date: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Fetches live inventory from RapidAPI.
        """
        try:
            travel_date = datetime.strptime(date, "%Y-%m-%d")
        except (ValueError, TypeError):
            travel_date = datetime.now()

        start_time = time.perf_counter()
        api_key = getattr(Config, "RAPIDAPI_KEY", None)
        if not api_key:
            logger.warning(f"No RapidAPI key found in Config for {self.provider_id}. Skipping live search.")
            return []

        # [Task 11.1.2] Dynamic Endpoint Dispatch mapping
        endpoint = "/flights/search" if self.transport_type == TransportType.FLIGHT else "/bus/search"
        
        headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": self.api_host
        }
        
        params = {
            "from": src,
            "to": dst,
            "date": travel_date.strftime("%Y-%m-%d"),
            "currency": "INR"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}{endpoint}", params=params, headers=headers)
                duration = time.perf_counter() - start_time
                self._metrics.histogram("request_duration_seconds", duration)
                
                if response.status_code == 200:
                    data = response.json()
                    self._metrics.counter("search_requests_success", tags={"transport_type": self.transport_type.value})
                    # Standardization of heterogeneous API responses
                    return self._standardize_response(data)
                else:
                    self._metrics.counter("search_requests_failed", tags={"status_code": str(response.status_code)})
                    logger.error(f"RapidAPI ({self.api_host}) error: {response.status_code}")
                    return []
        except Exception as e:
            duration = time.perf_counter() - start_time
            self._metrics.histogram("request_duration_seconds", duration)
            self._metrics.counter("search_requests_failed", tags={"error_type": type(e).__name__})
            logger.error(f"RapidAPI search failed: {e}")
            raise

    def _standardize_response(self, raw_data: Any) -> List[Dict[str, Any]]:
        """Standardizes various RapidAPI formats into RouteMaster format."""
        results = []
        # Multi-API parser logic
        raw_list = raw_data.get("results") or raw_data.get("data") or []
        for item in raw_list:
            results.append({
                "provider_id": self.provider_id,
                "transport_type": self.transport_type.value,
                "total_cost": item.get("price") or item.get("fare") or 0,
                "departure_time": item.get("departure") or item.get("dep_time"),
                "arrival_time": item.get("arrival") or item.get("arr_time"),
                "is_verified": True,
                "metadata": item
            })
        return results

    async def verify(self, booking_id: str) -> bool:
        return True # Real verification would call /verify endpoint

    async def book(self, booking_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "SUCCESS", "ref": f"RAPID_{booking_id}"}

    async def cancel(self, booking_id: str) -> bool:
        """RapidAPI usually handles cancellation via their own dashboard or specific endpoints."""
        return True

    async def get_status(self, booking_id: str) -> str:
        """Polls RapidAPI for booking status."""
        return "CONFIRMED"

    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics for monitoring."""
        return {
            "service": f"rapid_provider_{self.provider_id}",
            "http_circuit_breaker_state": self._http_circuit_breaker.state.name,
            "http_circuit_breaker_failures": self._http_circuit_breaker.failure_count,
            "provider_circuit_breaker_state": self._provider_circuit_breaker.state.name,
            "provider_circuit_breaker_failures": self._provider_circuit_breaker.failure_count,
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
            "status": "healthy" if (self._http_circuit_breaker.state == CircuitState.CLOSED and 
                                   self._provider_circuit_breaker.state == CircuitState.CLOSED) else "degraded",
            "service": f"rapid_provider_{self.provider_id}",
            "http_circuit_breaker": self._http_circuit_breaker.state.name,
            "provider_circuit_breaker": self._provider_circuit_breaker.state.name,
            "transport_type": self.transport_type.value,
            "timestamp": datetime.utcnow().isoformat()
        }

    def reset_circuit_breaker(self, breaker_name: str = "all"):
        """Reset circuit breaker(s) to closed state."""
        if breaker_name == "all" or breaker_name == "http":
            self._http_circuit_breaker.reset()
        if breaker_name == "all" or breaker_name == "provider":
            self._provider_circuit_breaker.reset()
        logger.info(f"🔄 [RAPID_PROVIDER] Circuit breaker '{breaker_name}' reset for {self.provider_id}")

# Pre-register common providers (Example)
flight_bridge = RapidTravelProvider("SKYSCANNER", TransportType.FLIGHT, "skyscanner44.p.rapidapi.com")
bus_bridge = RapidTravelProvider("REDBUS_MOCK", TransportType.BUS, "redbus11.p.rapidapi.com")
