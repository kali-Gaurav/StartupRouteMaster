from datetime import datetime, timedelta
from typing import Tuple
import re


def time_string_to_minutes(time_str: str) -> int:
    """Convert HH:MM or HH:MM:SS format to minutes from midnight."""
    # Match both HH:MM and HH:MM:SS formats
    match = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", time_str)
    if not match:
        raise ValueError(f"Invalid time format: {time_str}")
    hours, minutes = int(match.group(1)), int(match.group(2))
    # Validate ranges
    if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
        raise ValueError(f"Invalid time value: {time_str}")
    return hours * 60 + minutes


def minutes_to_time_string(minutes: int) -> str:
    """Convert minutes from midnight to HH:MM format."""
    hours = (minutes // 60) % 24
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def calculate_duration(start_time: str, end_time: str, next_day: bool = False) -> int:
    """
    Calculate duration in minutes between two times.
    If end time is earlier than start time, assume next day.
    """
    start_mins = time_string_to_minutes(start_time)
    end_mins = time_string_to_minutes(end_time)

    if end_mins < start_mins:
        end_mins += 24 * 60

    return end_mins - start_mins


def format_duration(minutes: int) -> str:
    """Format duration in minutes to human-readable string."""
    hours = minutes // 60
    mins = minutes % 60
    if hours == 0:
        return f"{mins}m"
    elif mins == 0:
        return f"{hours}h"
    else:
        return f"{hours}h {mins}m"


def get_day_of_week(date_str: str) -> int:
    """
    Get day of week from date string (YYYY-MM-DD).
    Returns 0=Monday, 1=Tuesday, ..., 6=Sunday
    """
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    return date_obj.weekday()


def operating_days_to_binary(day_str: str) -> str:
    """
    Convert operating days string to binary (Mon-Sun, 1=operates, 0=doesn't).
    Input format: "1111111" (index 0=Mon, 6=Sun)
    """
    if len(day_str) != 7:
        raise ValueError("Operating days must be 7 characters")
    return day_str


def is_operating_on_day(operating_days: str, date_str: str) -> bool:
    """Check if segment operates on given date."""
    day_of_week = get_day_of_week(date_str)
    operating_days_bin = operating_days_to_binary(operating_days)
    return operating_days_bin[day_of_week] == "1"


def add_minutes_to_time(time_str: str, minutes: int) -> str:
    """Add minutes to time string."""
    total_minutes = time_string_to_minutes(time_str) + minutes
    return minutes_to_time_string(total_minutes)


def time_window_overlap(window1: Tuple[int, int], window2: Tuple[int, int]) -> bool:
    """Check if two time windows overlap."""
    return window1[0] <= window2[1] and window2[0] <= window1[1]
