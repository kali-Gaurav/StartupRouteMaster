"""
Payment Utils - Task 2: UPI Deep Linking & URI Generation
Provides standardized methods for generating upi://pay links.
"""

import urllib.parse
from typing import Dict, Any

def generate_upi_uri(vpa: str, name: str, amount: float, transaction_note: str) -> str:
    """
    [2.1] Generates a standardized upi://pay URI.
    Format: upi://pay?pa=<vpa>&pn=<name>&am=<amount>&cu=INR&tn=<note>
    """
    base_url = "upi://pay"
    params = {
        "pa": vpa,
        "pn": name,
        "am": f"{amount:.2f}",
        "cu": "INR",
        "tn": transaction_note
    }
    
    # [2.9] URL Encoding for special characters
    query_string = urllib.parse.urlencode(params)
    return f"{base_url}?{query_string}"

def get_transaction_note(booking_id: str) -> str:
    """
    [2.5] & [4.1] Transaction Note Serialization: RM_<ShortID>
    Uses short ID to ensure it fits in bank SMS and UI (max 50 chars).
    """
    short_id = str(booking_id).split('-')[0].upper()
    return f"RM_{short_id}"
