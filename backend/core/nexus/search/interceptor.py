import logging
import time
import asyncio
from typing import Dict, Any, Optional, Tuple
from fastapi import Request, HTTPException
from services.multi_layer_cache import multi_layer_cache
from services.sovereign_waf_service import sovereign_waf

logger = logging.getLogger("nexus.search.interceptor")

class NexusInterceptorDecision:
    allowed: bool
    code: str
    message: str
    metadata: Dict[str, Any]

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
            # 1. Sovereign WAF Deep Inspection [PHASE 7]
            waf_result = await sovereign_waf.inspect_request(request, source, destination)
            if not waf_result["allowed"]:
                logger.warning(f"🛡️ [NEXUS:INTERCEPT] Sovereign WAF Block: {waf_result['reason']} for {client_ip}")
                return NexusInterceptorDecision(False, "WAF_BLOCK", f"Security restriction: {waf_result['reason']}", metadata=waf_result)

            # 2. Legacy Rate Limit Fallback (L1) [Task 18.3]
            rate_key = f"rl:search:{client_ip}"
            current_rate = await self.cache.get(rate_key) or 0
            if current_rate > 30: # Relaxed slightly since WAF handles more precision
                 logger.warning(f"🚫 [NEXUS:INTERCEPT] Legacy Rate Limit Exceeded for {client_ip}")
                 return NexusInterceptorDecision(False, "RATE_LIMIT", "Too many search requests. Please wait.")
            
            await self.cache.put(rate_key, current_rate + 1, ttl=60)

            # 3. Anomaly Scoring Integration
            is_suspicious = waf_result["threat_score"] > 0.5
            
            latency_ms = (time.perf_counter() - start_ts) * 1000
            return NexusInterceptorDecision(
                allowed=True, 
                code="PROCEED", 
                metadata={
                    "interceptor_latency_ms": f"{latency_ms:.2f}",
                    "waf": waf_result
                }
            )

        except Exception as e:
            logger.error(f"⚠️ [NEXUS:INTERCEPT] Fault: {e}")
            return NexusInterceptorDecision(True, "FALLBACK_PROCEED", "Interceptor fault detected, falling back to bypass.")

nexus_interceptor = NexusSearchInterceptor()
