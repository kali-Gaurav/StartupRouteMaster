import asyncio
import functools
import logging
import psutil
import time
from typing import Callable, Any, TypeVar, Coroutine
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("routemaster.performance")

# Task 5.3: Core CPU Offloader Pool
_executor = ThreadPoolExecutor(max_workers=min(32, (psutil.cpu_count() or 1) * 4 if hasattr(psutil, 'cpu_count') else 4))

T = TypeVar("T")

def cpu_offload(func: Callable[..., T]) -> Callable[..., Coroutine[Any, Any, T]]:
    """
    Decorator to automatically run CPU-intensive or blocking sync functions 
    in a dedicated thread pool. Part of Task 5: Event Loop Optimization.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> T:
        loop = asyncio.get_running_loop()
        # Use a partial to pass kwargs to the pool
        p_func = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(_executor, p_func)
    return wrapper

@cpu_offload
def blocking_psutil_calls():
    """Example entry: Psutil calls can sometimes block under high disk IO."""
    import psutil
    return psutil.cpu_percent(interval=None)

class LoopWatchdogHelper:
    """Helper to ensure the event loop is ticking."""
    @staticmethod
    async def tick_forever():
        from core.engines.orchestrator import orchestrator
        while not orchestrator.is_shutting_down:
            orchestrator.watchdog.check_in()
            await asyncio.sleep(0.5)

class slow_await:
    """
    Task 5.9: Context manager to trace slow awaits.
    Usage: async with slow_await("DB_QUERY", threshold=0.1): 
              await db.execute(...)
    """
    def __init__(self, name: str, threshold: float = 0.5):
        self.name = name
        self.threshold = threshold
        self.start = 0

    async def __aenter__(self):
        self.start = time.perf_counter()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration = time.perf_counter() - self.start
        if duration > self.threshold:
            logger.warning(f"🐢 SLOW AWAIT: '{self.name}' took {duration*1000:.1f}ms (threshold={self.threshold*1000}ms)")
            from core.infrastructure.system_monitor import system_monitor
            system_monitor.report_request_latency(duration * 1000)
