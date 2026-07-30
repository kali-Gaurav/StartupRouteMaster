import time
import functools
import logging
from typing import Any, Callable, Optional
from utils.metrics import EXTERNAL_API_LATENCY_SECONDS, EXTERNAL_API_CALLS_TOTAL, EXTERNAL_API_COSTS_TOTAL

logger = logging.getLogger(__name__)

def monitor_external_api(provider: str, cost_per_call: float = 0.0):
    """
    Subtask 3.2: Request Monitoring Wrapper.
    A decorator to automatically capture latency, status, and estimated costs 
    for outgoing API calls to external providers.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            endpoint = func.__name__
            start_time = time.time()
            status = "success"
            
            try:
                result = await func(*args, **kwargs)
                # If the result is a response object with status_code, use it
                if hasattr(result, 'status_code'):
                    status = str(result.status_code)
                return result
            except Exception as e:
                status = "error"
                logger.error(f"API Error [{provider}::{endpoint}]: {e}")
                raise
            finally:
                duration = time.time() - start_time
                
                # Record Metrics
                EXTERNAL_API_LATENCY_SECONDS.labels(provider=provider, endpoint=endpoint).observe(duration)
                EXTERNAL_API_CALLS_TOTAL.labels(provider=provider, endpoint=endpoint, status=status).inc()
                
                if cost_per_call > 0:
                    EXTERNAL_API_COSTS_TOTAL.labels(provider=provider).inc(cost_per_call)
                
                logger.debug(f"API Monitor [{provider}::{endpoint}]: {status} in {duration:.3f}s")

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            endpoint = func.__name__
            start_time = time.time()
            status = "success"
            
            try:
                result = func(*args, **kwargs)
                if hasattr(result, 'status_code'):
                    status = str(result.status_code)
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                EXTERNAL_API_LATENCY_SECONDS.labels(provider=provider, endpoint=endpoint).observe(duration)
                EXTERNAL_API_CALLS_TOTAL.labels(provider=provider, endpoint=endpoint, status=status).inc()
                if cost_per_call > 0:
                    EXTERNAL_API_COSTS_TOTAL.labels(provider=provider).inc(cost_per_call)

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

import asyncio # Needed for iscoroutinefunction check
