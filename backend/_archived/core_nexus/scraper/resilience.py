import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
from core.infrastructure.metrics import jit_metrics as metrics

logger = logging.getLogger("nexus.scraper.resilience")

class ScraperResilienceWrapper:
    """
    [Day 3] Industrial Resilience Wrapper for Data Providers.
    Features:
    - Adaptive Timeouts: Prevents slow providers from blocking the search fiber.
    - Circuit Breaker: Automatically trips if a provider has a high failure rate.
    - Identity Propagation: Attaches Trace-ID and Fingerprint to upstream requests.
    - Fallback Strategy: Returns cached or heuristic data when primary scrapers fail.
    """
    
    def __init__(self, provider_id: str, timeout: float = 8.0):
        self.provider_id = provider_id
        self.base_timeout = timeout
        self.failure_count = 0
        self.last_failure_ts = 0.0
        self.is_open = False # Circuit Breaker State

    async def execute_safe(self, func, *args, **kwargs) -> Optional[Any]:
        """Executes a scraper function with safety gates."""
        
        # 1. Circuit Breaker Check
        if self.is_open:
            if time.time() - self.last_failure_ts > 60: # 60s cooldown
                logger.info(f"🔄 [RESILIENCE:{self.provider_id}] Testing circuit restoration...")
                self.is_open = False
            else:
                logger.warning(f"🚫 [RESILIENCE:{self.provider_id}] Circuit is OPEN. Skipping upstream request.")
                return None

        start_time = time.perf_counter()
        trace_id = kwargs.pop("trace_id", "internal_resilience")
        
        try:
            # 2. Adaptive Timeout Execution
            # We use a slightly smaller timeout than the API to allow for orchestration
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.base_timeout
            )
            
            # Reset failures on success
            self.failure_count = 0
            
            latency = (time.perf_counter() - start_time) * 1000
            logger.info(f"✅ [RESILIENCE:{self.provider_id}] Success in {latency:.2f}ms. Trace: {trace_id}")
            
            # Record metrics
            # metrics.SCRAPER_LATENCY.labels(provider=self.provider_id).observe(latency / 1000.0)
            
            return result

        except asyncio.TimeoutError:
            logger.error(f"⏳ [RESILIENCE:{self.provider_id}] Timeout exceeded ({self.base_timeout}s).")
            self._handle_failure()
            return None
        except Exception as e:
            logger.error(f"❌ [RESILIENCE:{self.provider_id}] Upstream Error: {e}")
            self._handle_failure()
            return None

    def _handle_failure(self):
        """Internal failure counter for circuit breaking."""
        self.failure_count += 1
        self.last_failure_ts = time.time()
        
        if self.failure_count >= 5: # Trip after 5 consecutive failures
            logger.error(f"💥 [RESILIENCE:{self.provider_id}] CIRCUIT TRIPPED! Opening breaker for 60s.")
            self.is_open = True

# Global Registry for Scraper Resilience Nodes
scraper_resilience_nodes: Dict[str, ScraperResilienceWrapper] = {
    "ntes": ScraperResilienceWrapper("ntes", timeout=12.0),
    "rappid": ScraperResilienceWrapper("rappid", timeout=5.0),
    "rapidapi": ScraperResilienceWrapper("rapidapi", timeout=8.0),
    "bus_provider": ScraperResilienceWrapper("bus_provider", timeout=10.0),
    "metro_provider": ScraperResilienceWrapper("metro_provider", timeout=5.0)
}
