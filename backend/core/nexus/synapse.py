import logging
from typing import Dict, List, Any, Optional
from collections import OrderedDict
from datetime import datetime, timedelta
from core.data_structures import Route

logger = logging.getLogger("nexus.synapse")

class CerebralCache:
    """
    [Atomic Task 1] The Memory Palace (Unified Synapse).
    In-memory LRU cache for high-frequency hub segments and pre-calculated routes.
    """
    
    _cache: OrderedDict = OrderedDict()
    _MAX_SIZE = 1000 # Store 1000 high-value segments
    
    @classmethod
    def get_segment(cls, src: str, dst: str, date_str: str) -> Optional[List[Any]]:
        key = f"{src}:{dst}:{date_str}"
        if key in cls._cache:
            # Move to end (LRU)
            cls._cache.move_to_end(key)
            return cls._cache[key]
        return None

    @classmethod
    def set_segment(cls, src: str, dst: str, date_str: str, routes: List[Any]):
        key = f"{src}:{dst}:{date_str}"
        if len(cls._cache) >= cls._MAX_SIZE:
            cls._cache.popitem(last=False)
        cls._cache[key] = routes
        cls._cache.move_to_end(key)

class SynapseOptimizer:
    """
    [Task 2] Viewport-Aware Response Slicing.
    Decides hydration depth based on result rank and intelligence.
    """
    
    @staticmethod
    def get_hydration_level(rank: int, score: float) -> str:
        """
        Determines how much 'meat' to put on the route.
        """
        if rank < 5:
            return "FULL" # Top results get everything (logos, train names, detail)
        if rank < 20 or score > 0.8:
            return "STANDARD" # Moderate results get basic info
        return "SHADOW" # Background results get minimal IDs (Revealed on hover)

    @staticmethod
    def apply_intelligent_pruning(routes: List[Any], budget: float) -> List[Any]:
        """
        Prunes results that are statistically unlikely to be converted.
        """
        if not routes: return []
        if budget > 0.8: return routes # High budget, show everything
        
        def get_score(r):
            if isinstance(r, dict):
                return r.get("score", 0.0)
            return getattr(r, "score", 0.0)

        # Prune very high cost or very low probability
        return [r for r in routes if get_score(r) > 0.3]
