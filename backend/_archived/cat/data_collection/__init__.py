"""Data collection module for CAT."""

from .synthetic_data import SyntheticDataGenerator, generate_synthetic_dataset
from .clients import (
    EventCalendarClient,
    WeatherClient,
    HistoricalRecordsClient,
    RateLimiter,
    CacheEntry
)
from .collector import DataCollector, FetchResult, DataFreshnessStatus

__all__ = [
    "SyntheticDataGenerator",
    "generate_synthetic_dataset",
    "EventCalendarClient",
    "WeatherClient",
    "HistoricalRecordsClient",
    "RateLimiter",
    "CacheEntry",
    "DataCollector",
    "FetchResult",
    "DataFreshnessStatus"
]