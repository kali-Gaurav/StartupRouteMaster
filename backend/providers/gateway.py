"""
The Unified Data Provider Gateway.
Refined with budget tracking, resilience failovers, and multi-layer caching.
"""
import asyncio
import logging
import time
import json
from typing import Optional, Dict, Any, List, Callable, Coroutine
from datetime import datetime

from sqlalchemy import select, update
from backend.database.session import AsyncSessionUser
from backend.database.models import APIBudget

from .models import UnifiedLiveStatus, UnifiedFare, UnifiedPNRStatus, UnifiedSchedule
from .clients.rapidapi import RapidApiClient, to_unified_live_status as rapidapi_to_unified
from .clients.ntes_scraper import NtesScraperClient, to_unified_live_status as ntes_to_unified
from .circuit_breaker import AsyncCircuitBreaker, CircuitBreakerOpenError
from services.multi_layer_cache import multi_layer_cache as cache_system

logger = logging.getLogger("provider.gateway")

# --- Resilience Defaults ---
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1

class ProviderGateway:
    def __init__(self):
        self.rapidapi_client = RapidApiClient()
        self.ntes_client = NtesScraperClient()
        
        # Instantiate Breakers
        self.rapidapi_breaker = AsyncCircuitBreaker(failure_threshold=5, reset_timeout=60.0, name="rapidapi")
        self.ntes_breaker = AsyncCircuitBreaker(failure_threshold=3, reset_timeout=45.0, name="ntes")
        
        # Pre-wrap retry helpers with breakers
        self._safe_fetch_rapidapi = self.rapidapi_breaker(self._execute_with_retries)
        self._safe_fetch_ntes = self.ntes_breaker(self._execute_with_retries)
        
        logger.info("Provider Gateway Initialized.")

    async def _execute_with_retries(self, func, *args, **kwargs):
        """Standard retry logic."""
        last_err = Exception("Max retries reached")
        print(f"DEBUG_GATEWAY: _execute_with_retries for {func.__name__}")
        for attempt in range(MAX_RETRIES + 1):
            try:
                res = await func(*args, **kwargs)
                print(f"DEBUG_GATEWAY: Call success on attempt {attempt}")
                return res
            except Exception as e:
                print(f"DEBUG_GATEWAY: Call failed on attempt {attempt}: {e}")
                last_err = e
                if attempt < MAX_RETRIES:
                    delay = RETRY_DELAY_SECONDS * (2 ** attempt)
                    await asyncio.sleep(delay)
                else: 
                    print(f"DEBUG_GATEWAY: Max retries reached, raising: {last_err}")
                    raise last_err
        return None

    async def _is_budget_ok(self, provider_name: str = "RapidAPI") -> bool:
        try:
            async with AsyncSessionUser() as session:
                query = select(APIBudget).filter(APIBudget.provider_name == provider_name)
                result = await session.execute(query)
                budget = result.scalar_one_or_none()
                if not budget: return True
                
                usage_percent = (budget.current_spend / budget.monthly_limit) * 100.0
                
                # Check Critical Threshold
                if usage_percent >= budget.critical_threshold_percent:
                    logger.critical(f"🛑 BUDGET EXCEEDED for {provider_name} ({usage_percent:.1f}%)")
                    return False
                
                # Check Warning Threshold & Alert (Throttled)
                if usage_percent >= budget.warning_threshold_percent:
                    alert_key = f"alert_sent:budget:{provider_name}:{datetime.utcnow().strftime('%Y-%m-%d-%H')}"
                    if not await cache_system.redis.exists(alert_key):
                        logger.warning(f"⚠️ Budget Warning for {provider_name}: {usage_percent:.1f}% consumed.")
                        # Direct Redis push for alert queue to avoid circular imports
                        alert_msg = {
                            "alert_id": f"budget_{provider_name}_{int(time.time())}",
                            "alert_type": "budget_warning",
                            "details": {
                                "message": f"API Budget Warning: {provider_name} has consumed {usage_percent:.1f}% of monthly limit.",
                                "provider": provider_name,
                                "usage_percent": round(usage_percent, 2)
                            },
                            "priority": "critical" if usage_percent > 90 else "high"
                        }
                        await cache_system.redis.rpush("booking_alerts_queue", json.dumps(alert_msg))
                        await cache_system.redis.setex(alert_key, 3600, "1") # Throttled for 1 hour
                
                return budget.is_active
        except Exception as e:
            logger.error(f"Budget check error: {e}")
            return True

    async def _record_api_cost(self, provider_name: str = "RapidAPI"):
        try:
            async with AsyncSessionUser() as session:
                stmt = update(APIBudget).where(APIBudget.provider_name == provider_name).values(
                    current_spend=APIBudget.current_spend + APIBudget.cost_per_request
                )
                await session.execute(stmt)
                await session.commit()
        except Exception as e: logger.error(f"Record cost error: {e}")

    async def get_live_status(self, train_number: str, train_date: str) -> Optional[UnifiedLiveStatus]:
        cache_key = f"live_status:{train_number}"
        cached = await cache_system.get(cache_key)
        if cached:
            try: return UnifiedLiveStatus(**cached) if isinstance(cached, dict) else cached
            except Exception: pass

        # 1. Primary: RapidAPI
        if await self._is_budget_ok("RapidAPI"):
            start = time.perf_counter()
            try:
                raw_data = await self._safe_fetch_rapidapi(self.rapidapi_client.get_live_status, train_number, train_date=train_date)
                lat = (time.perf_counter() - start) * 1000
                from backend.core.metrics import jit_metrics
                
                if raw_data:
                    jit_metrics.record_provider_call("rapidapi", True, lat)
                    asyncio.create_task(self._record_api_cost("RapidAPI"))
                    unified = rapidapi_to_unified(raw_data=raw_data, train_date=train_date)
                    if unified:
                        await cache_system.put(cache_key, unified.model_dump(), ttl=300)
                        return unified
                else:
                    jit_metrics.record_provider_call("rapidapi", False, lat)
            except Exception as e:
                lat = (time.perf_counter() - start) * 1000
                from backend.core.metrics import jit_metrics
                jit_metrics.record_provider_call("rapidapi", False, lat)
                logger.warning(f"RapidAPI failover trigger: {str(e)[:50]}")

        # 2. Fallback: NTES
        start = time.perf_counter()
        try:
            raw_data = await self._safe_fetch_ntes(self.ntes_client.get_live_status, train_number)
            lat = (time.perf_counter() - start) * 1000
            from backend.core.metrics import jit_metrics
            
            if raw_data:
                jit_metrics.record_provider_call("ntes_scraper", True, lat)
                unified = ntes_to_unified(raw_data, train_number)
                if unified:
                    await cache_system.put(cache_key, unified.model_dump(), ttl=300)
                    return unified
            else:
                jit_metrics.record_provider_call("ntes_scraper", False, lat)
        except Exception as e:
            lat = (time.perf_counter() - start) * 1000
            from backend.core.metrics import jit_metrics
            jit_metrics.record_provider_call("ntes_scraper", False, lat)
            logger.error(f"NTES failover trigger: {e}")
        return None

    async def get_fare(self, train_number: str, travel_date: str, from_stn: str, to_stn: str, 
                       cls: str, quota: str = "GN") -> Optional[UnifiedFare]:
        cache_key = f"fare:{train_number}:{from_stn}:{to_stn}:{cls}:{quota}"
        cached = await cache_system.get(cache_key)
        if cached: return UnifiedFare(**cached) if isinstance(cached, dict) else cached
        if await self._is_budget_ok("RapidAPI"):
            try:
                fare = await self._safe_fetch_rapidapi(self.rapidapi_client.get_fare, train_number, travel_date, from_stn, to_stn, cls, quota)
                if fare:
                    asyncio.create_task(self._record_api_cost("RapidAPI"))
                    await cache_system.put(cache_key, fare.model_dump(), ttl=1800)
                    return fare
            except Exception as e: logger.warning(f"Fare lookup failed: {e}")
        return None

    async def get_pnr_status(self, pnr: str) -> Optional[UnifiedPNRStatus]:
        cache_key = f"pnr:{pnr}"
        cached = await cache_system.get(cache_key)
        if cached: return UnifiedPNRStatus(**cached) if isinstance(cached, dict) else cached
        if await self._is_budget_ok("RapidAPI"):
            try:
                pnr_data = await self._safe_fetch_rapidapi(self.rapidapi_client.get_pnr_status, pnr)
                if pnr_data:
                    asyncio.create_task(self._record_api_cost("RapidAPI"))
                    await cache_system.put(cache_key, pnr_data.model_dump(), ttl=3600)
                    return pnr_data
            except Exception as e: logger.warning(f"PNR lookup failed: {e}")
        return None

    async def get_schedule(self, train_number: str) -> Optional[UnifiedSchedule]:
        cache_key = f"schedule:{train_number}"
        cached = await cache_system.get(cache_key)
        if cached: return UnifiedSchedule(**cached) if isinstance(cached, dict) else cached
        if await self._is_budget_ok("RapidAPI"):
            try:
                schedule = await self._safe_fetch_rapidapi(self.rapidapi_client.get_schedule, train_number)
                if schedule:
                    asyncio.create_task(self._record_api_cost("RapidAPI"))
                    await cache_system.put(cache_key, schedule.model_dump(), ttl=86400)
                    return schedule
            except Exception as e: logger.warning(f"Schedule lookup failed: {e}")
        return None

    async def get_health(self) -> Dict[str, Any]:
        return {
            "rapidapi": self.rapidapi_breaker.state,
            "ntes": self.ntes_breaker.state
        }

    async def shutdown(self):
        await self.ntes_client.close_playwright()
        logger.info("Gateway shutdown.")

provider_gateway = ProviderGateway()
