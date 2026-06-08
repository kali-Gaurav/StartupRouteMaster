"""
Resilience Compatibility Layer
============================
Redirects legacy 'resilience' imports to 'core.resilience.core' or provides
standalone implementations for scraper-sentinel and other services.
"""

from cat.reliability.circuit_breaker import CircuitState, CircuitBreaker, CircuitBreakerConfig
from core.resilience.retry import retry as _retry, RetryPolicy

# Mock metrics for now to avoid breaking imports
class MetricsClient:
    def __init__(self, **kwargs): pass
    def gauge(self, *args, **kwargs): pass
    def counter(self, *args, **kwargs): pass
    def histogram(self, *args, **kwargs): pass
    def get_counter(self, *args): return 0
    def get_percentile(self, *args): return 0.0

def track_metrics(**kwargs):
    def decorator(func):
        return func
    return decorator

# Circuit Breaker Decorator Factory
def circuit_breaker(name: str, failure_threshold: int = 5, recovery_timeout: float = 60.0):
    from core.resilience.core import circuit_manager, CircuitConfig
    config = CircuitConfig(
        failure_threshold=failure_threshold,
        timeout_seconds=recovery_timeout
    )
    breaker = circuit_manager.get_or_create(name, config)
    return breaker.decorate

# Retry Policy - returns the actual retry decorator
class RetryStrategy:
    EXPONENTIAL_BACKOFF = "exponential"
    LINEAR_BACKOFF = "linear"

def retry_policy(**kwargs):
    """Retry policy decorator factory that returns the actual retry decorator."""
    return _retry