"""
Real-time ingestion service module.
Handles API data fetching, parsing, and database storage.
"""

from .api_client import RappidAPIClient, AsyncRappidAPIClient, get_active_trains
from .parser import (
    parse_delay,
    parse_timing,
    extract_train_update,
    detect_missed_connection,
    classify_delay_severity
)
from .ingestion_worker import LiveIngestionWorker, start_ingestion_service

__all__ = [
    "RappidAPIClient",
    "AsyncRappidAPIClient",
    "get_active_trains",
    "parse_delay",
    "parse_timing",
    "extract_train_update",
    "detect_missed_connection",
    "classify_delay_severity",
    "LiveIngestionWorker",
    "start_ingestion_service",
]
