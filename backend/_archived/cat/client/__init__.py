"""
CAT Client Library for Route Engine Integration.

Provides Python client for CAT inference service with support for
synchronous and asynchronous prediction requests.
"""

from .cat_client import CATClient, create_cat_client

__all__ = ["CATClient", "create_cat_client"]
