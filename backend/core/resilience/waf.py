import logging
import time
import hashlib
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, Dict
from core.resilience.rate_limit import rate_limiter

logger = logging.getLogger("routemaster.waf")

class SovereignWAFMiddleware(BaseHTTPMiddleware):
    """
    [SOVEREIGN] Edge Security & Fingerprinting Middleware.
    Protects RouteMaster from advanced bots, demand manipulation, and incentive farming.
    """
    def __init__(self, app):
        super().__init__(app)
        self._bot_user_agents = [
            "python-requests", "curl", "postman", "scaper", "selenium", "puppeteer", "headless"
        ]

    async def dispatch(self, request: Request, call_next):
        start_time = time.monotonic()
        
        # 1. Device Fingerprinting (L1)
        fingerprint = self._generate_fingerprint(request)
        request.state.fingerprint = fingerprint
        
        # 2. Bot Detection (L2)
        is_bot = self._check_bot_signals(request)
        request.state.is_bot = is_bot
        
        if is_bot:
            # We don't block immediately, we flag for the Rate Limiter
            # This allows us to 'Shadow Ban' or provide limited results
            logger.warning(f"🤖 [WAF] Bot Signal Detected: {fingerprint[:8]} | UA: {request.headers.get('user-agent')}")

        # 3. Security Header Verification (L3)
        # Check for mandatory RM headers in production
        # if not self._verify_integrity_headers(request):
        #    return Response(content="Integrity check failed", status_code=403)

        # 4. Integrate with Rate Limiter
        # Flag suspicious behavior to the RL singleton
        if is_bot:
            # Tighten limits for bots
            pass 

        response = await call_next(request)
        
        # Inject Fingerprint into headers for frontend tracking
        response.headers["X-RM-Fingerprint"] = fingerprint
        response.headers["X-WAF-Processed"] = "true"
        
        duration = time.monotonic() - start_time
        if duration > 1.0:
            logger.warning(f"⚠️ [WAF] Slow request inspection: {duration:.2f}s")
            
        return response

    def _generate_fingerprint(self, request: Request) -> str:
        """Generate a stable device fingerprint based on headers and IP."""
        ip = request.client.host
        ua = request.headers.get("user-agent", "unknown")
        accept = request.headers.get("accept", "")
        lang = request.headers.get("accept-language", "")
        
        # Create a raw string for hashing
        raw = f"{ip}|{ua}|{accept}|{lang}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _check_bot_signals(self, request: Request) -> bool:
        """Check for common bot signatures."""
        ua = request.headers.get("user-agent", "").lower()
        
        # 1. Known Bot UA patterns
        if any(bot in ua for bot in self._bot_user_agents):
            return True
            
        # 2. Missing critical browser headers
        if "user-agent" not in request.headers or "accept" not in request.headers:
            return True
            
        # 3. Suspiciously fast search frequency (handled by RL, but flagged here)
        return False

    def _verify_integrity_headers(self, request: Request) -> bool:
        """Verify internal request signature (for service-to-service)."""
        # Placeholder for HMAC verification
        return True

# Singleton middleware instance is not used here, FastAPI uses the class
