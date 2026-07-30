"""
Shim module for storage_sync to maintain compatibility.
The actual implementation is in services.data.storage_sync.
"""

from services.data.storage_sync import (
    r2_sync_manager
)

__all__ = ["r2_sync_manager"]
