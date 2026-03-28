import logging
import time
import asyncio
from typing import Dict, Any, Optional, Tuple
from fastapi import Request, HTTPException
from services.multi_layer_cache import multi_layer_cache

logger = logging.getLogger("nexus.search.interceptor")

class NexusInterceptorDecision:
    def __init__(self, allowed: bool, code: str, message: str = "", metadata: Dict = None):
        self.allowed = allowed
        self.code = code
        self.message = message
        self.metadata = metadata or {}

class NexusSearchInterceptor:
    """
    [Task 18] Lightweight Interceptor (Layer 2.5).
    Standalone router-level gate to protect the search fiber from abuse/overload.
    """
    
    def __init__(self):
        self.cache = multi_layer_cache
        
    async def intercept(self, request: Request, source: str, destination: str) -> NexusInterceptorDecision:
        """Runs pre-computation checks to decide if we proceed to Graph Engine."""
        start_ts = time.perf_counter()
        client_ip = request.state.client_ip if hasattr(request.state, 'client_ip') else request.client.host
        
        try:
            # 1. Identity Verification (Tier 0)
            user_id = request.headers.get("x-user-id", "anonymous")
            
            # 2. High-Speed Rate Limit (Redis L1) [Task 18.3]
            rate_key = f"rl:search:{client_ip}"
            current_rate = await self.cache.get(rate_key) or 0
            if current_rate > 15: # Hard limit 15 req/min for search
                 logger.warning(f"🚫 [NEXUS:INTERCEPT] Rate Limit Exceeded for {client_ip}")
                 return NexusInterceptorDecision(False, "RATE_LIMIT", "Too many search requests. Please wait.")
            
            await self.cache.put(rate_key, current_rate + 1, ttl=60)

            # 3. Simple Fraud Scoring (Background) [Task 18.4]
            # [Gap] Currently using a simple heuristic; Phase 7 will add Deep Analysis
            is_suspicious = False
            if source == destination:
                 is_suspicious = True
                 logger.info(f"🚩 [NEXUS:INTERCEPT] Suspicious Request: Identical Src/Dst for {client_ip}")
            
            # 4. Cache Pre-Check (L0) [Task 18.5]
            # This is a hint to the route that we might have data
            # (Already handled better by the Gate, but we keep it here as a 'Skip' flag)
            
            latency_ms = (time.perf_counter() - start_ts) * 1000
            return NexusInterceptorDecision(
                allowed=not (is_suspicious and current_rate > 5), 
                code="PROCEED", 
                metadata={"interceptor_latency_ms": f"{latency_ms:.2f}"}
            )

        except Exception as e:
            logger.error(f"⚠️ [NEXUS:INTERCEPT] Fault: {e}")
            return NexusInterceptorDecision(True, "FALLBACK_PROCEED", "Interceptor fault detected, falling back to bypass.")

nexus_interceptor = NexusSearchInterceptor()
