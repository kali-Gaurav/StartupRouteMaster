import time
import logging
from typing import Optional, Tuple

logger = logging.getLogger("rate-limiter")

# Lua script for atomic Token Bucket implementation
# KEYS[1] : Rate limit key
# ARGV[1] : Tokens per second (refill rate)
# ARGV[2] : Bucket capacity (burst limit)
# ARGV[3] : Current timestamp (seconds)
TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local bucket = redis.call('hmget', key, 'tokens', 'last_refill')
local current_tokens = tonumber(bucket[1]) or capacity
local last_refill = tonumber(bucket[2]) or now

-- Refill tokens based on time passed
local delta = math.max(0, now - last_refill)
local refill = delta * rate
current_tokens = math.min(capacity, current_tokens + refill)

local allowed = 0
if current_tokens >= 1 then
    current_tokens = current_tokens - 1
    allowed = 1
end

redis.call('hmset', key, 'tokens', current_tokens, 'last_refill', now)
redis.call('expire', key, 60) -- Auto cleanup

return {allowed, current_tokens}
"""

class RedisTokenBucket:
    """
    Subtask 4.1: Distributed Token Bucket Rate Limiter.
    Uses Redis + Lua for atomic, cross-worker rate limiting.
    """
    def __init__(self, redis_client):
        self.redis = redis_client
        self._script = None

    async def is_allowed(self, key: str, rate: float, capacity: int) -> Tuple[bool, float]:
        """
        Checks if a request is allowed under the rate limit.
        Returns (is_allowed, remaining_tokens)
        """
        if not self.redis:
            return True, 1.0 # Fail open if Redis is down

        if not self._script:
            self._script = self.redis.register_script(TOKEN_BUCKET_LUA)

        try:
            now = time.time()
            res = await self._script(keys=[key], args=[rate, capacity, now])
            return bool(res[0]), float(res[1])
        except Exception as e:
            logger.error(f"Rate limit Lua error: {e}")
            return True, 1.0 # Fail open
