import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from services.multi_layer_cache import multi_layer_cache

logger = logging.getLogger("nexus.search.gate")

class NexusLatencyGate:
    """[Task 11] Fast-Path Search Responder.
    Orchestrates L1 (Memory) and L2 (Redis) lookup BEFORE triggering Graph-Search.
    """
    
    def __init__(self):
        self.cache = multi_layer_cache
        
    async def get_cached_search(self, 
                                src: str, 
                                dst: str, 
                                travel_date: str, 
                                persona: str = "ECONOMY") -> Optional[List[Any]]:
        """Attempt zero-latency retrieval from the high-integrity fabric."""
        # Standardized Key: search:v3:{src}:{dst}:{date}:{persona}
        cache_key = f"search:v3:{src.upper()}:{dst.upper()}:{travel_date}:{persona}"
        
        try:
             # Fast L1 check happens inside MultiLayerCache
             cached_data = await self.cache.get(cache_key)
             if cached_data:
                  logger.info(f"⚡ [NEXUS:GATE] Fast-Path HIT: {cache_key}")
                  return cached_data
             return None
        except Exception as e:
             logger.warning(f"⚠️ [NEXUS:GATE] Cache Fabric probe failed: {e}")
             return None

    async def commit_search(self, 
                          src: str, 
                          dst: str, 
                          travel_date: str, 
                          results: List[Any], 
                          persona: str = "ECONOMY",
                          ttl: int = 1800): # 30 mins default
        """Synchronize successful search results to the Performance Fabric."""
        cache_key = f"search:v3:{src.upper()}:{dst.upper()}:{travel_date}:{persona}"
        try:
             await self.cache.put(cache_key, results, ttl=ttl)
             logger.debug(f"📝 [NEXUS:GATE] Committing to L1/L2: {cache_key}")
        except Exception as e:
             logger.error(f"🚨 [NEXUS:GATE] Fabric Commit Failed: {e}")

nexus_latency_gate = NexusLatencyGate()
