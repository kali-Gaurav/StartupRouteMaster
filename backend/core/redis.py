import os
import redis
from database.config import Config

# Initialize synchronous redis client
redis_client = redis.from_url(
    Config.REDIS_URL,
    decode_responses=True,
    ssl_cert_reqs=None
)

# Initialize asynchronous redis client for fastapi-limiter/cache
import redis.asyncio as aioredis
async_redis_client = aioredis.from_url(
    Config.REDIS_URL,
    decode_responses=True,
    ssl_cert_reqs=None
)
