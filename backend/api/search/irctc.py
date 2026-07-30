"""
IRCTC Booking URL Builder
=========================
Converts a Route Master result into a pre-filled IRCTC search URL.
User clicks → lands on IRCTC with train, date, class pre-selected.

No API key needed. Just URL construction.
"""
from datetime import date
from typing import Optional
from urllib.parse import urlencode


# IRCTC train class codes
CLASS_MAP = {
    "SL": "SL",   "sl": "SL",
    "3A": "3A",   "3a": "3A",
    "2A": "2A",   "2a": "2A",
    "1A": "1A",   "1a": "1A",
    "CC": "CC",   "cc": "CC",
    "EC": "EC",   "ec": "EC",
    "2S": "2S",   "2s": "2S",
    "GN": "GN",   "gn": "GN",
}

IRCTC_BASE = "https://www.irctc.co.in/nget/train-search"


def build_irctc_url(
    from_station: str,
    to_station: str,
    travel_date: date,
    travel_class: Optional[str] = "SL",
    quota: str = "GN",
) -> str:
    """
    Build a pre-filled IRCTC train search URL.

    Args:
        from_station: Station code e.g. 'NDLS'
        to_station:   Station code e.g. 'BCT'
        travel_date:  Date of journey
        travel_class: Class code e.g. 'SL', '3A', '2A'
        quota:        Quota e.g. 'GN', 'TQ', 'LD'

    Returns:
        Full IRCTC URL string
    """
    irctc_class = CLASS_MAP.get(travel_class or "SL", "SL")
    date_str = travel_date.strftime("%d/%m/%Y")

    params = {
        "fromStn":    from_station.upper(),
        "toStn":      to_station.upper(),
        "jrnyDate":   date_str,
        "jrnyClass":  irctc_class,
        "jrnySrc":    "P",
        "returnDate": "",
        "ticketType": "E",
        "quota":      quota,
    }

    return f"{IRCTC_BASE}?{urlencode(params)}"


def build_irctc_url_for_train(
    train_number: str,
    from_station: str,
    to_station: str,
    travel_date: date,
    travel_class: Optional[str] = "SL",
) -> str:
    """
    Build IRCTC URL for a specific train number.
    Links directly to the train's availability page.
    """
    irctc_class = CLASS_MAP.get(travel_class or "SL", "SL")
    date_str = travel_date.strftime("%d/%m/%Y")

    params = {
        "trainNo":   train_number,
        "fromStn":   from_station.upper(),
        "toStn":     to_station.upper(),
        "jrnyDate":  date_str,
        "jrnyClass": irctc_class,
        "quota":     "GN",
        "ticketType": "E",
    }

    return f"{IRCTC_BASE}?{urlencode(params)}"
