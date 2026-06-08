"""
[Nexus Fix] Bridge for Multi-Layer Cache imports.
This resolves the ModuleNotFoundError across the project by re-exporting 
the multi_layer_cache singleton and its associated structures.
"""
from .cache.multi_layer import (
    multi_layer_cache, 
    RouteQuery, 
    AvailabilityQuery, 
    PROCESS_ID,
    DiscoveryQuery,
    TTL_ROUTE_SEARCH
)

__all__ = [
    "multi_layer_cache", 
    "RouteQuery", 
    "AvailabilityQuery", 
    "PROCESS_ID",
    "DiscoveryQuery",
    "TTL_ROUTE_SEARCH"
]
