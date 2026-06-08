import contextvars
import time
from typing import Optional

# [Task 29] Context-Aware Timeout variables
request_timeout_ctx: contextvars.ContextVar[Optional[float]] = contextvars.ContextVar("request_timeout", default=None)
request_start_time_ctx: contextvars.ContextVar[Optional[float]] = contextvars.ContextVar("request_start_time", default=None)

def get_remaining_timeout(default: float = 5.0) -> float:
    """[Task 29.1] Calculate the remaining timeout budget for the current request."""
    total_timeout = request_timeout_ctx.get()
    start_time = request_start_time_ctx.get()
    
    if total_timeout is None or start_time is None:
        return default
        
    elapsed = time.perf_counter() - start_time
    remaining = total_timeout - elapsed
    return max(0.1, remaining) 

def check_timeout():
    """[Task 29.3] Raise TimeoutError if current request has exceeded its budget."""
    if get_remaining_timeout() <= 0.1:
        raise TimeoutError("Request budget exhausted (context-aware timeout)")
