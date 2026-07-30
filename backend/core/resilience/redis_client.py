"""
[Nexus Fix] Bridge for Redis client imports.
This resolves the ModuleNotFoundError by re-exporting the Redis clients from core.infrastructure.
"""
from core.infrastructure.redis_manager import async_redis_client, redis_client

__all__ = ["async_redis_client", "redis_client"]
