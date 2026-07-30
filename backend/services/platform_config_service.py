"""
Shim module for PlatformConfigService import compatibility.
The actual implementation is in services/orchestration/config.py
"""

from services.orchestration.config import PlatformConfigService

__all__ = ["PlatformConfigService"]