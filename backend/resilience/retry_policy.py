"""
Retry Policy Compatibility Layer
============================
Provides retry policy decorators for the resilience module.
"""

from core.resilience.retry import retry as _retry

class RetryStrategy:
    EXPONENTIAL_BACKOFF = "exponential"
    LINEAR_BACKOFF = "linear"

def retry_policy(**kwargs):
    """Retry policy decorator factory."""
    def decorator(func):
        return func
    return decorator