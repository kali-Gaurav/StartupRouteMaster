"""
Dynamic Routing Logic - Heuristics and Waiting Time Calculations
Part of the 10X Evolution Plan (Task 1).
"""

import math
from datetime import datetime, time, timedelta
from typing import Tuple, Optional, Union, Any
from functools import lru_cache
from core.data_utils.structures import DynamicWaitConfig, TransferWindow, SearchPhase

def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points on the earth."""
    R = 6371  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) * math.sin(dlon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def calculate_journey_duration_heuristic(distance_km: float, avg_speed_kmh: float = 55.0) -> int:
    """
    Estimate journey duration in minutes based on distance and average speed.
    Subtask 1.2.
    """
    if distance_km <= 0:
        return 0
    hours = distance_km / avg_speed_kmh
    return int(hours * 60)

from core.engines.hubs import MEGA_HUBS, MAJOR_HUBS, REGIONAL_HUBS

@lru_cache(maxsize=1024)
def get_station_size_modifier(station_code: str) -> float:
    """
    Returns a multiplier for the maximum wait time based on station hierarchy.
    """
    if station_code in MEGA_HUBS:
        return 1.8  # Large hubs (DDU, NDLS) - huge wait tolerance
    if station_code in MAJOR_HUBS:
        return 1.4  # Solid junctions
    if station_code in REGIONAL_HUBS:
        return 1.15 # Small junctions
    return 1.0

from core.data_utils.structures import DynamicWaitConfig, TransferWindow, SearchPhase

def compute_dynamic_window(
    journey_duration_mins: int, 
    config: DynamicWaitConfig, 
    station_code: Optional[str] = None,
    phase: SearchPhase = SearchPhase.MODERATE
) -> Tuple[int, int]:
    """
    Compute the min and max wait window based on the journey duration and search phase.
    Uses a beta-curve for non-linear scaling of max wait.
    Subtask 1.3 / 1.11 / 2.4.
    """
    # Base min wait is always from config
    min_wait = config.min_wait_minutes

    # Max wait scales with journey duration: max_wait = base_max * (duration / 1440)^beta
    # Audit Fix: ensure beta is not None
    beta = config.beta if config.beta is not None else 1.5
    scale_factor = math.pow(max(journey_duration_mins, 60) / 1440.0, beta)

    dynamic_max = int(config.max_wait_minutes * scale_factor)
    
    # Apply phase multiplier
    phase_mult = config.phase_multipliers.get(phase, 1.0)
    dynamic_max = int(dynamic_max * phase_mult)
    
    # Apply station size modifier
    if station_code:
        dynamic_max = int(dynamic_max * get_station_size_modifier(station_code))
    
    # Clamp to boundaries
    # Relaxed phase allows much larger windows
    upper_bound_mult = 3 if phase != SearchPhase.RELAXED else 6
    dynamic_max = max(min_wait + 30, min(dynamic_max, config.max_wait_minutes * upper_bound_mult))
    
    return min_wait, dynamic_max

def is_valid_transfer(
    arrival_time: Union[datetime, int], 
    departure_time: Union[datetime, int], 
    journey_so_far_mins: int, 
    config: DynamicWaitConfig,
    station_code: Optional[str] = None,
    transfer_penalty: int = 0,
    phase: SearchPhase = SearchPhase.MODERATE
) -> bool:
    """
    Comprehensive transfer validation including dynamic size-aware windows.
    Task 13: Refined size & penalty logic.
    """
    if isinstance(arrival_time, int) and isinstance(departure_time, int):
        wait_mins = (departure_time - arrival_time) % 1440
    elif isinstance(arrival_time, datetime) and isinstance(departure_time, datetime):
        wait_mins = (departure_time - arrival_time).total_seconds() / 60
    else:
        raise TypeError("arrival_time and departure_time must be both int or both datetime")
    
    # [Task 13] Dynamic Min Wait Budget based on Station Size
    station_min_buffer = 15 # Standard
    if station_code in MEGA_HUBS:
        station_min_buffer = 40 # Need time in NDLS/HWH to switch platforms
    elif station_code in MAJOR_HUBS:
        station_min_buffer = 25
    elif station_code in REGIONAL_HUBS:
        station_min_buffer = 15
    else:
        station_min_buffer = 10 # Tiny station, walk across
        
    # [Yield Enhancement] If search is relaxed, we cut minimum buffer by half
    if phase == SearchPhase.RELAXED:
        station_min_buffer = max(10, station_min_buffer // 2)

    # 1. Basic window check
    min_w, max_w = compute_dynamic_window(journey_so_far_mins, config, station_code, phase)
    
    # Apply station-specific minimum
    effective_min = max(min_w + transfer_penalty, station_min_buffer)
    
    # [Massive Yield Optimization] Increase floor for dynamic_max for short legs aggressively. In India people often wait 6-10 hours.
    max_w = max(max_w, 600 if phase != SearchPhase.STRICT else 300)
    
    if wait_mins < effective_min or wait_mins > max_w:
        # logger.debug(f"Transfer Rejected (Window): wait={wait_mins}, min={effective_min}, max={max_w}, station={station_code}")
        return False
        
    # 2. Waiting Ratio check
    if phase == SearchPhase.RELAXED: max_ratio = 5.0
    elif phase == SearchPhase.MODERATE: max_ratio = 4.0
    else: max_ratio = 2.0 
        
    if journey_so_far_mins > 0:
        ratio = wait_mins / (journey_so_far_mins + wait_mins)
        if ratio > max_ratio:
            return False
            
    return True

def is_night_time(check_time: time) -> bool:
    """Check if a given time falls in the 'Night' period (01:00-04:00)."""
    start = time(1, 0)
    end = time(4, 0)
    return start <= check_time <= end

def calculate_transfer_comfort(arrival_time: datetime, departure_time: datetime, config: DynamicWaitConfig) -> float:
    """
    Calculate a comfort score for a transfer based on waiting time and night penalties.
    Subtask 1.13 / 1.14 (Preview).
    """
    wait_mins = (departure_time - arrival_time).total_seconds() / 60
    score = 1.0
    
    # Check for night wait
    current = arrival_time
    while current < departure_time:
        if is_night_time(current.time()):
            score *= (1.0 / config.night_penalty_multiplier)
            break # Apply once
        current += timedelta(minutes=30)
        
    # Wait duration score: ideal wait is 45-120 mins
    if wait_mins < 30: score *= 0.8 # Tight
    if wait_mins > 300: score *= 0.5 # Too long
    
    return round(score, 2)
