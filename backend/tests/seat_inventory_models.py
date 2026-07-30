"""Re-export of the legacy seat inventory models for the tests package."""

from backend import seat_inventory_models as _legacy_models
from seat_inventory_models import *  # noqa: F401,F403

try:
    __all__ = _legacy_models.__all__
except AttributeError:
    __all__ = [name for name in dir() if not name.startswith("_")]
