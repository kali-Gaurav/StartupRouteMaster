import time
import logging
from typing import Dict, Tuple
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger("routemaster.aegis.guardian")

class ScraperGuardianMiddleware(BaseHTTPMiddleware):
    """
    [P13] Intelligence Firewall.
    Protects the NIS (Nexus Intelligence Store) from automated weight-harvesting bots.
    """
    
    # In-memory storage (In prod, this should move to Redis/Upstash)
    _search_counters: Dict[str, Tuple[int, float]] = {} # ip -> (count, first_search_time)
    _BLOCK_THRESHOLD = 50 # Max searches without a revenue event
    _WINDOW = 86400 # 24 hours
    
    async def dispatch(self, request: Request, call_next):
        # Only protect the high-value search endpoint
        if "/search" not in request.url.path:
            return await call_next(request)

        client_ip = request.client.host
        
        # [P13] Behavioral Guard: Check for harvesting patterns
        is_bot = self._check_harvesting_pattern(client_ip)
        
        if is_bot:
            logger.warning(f"🚫 [AEGIS:GUARDIAN] Blocking harvesting bot from IP: {client_ip}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Aegis Interference Detected",
                    "code": "HARVESTING_BLOCKED",
                    "message": "Your search patterns indicate automated data harvesting. Please slow down or authenticate."
                }
            )

        # Record search activity
        self._record_search(client_ip)
        
        response = await call_next(request)
        return response

    def _record_search(self, ip: str):
        now = time.time()
        if ip not in self._search_counters:
            self._search_counters[ip] = (1, now)
        else:
            count, first_time = self._search_counters[ip]
            if now - first_time > self._WINDOW:
                # Reset window
                self._search_counters[ip] = (1, now)
            else:
                self._search_counters[ip] = (count + 1, first_time)

    def _check_harvesting_pattern(self, ip: str) -> bool:
        """Determines if the IP has crossed the bot threshold."""
        if ip not in self._search_counters:
            return False
        
        count, _ = self._search_counters[ip]
        return count > self._BLOCK_THRESHOLD

    @classmethod
    def record_revenue_event(cls, ip: str):
        """
        [Trust Loop] Reset the counter if the user actually pays/unlocks a route.
        """
        if ip in cls._search_counters:
            logger.info(f"🛡️ [AEGIS:GUARDIAN] User at {ip} verified as organic (Revenue Event). Resetting counters.")
            del cls._search_counters[ip]
