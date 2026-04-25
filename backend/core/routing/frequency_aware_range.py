import logging
from typing import Dict, Any, Tuple
from functools import lru_cache
from datetime import datetime, timedelta

logger = logging.getLogger("frequency-sizer")

# [Task 3] Cache for frequency metrics to avoid repeated calculations
_frequency_cache: Dict[int, Tuple[int, float]] = {}
_cache_timestamp = datetime.now()
_CACHE_TTL_SECONDS = 3600  # Refresh every hour

def _should_refresh_cache() -> bool:
    """Check if frequency cache needs refresh"""
    global _cache_timestamp
    if datetime.now() - _cache_timestamp > timedelta(seconds=_CACHE_TTL_SECONDS):
        _cache_timestamp = datetime.now()
        _frequency_cache.clear()
        return True
    return False

def get_frequency_aware_sizer(stop_id: int, graph: Any) -> int:
    """
    [Task 3] Frequency-Aware Sizing - Dynamically adjusts search depth based on train density.
    
    Higher density hubs (NDLS, HWH) get larger frontiers to capture diverse options.
    Lower density stops get smaller frontiers for efficiency.
    
    Frontier Size Scaling:
    - 0-30 deps: 3 routes (remote stations, fewer options)
    - 31-100 deps: 5 routes (secondary hubs)
    - 101-300 deps: 10 routes (major hubs)
    - 301-600 deps: 15 routes (super-hubs like NDLS, HWH)
    - 600+ deps: 20 routes (exceptional mega-hubs)
    
    Also computes frequency density (deps per hour) for adaptive timeouts and caching.
    """
    if not graph or not graph.snapshot:
        logger.debug(f"[Task 3] No graph/snapshot for stop {stop_id}, returning default size 5")
        return 5
    
    # [Task 3] Check cache first
    if stop_id in _frequency_cache:
        size, density = _frequency_cache[stop_id]
        logger.debug(f"[Task 3] Cache hit for stop {stop_id}: {size} routes, density {density:.1f} deps/hour")
        return size
    
    try:
        stop_idx = graph.snapshot._stop_id_map.get(stop_id)
        if stop_idx is None:
            logger.debug(f"[Task 3] Stop {stop_id} not in map, returning default size 5")
            return 5
        
        # Get departure count for this stop
        _, count = graph.snapshot._departures_index[stop_idx]
        
        # [Task 3] Enhanced Scaling Logic with density calculation
        if count < 30:
            size = 3
            category = "remote"
        elif count < 100:
            size = 5
            category = "secondary"
        elif count < 300:
            size = 10
            category = "major"
        elif count < 600:
            size = 15
            category = "super-hub"
        else:
            size = 20
            category = "mega-hub"
        
        # [Task 3] Calculate frequency density (departures per hour)
        # Assuming roughly 24-hour schedule window in snapshot
        frequency_density = count / 24.0
        
        logger.debug(f"[Task 3] Stop {stop_id}: {count} deps ({frequency_density:.1f}/hour), "
                    f"category={category}, frontier_size={size}")
        
        # [Task 3] Cache result
        _frequency_cache[stop_id] = (size, frequency_density)
        
        return size
        
    except Exception as e:
        logger.warning(f"[Task 3] Error computing frequency for stop {stop_id}: {e}")
        return 5

def get_frequency_category(stop_id: int, graph: Any) -> str:
    """
    [Task 3] Get human-readable frequency category for a stop.
    Useful for debugging and logging.
    """
    if not graph or not graph.snapshot:
        return "unknown"
    
    try:
        stop_idx = graph.snapshot._stop_id_map.get(stop_id)
        if stop_idx is None:
            return "unknown"
        
        _, count = graph.snapshot._departures_index[stop_idx]
        
        if count < 30:
            return "remote"
        elif count < 100:
            return "secondary"
        elif count < 300:
            return "major"
        elif count < 600:
            return "super-hub"
        else:
            return "mega-hub"
    except:
        return "unknown"

def get_adaptive_timeout(source_stop_id: int, dest_stop_id: int, graph: Any, 
                        base_timeout_ms: int = 5000) -> int:
    """
    [Task 3] Compute adaptive timeout based on source and destination frequencies.
    
    High-frequency routes can afford tighter timeouts.
    Low-frequency routes need more time for exploration.
    """
    try:
        source_size = get_frequency_aware_sizer(source_stop_id, graph)
        dest_size = get_frequency_aware_sizer(dest_stop_id, graph)
        
        # Combined frequency factor (1.0 for mega-hubs, 0.5 for remote)
        frequency_factor = (source_size * dest_size) / (20 * 20)
        
        # Adaptive timeout: reduce for high-frequency, extend for low-frequency
        adaptive_timeout = int(base_timeout_ms / (0.5 + frequency_factor))
        
        logger.debug(f"[Task 3] Adaptive timeout: {adaptive_timeout}ms "
                    f"(source_size={source_size}, dest_size={dest_size}, factor={frequency_factor:.2f})")
        
        return max(2000, min(adaptive_timeout, 15000))  # Clamp to 2-15 seconds
    except Exception as e:
        logger.warning(f"[Task 3] Error computing adaptive timeout: {e}")
        return base_timeout_ms
