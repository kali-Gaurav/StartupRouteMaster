from datetime import datetime, timedelta
import re


def validate_date(date_str: str) -> bool:
    """Validate date format YYYY-MM-DD and ensure it's in future."""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        if date_obj.date() < datetime.now().date():
            return False
        return True
    except ValueError:
        return False


def validate_phone(phone: str) -> bool:
    """Validate 10-digit phone number."""
    return bool(re.match(r"^\d{10}$", phone))


def validate_budget(budget: str) -> bool:
    """Validate budget category."""
    return budget in ["all", "economy", "standard", "premium"]


def validate_location(location: str) -> bool:
    """Validate location name."""
    return 1 <= len(location) <= 255 and location.isalpha()


def validate_time_format(time_str: str) -> bool:
    """Validate time format HH:MM."""
    try:
        datetime.strptime(time_str, "%H:%M")
        return True
    except ValueError:
        return False


def validate_transfer_window(window_min: int, window_max: int) -> bool:
    """Validate transfer window constraints."""
    return 0 < window_min <= window_max <= 1440


def validate_max_transfers(max_transfers: int) -> bool:
    """Validate max transfers constraint."""
    return 0 <= max_transfers <= 10


def validate_cost_range(cost: float) -> bool:
    """Validate cost is positive."""
    return cost > 0


def validate_operating_days(operating_days: str) -> bool:
    """Validate operating days string."""
    return len(operating_days) == 7 and all(c in "01" for c in operating_days)
