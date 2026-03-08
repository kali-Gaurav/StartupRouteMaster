import time
import logging
import json
from enum import Enum
from typing import Dict, Any, Optional
from services.multi_layer_cache import multi_layer_cache

logger = logging.getLogger(__name__)

class CircuitState(str, Enum):
    CLOSED = "CLOSED"       # API healthy, all requests pass
    OPEN = "OPEN"           # API unhealthy, all requests fail fast
    HALF_OPEN = "HALF_OPEN" # Testing API with limited requests

class ExternalAPIHealth:
    """
    Task 11: Production-Grade Circuit Breaker for External APIs.
    [11.1] State machine support.
    [11.3] Redis-backed for multi-worker consistency.
    [11.4] 3s Latency Trigger.
    """
    def __init__(self, provider_name: str = "RapidAPI", failure_threshold: int = 5, recovery_timeout: int = 300):
        self.name = provider_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.latency_limit_ms = 3000 # [11.4] 3 seconds
        
        # Redis Keys
        self.key_state = f"health:state:{self.name}"
        self.key_failures = f"health:failures:{self.name}"
        self.key_last_trip = f"health:last_trip:{self.name}"

    async def _get_redis(self):
        await multi_layer_cache.initialize()
        return multi_layer_cache.redis

    async def get_state(self) -> CircuitState:
        """[11.1] Retrieve current state from Redis."""
        r = await self._get_redis()
        if not r: return CircuitState.CLOSED
        
        state = await r.get(self.key_state)
        if not state: return CircuitState.CLOSED
        
        state_str = state.decode() if isinstance(state, bytes) else state
        
        # [11.7] Check for recovery timeout
        if state_str == CircuitState.OPEN:
            last_trip = await r.get(self.key_last_trip)
            if last_trip:
                trip_time = float(last_trip)
                if (time.time() - trip_time) > self.recovery_timeout:
                    await self._set_state(CircuitState.HALF_OPEN)
                    return CircuitState.HALF_OPEN
                    
        return CircuitState(state_str)

    async def _set_state(self, state: CircuitState):
        r = await self._get_redis()
        if r:
            await r.set(self.key_state, state.value)
            if state == CircuitState.OPEN:
                await r.set(self.key_last_trip, str(time.time()))
            elif state == CircuitState.CLOSED:
                await r.delete(self.key_failures)
            
            logger.warning(f"🚨 CIRCUIT BREAKER [{self.name}]: State changed to {state.value}")

    async def record_success(self, latency_ms: float = 0.0):
        """Handle success based on current state."""
        state = await self.get_state()
        r = await self._get_redis()
        
        if state == CircuitState.HALF_OPEN:
            # Successful test request, close the circuit
            await self._set_state(CircuitState.CLOSED)
        elif state == CircuitState.CLOSED:
            # [11.4] Check Latency
            if latency_ms > self.latency_limit_ms:
                logger.warning(f"High latency ({latency_ms:.0f}ms) detected for {self.name}.")
                await self.record_failure("Latency Limit Exceeded")
            else:
                if r: await r.delete(self.key_failures)

    async def record_failure(self, error: str = None):
        """[11.2] Increment failure counter and trip if threshold reached."""
        r = await self._get_redis()
        if not r: return

        state = await self.get_state()
        if state == CircuitState.HALF_OPEN:
            # Test request failed, reopen immediately
            await self._set_state(CircuitState.OPEN)
            return

        fails = await r.incr(self.key_failures)
        if fails >= self.failure_threshold:
            await self._set_state(CircuitState.OPEN)

    async def is_available(self) -> bool:
        """Helper for DataProvider to check if API should be called."""
        state = await self.get_state()
        return state != CircuitState.OPEN

    async def get_status(self) -> Dict[str, Any]:
        r = await self._get_redis()
        state = await self.get_state()
        fails = int(await r.get(self.key_failures) or 0) if r else 0
        return {
            "provider": self.name,
            "state": state.value,
            "consecutive_failures": fails,
            "available": state != CircuitState.OPEN
        }

# Multi-Provider instances
rapid_api_health = ExternalAPIHealth("RapidAPI")
rappid_health = ExternalAPIHealth("RappidIn")

# Maintenance for existing code imports
api_health = rapid_api_health 
