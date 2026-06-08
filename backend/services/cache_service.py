"""
[Nexus Fix] Bridge for Cache Service imports.
"""
from .cache.manager import CacheService, CacheServiceMetrics, cache_service

__all__ = ["CacheService", "CacheServiceMetrics", "cache_service"]
