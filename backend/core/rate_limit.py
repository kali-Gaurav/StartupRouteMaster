from fastapi_limiter import FastAPILimiter
from core.redis import async_redis_client
import logging

logger = logging.getLogger(__name__)

async def init_rate_limiter():
    """
    Initialize FastAPILimiter using the shared async Redis client.
    """
    try:
        await FastAPILimiter.init(async_redis_client)
        logger.info("FastAPI-Limiter initialized with Redis.")
    except Exception as e:
        logger.error(f"Failed to initialize FastAPI-Limiter: {e}")
        # In production, this might be a critical failure depending on requirements.
