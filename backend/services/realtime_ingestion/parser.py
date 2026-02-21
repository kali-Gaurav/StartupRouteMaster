"""
Delay parsing and data extraction utilities for real-time train API responses.

This module handles:
- Parsing delay strings from API responses
- Extracting and normalizing timing data
- Status classification
- Data validation
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
import re


def parse_delay(delay_str: str) -> int:
    """
    Parse delay string from API response and return delay in minutes.
    
    Handles:
    - "On Time" -> 0
    - "23min" -> 23
    - "1h 30min" -> 90
    - Empty/None -> 0
    
    Args:
        delay_str: Delay string from API
        
    Returns:
        Delay in minutes as integer
    """
    if not delay_str or delay_str is None:
        return 0
    
    delay_str = delay_str.strip()
    
    if "On Time" in delay_str or delay_str == "":
        return 0
    
    # Extract minutes component
    total_minutes = 0
    
    # Check for hours
    hours_match = re.search(r'(\d+)\s*h(?:our(?:s)?)?', delay_str, re.IGNORECASE)
    if hours_match:
        total_minutes += int(hours_match.group(1)) * 60
    
    # Check for minutes
    minutes_match = re.search(r'(\d+)\s*m(?:in(?:ute(?:s)?)?)?', delay_str, re.IGNORECASE)
    if minutes_match:
        total_minutes += int(minutes_match.group(1))
    
    return total_minutes


def parse_timing(timing_str: str, scheduled_offset: int = 0) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Parse timing string from API response (format: "HH:MM HH:MM" - scheduled:actual).
    
    Args:
        timing_str: Timing string (e.g., "16:16 16:05")
        scheduled_offset: Days offset if crossing midnight
        
    Returns:
        Tuple of (scheduled_time, actual_time) as datetime objects
        
    Examples:
        "16:16 16:05" -> (16:16, 16:05)
        "23:30 00:15" -> (23:30 today, 00:15 next day)
    """
    if not timing_str or timing_str == "-" or "Destination" in timing_str or "Source" in timing_str:
        return None, None
    
    # Split scheduled and actual timing
    parts = timing_str.split()
    
    if len(parts) < 1:
        return None, None
    
    scheduled_str = parts[0]
    actual_str = parts[1] if len(parts) > 1 else parts[0]
    
    try:
        # Create datetime objects
        now = datetime.now()
        base_date = now.date() + timedelta(days=scheduled_offset)
        
        scheduled_hours, scheduled_mins = map(int, scheduled_str.split(':'))
        scheduled = datetime.combine(base_date, datetime.min.time()).replace(
            hour=scheduled_hours, minute=scheduled_mins
        )
        
        actual_hours, actual_mins = map(int, actual_str.split(':'))
        actual_day = base_date
        
        # Handle day boundary crossing (if actual time < scheduled time, assume next day)
        if actual_hours < scheduled_hours or (actual_hours == scheduled_hours and actual_mins < scheduled_mins):
            if timing_str.endswith("00:"):  # Likely crossed midnight
                actual_day = base_date + timedelta(days=1)
        
        actual = datetime.combine(actual_day, datetime.min.time()).replace(
            hour=actual_hours, minute=actual_mins
        )
        
        return scheduled, actual
    
    except (ValueError, IndexError):
        return None, None


def extract_train_update(api_response: Dict[str, Any], train_number: str) -> Dict[str, Any]:
    """
    Extract structured data from Rappid API response into standardized format.
    
    Args:
        api_response: Full API response dict
        train_number: Train number for context
        
    Returns:
        Structured updates ready for database storage
    """
    updates = []
    
    if not api_response.get("success"):
        return updates
    
    data_array = api_response.get("data", [])
    updated_time_str = api_response.get("updated_time", "")
    
    # Parse when data was updated
    recorded_at = datetime.now()
    if "ago" in updated_time_str:
        # "Updated 15min ago" -> subtract minutes
        minutes_match = re.search(r'(\d+)\s*min', updated_time_str)
        if minutes_match:
            minutes = int(minutes_match.group(1))
            recorded_at = recorded_at - timedelta(minutes=minutes)
    
    for station_data in data_array:
        try:
            station_code = station_data.get("station_name", "").upper()
            distance_str = station_data.get("distance", "-")
            distance_km = None
            
            # Parse distance
            if distance_str != "-":
                dist_match = re.search(r'(\d+(?:\.\d+)?)', distance_str)
                if dist_match:
                    distance_km = float(dist_match.group(1))
            
            # Parse timings
            timing_str = station_data.get("timing", "")
            scheduled_arrival, actual_arrival = parse_timing(timing_str)
            
            # Parse delay
            delay_str = station_data.get("delay", "")
            delay_minutes = parse_delay(delay_str)
            
            # Determine status
            status = "On Time"
            if delay_minutes > 0:
                status = "Delayed"
            elif station_data.get("status") == "Cancelled":
                status = "Cancelled"
            elif station_data.get("is_current_station"):
                status = "Running"
            
            update = {
                "train_number": train_number,
                "station_code": station_code,
                "station_name": station_data.get("station_name", ""),
                "sequence": len(updates),  # Approximate sequence
                "distance_km": distance_km,
                "scheduled_arrival": scheduled_arrival,
                "actual_arrival": actual_arrival,
                "delay_minutes": delay_minutes,
                "platform": station_data.get("platform", "").strip() or None,
                "halt_minutes": _parse_halt(station_data.get("halt", "")),
                "status": status,
                "is_current_station": station_data.get("is_current_station", False),
                "recorded_at": recorded_at,
                "source": "rappid_api",
            }
            
            updates.append(update)
        
        except Exception as e:
            # Log parsing error but continue with other stations
            print(f"⚠️ Error parsing station data: {e}")
            continue
    
    return updates


def _parse_halt(halt_str: str) -> Optional[int]:
    """Parse halt duration string to minutes."""
    if not halt_str or halt_str in ["-", "Source", "Destination"]:
        return None
    
    try:
        minutes_match = re.search(r'(\d+)\s*min', halt_str, re.IGNORECASE)
        if minutes_match:
            return int(minutes_match.group(1))
    except (ValueError, AttributeError):
        pass
    
    return None


def detect_missed_connection(
    arrival_delay: int,
    platform_change: bool,
    transfer_buffer_minutes: int
) -> Tuple[bool, str]:
    """
    Detect if a connection is likely to be missed.
    
    Args:
        arrival_delay: Current arrival delay in minutes
        platform_change: Whether platform changed
        transfer_buffer_minutes: Planned buffer time in minutes
        
    Returns:
        Tuple of (missed: bool, reason: str)
    """
    # Basic heuristic: if delay exceeds buffer, connection is risky
    if arrival_delay > transfer_buffer_minutes:
        reason = f"Delay ({arrival_delay}min) exceeds transfer buffer ({transfer_buffer_minutes}min)"
        return True, reason
    
    # Platform changes add risk
    if platform_change and arrival_delay > transfer_buffer_minutes * 0.5:
        reason = f"Platform change + delay ({arrival_delay}min) risky with buffer ({transfer_buffer_minutes}min)"
        return True, reason
    
    return False, "Connection viable"


def classify_delay_severity(delay_minutes: int) -> str:
    """
    Classify delay severity for display and ranking.
    
    Args:
        delay_minutes: Delay in minutes
        
    Returns:
        Severity level: 'on_time', 'minor', 'moderate', 'severe'
    """
    if delay_minutes == 0:
        return "on_time"
    elif delay_minutes <= 5:
        return "minor"
    elif delay_minutes <= 15:
        return "moderate"
    else:
        return "severe"
