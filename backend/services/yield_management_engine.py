"""
Shim module for YieldManagementEngine to maintain compatibility.
The actual implementation has been moved to services.ml.yield_engine.
"""

from services.ml.yield_engine import (
    YieldManagementEngine,
    QuotaType,
    yield_management_engine
)

__all__ = [
    "YieldManagementEngine",
    "QuotaType",
    "yield_management_engine"
]
