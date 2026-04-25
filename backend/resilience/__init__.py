"""
Resilience Compatibility Layer
============================
Redirects legacy 'resilience' imports to 'core.resilience' or provides
standalone implementations for scraper-sentinel and other services.
"""

from core.resilience import CircuitState, CircuitBreaker as _CircuitBreaker

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
    from core.resilience import CircuitBreaker, CircuitConfig
    config = CircuitConfig(
        failure_threshold=failure_threshold,
        timeout_seconds=recovery_timeout
    )
    breaker = CircuitBreaker(name, config)
    
    class BreakerProxy:
        def __init__(self, breaker):
            self._breaker = breaker
        def __call__(self, func):
            return self._breaker.decorate(func)
        def __getattr__(self, name):
            return getattr(self._breaker, name)
            
    return BreakerProxy(breaker)

# Retry Policy
class RetryStrategy:
    EXPONENTIAL_BACKOFF = "exponential"
    LINEAR_BACKOFF = "linear"

def retry_policy(**kwargs):
    def decorator(func):
        return func
    return decorator
