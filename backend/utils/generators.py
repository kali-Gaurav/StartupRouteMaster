"""
Generators for PNR, confirmation numbers, and other identifiers.
"""
import random
import string
from datetime import datetime

def generate_pnr() -> str:
    """
    Generate an Indian Railway-style PNR (Passenger Name Record).
    Format: 6 alphanumeric characters.
    Example: ABC1234
    
    Structure:
    - First 3 characters: Random letters (A-Z)
    - Last 3 characters: Random digits (0-9)
    """
    letters = ''.join(random.choices(string.ascii_uppercase, k=3))
    digits = ''.join(random.choices(string.digits, k=3))
    return letters + digits


def generate_booking_reference() -> str:
    """Generate a unique booking reference ID."""
    timestamp = int(datetime.utcnow().timestamp())
    random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"BK{timestamp}{random_suffix}"


def generate_confirmation_number() -> str:
    """Generate a confirmation number for payment/booking."""
    return ''.join(random.choices(string.digits, k=10))


def validate_pnr_format(pnr: str) -> bool:
    """Validate PNR format (6 alphanumeric characters)."""
    if not pnr or len(pnr) != 6:
        return False
    return pnr[:3].isalpha() and pnr[3:].isdigit()
