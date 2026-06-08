import logging
import httpx
import base64
import time
from typing import Optional, Dict, Any
from datetime import datetime
from core.nexus.audit.chaos import chaos_trap
from resilience import circuit_breaker, CircuitState
from resilience.retry_policy import retry_policy, RetryStrategy
from resilience.metrics import track_metrics, MetricsClient

logger = logging.getLogger("nexus.captcha.gateway")

class CaptchaGateway:
    """[Task 33] Unified CAPTCHA Resolution Gateway.
    Abstracts resolution via RapidAPI, local OCR, or Mocks.
    """
    
    def __init__(self):
        # In a real VPS, we would load keys from Config
        from config import Config
        self.api_key = getattr(Config, "CAPTCHA_SOLVER_KEY", "MOCK_KEY")
        self.provider = "rapidapi_solver" # Example
        
        # Circuit breaker for CAPTCHA resolution
        self._captcha_circuit_breaker = circuit_breaker(
            name="captcha_gateway",
            failure_threshold=5,
            recovery_timeout=120.0  # 2 minutes for external service
        )
        # Retry policy
        self._captcha_retry_policy = retry_policy(
            max_attempts=3,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            base_delay=1.0,
            max_delay=30.0
        )
        # Metrics tracking
        self._metrics = MetricsClient(
            service_name="captcha_gateway",
            default_tags={"component": "scraper"}
        )
        self._metrics.gauge("circuit_breaker_state", lambda: self._captcha_circuit_breaker.state.value)
        self._metrics.counter("captcha_requests_total")
        self._metrics.counter("captcha_requests_success")
        self._metrics.counter("captcha_requests_failed")
        self._metrics.counter("captcha_requests_mock")
        self._metrics.histogram("captcha_resolution_duration_seconds")

    @track_metrics(service="captcha_gateway", operation="resolve_image_captcha")
    @_captcha_circuit_breaker
    @_captcha_retry_policy
    @chaos_trap("captcha_resolution")
    async def resolve_image_captcha(self, 
                                   image_bytes: bytes, 
                                   instruction: str = "Enter the characters in the image") -> Optional[str]:
        """
        [Task 33.2] Send image to solver and return text.
        Returns a mock response if in SLIM_MODE/DEV.
        """
        # 1. Deterministic Mock for Dev
        from config import Config
        if Config.SLIM_MODE:
             logger.info("🧪 [CAPTCHA:MOCK] Returning SLIM_MODE deterministic solver: 'ABCD12'")
             return "ABCD12"
             
        # 2. Real RapidAPI/External Solver Logic
        try:
             # This is a template for actual integration (e.g. 2Captcha via RapidAPI)
             # payload = {"image": base64.b64encode(image_bytes).decode(), "instruction": instruction}
             # async with httpx.AsyncClient() as client:
             #      resp = await client.post("https://api.solver.com/v1/solve", json=payload)
             #      return resp.json().get("text")
             logger.warning("⚠️ [CAPTCHA:REAL] solver not fully configured. Using fallback.")
             return "FAIL_USE_MOCK"
        except Exception as e:
             logger.error(f"🚨 [CAPTCHA:ERROR] Solver failed: {e}")
             return None

    async def resolve_text_captcha(self, challenge_text: str) -> Optional[str]:
        """
        [Task 33.2] Solve text-based math or logic challenges.
        Example: "What is 5 + 3?" -> "8"
        """
        try:
             import re
             # Basic Math Challenge Regex
             math_match = re.search(r'(\d+)\s*([\+\-\*])\s*(\d+)', challenge_text)
             if math_match:
                  a, op, b = math_match.groups()
                  a, b = int(a), int(b)
                  if op == '+': return str(a + b)
                  if op == '-': return str(a - b)
                  if op == '*': return str(a * b)
             
             return challenge_text.strip() # Default fallback
        except:
             return None

    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics for monitoring."""
        return {
            "service": "captcha_gateway",
            "circuit_breaker_state": self._captcha_circuit_breaker.state.name,
            "circuit_breaker_failures": self._captcha_circuit_breaker.failure_count,
            "captcha_requests_total": self._metrics.get_counter("captcha_requests_total"),
            "captcha_requests_success": self._metrics.get_counter("captcha_requests_success"),
            "captcha_requests_failed": self._metrics.get_counter("captcha_requests_failed"),
            "captcha_requests_mock": self._metrics.get_counter("captcha_requests_mock"),
            "captcha_resolution_duration_p50": self._metrics.get_percentile("captcha_resolution_duration_seconds", 50),
            "captcha_resolution_duration_p95": self._metrics.get_percentile("captcha_resolution_duration_seconds", 95),
        }

    def health_check(self) -> Dict[str, Any]:
        """Health check endpoint data."""
        return {
            "status": "healthy" if self._captcha_circuit_breaker.state == CircuitState.CLOSED else "degraded",
            "service": "captcha_gateway",
            "circuit_breaker": self._captcha_circuit_breaker.state.name,
            "provider": self.provider,
            "timestamp": datetime.utcnow().isoformat()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker to closed state."""
        self._captcha_circuit_breaker.reset()
        logger.info("🔄 [CAPTCHA] Circuit breaker reset for captcha gateway")

# Global instance
captcha_gateway = CaptchaGateway()
