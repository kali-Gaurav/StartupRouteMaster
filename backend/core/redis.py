import os
import redis
from database.config import Config

# Initialize synchronous redis client
redis_client = redis.from_url(
    Config.REDIS_URL,
    decode_responses=True,
    ssl_cert_reqs=None,
    socket_timeout=5.0,
    socket_connect_timeout=5.0,
    retry_on_timeout=True,
    max_connections=50 # Increased pool size
)

# Initialize asynchronous redis client for fastapi-limiter/cache
import redis.asyncio as aioredis
async_redis_client = aioredis.from_url(
    Config.REDIS_URL,
    decode_responses=True,
    ssl_cert_reqs=None,
    socket_timeout=5.0,
    socket_connect_timeout=5.0,
    max_connections=100 # Optimized for concurrent async requests
)
