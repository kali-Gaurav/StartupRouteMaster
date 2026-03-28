import logging
import time
import hashlib
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException
from core.container import container
from core.auth.utils import AUTH_SECRET

logger = logging.getLogger("nexus.sybil")

class SybilProtectionManager:
    """
    [Task 110] Sybil Protection Service.
    Prevents high-velocity scraping by enforcing 'Challenges' on suspicious actors.
    """
    def __init__(self, challenge_threshold: float = 0.8):
        self.challenge_threshold = challenge_threshold
        
    async def check_challenge_required(self, user_id: str, request: Request) -> bool:
        """Determines if a challenge is currently required for this user."""
        cache = await container.get("cache")
        if not cache or not cache.redis:
            return False
            
        # Check if they have an active 'Challenge Required' flag
        flag = await cache.redis.get(f"auth:sybil:challenge:{user_id}")
        if flag:
            return True
        return False

    async def issue_challenge_required(self, user_id: str):
        """Forces a challenge on the user for their next request."""
        cache = await container.get("cache")
        if cache and cache.redis:
            await cache.redis.set(f"auth:sybil:challenge:{user_id}", "1", ex=300) # 5m window

    async def verify_challenge_solution(self, user_id: str, solution: str) -> bool:
        """
        Verify a lightweight PoW or HMAC-based challenge response.
        In this version, a simple HMAC verify of (user_id + salt).
        """
        # [Placeholder for actual PoW verification]
        # For Phase 11, we verify a signature of the current minute to simplify client-side dev
        expected = hashlib.sha256(f"{user_id}:{AUTH_SECRET}:{int(time.time() / 60)}".encode()).hexdigest()
        if solution == expected:
            cache = await container.get("cache")
            if cache and cache.redis:
                # Issue a SYBIL_TOKEN (bypass) for 1 hour
                await cache.redis.set(f"auth:sybil:bypass:{user_id}", "1", ex=3600)
                await cache.redis.delete(f"auth:sybil:challenge:{user_id}")
            return True
        return False

    async def is_bypassed(self, user_id: str) -> bool:
        cache = await container.get("cache")
        if not cache or not cache.redis:
            return False
        return await cache.redis.get(f"auth:sybil:bypass:{user_id}") is not None

sybil_manager = SybilProtectionManager()
