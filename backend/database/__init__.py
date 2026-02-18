"""
Database configuration, models, and session management.
"""

from .config import Config
from .session import SessionLocal, engine_write, get_db, init_db, close_db, Base

# Backwards-compatible alias expected by some modules/tests
engine = engine_write
from .models import (
    Stop, Trip, Route, StopTime, Transfer, Calendar,
    CalendarDate, Agency, User, Booking, Payment
)

__all__ = [
    "Config",
    "SessionLocal",
    "engine_write",
    "engine",
    "get_db",
    "init_db",
    "close_db",
    "Base",
    "Stop",
    "Trip",
    "Route",
    "StopTime",
    "Transfer",
    "Calendar",
    "CalendarDate",
    "Agency",
    "User",
    "Booking",
    "Payment",
]
