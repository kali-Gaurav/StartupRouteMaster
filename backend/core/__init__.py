"""
Core Route Finding Engine - Master Entry Point
Standardized for 10X Performance.
"""

# Note: We avoid heavy imports here to prevent circular dependencies
# during model/schema initialization. Use direct imports from submodules.
# Example: from core.route_engine import get_route_engine (G11.4)

from . import data_structures

__all__ = [
    "data_structures"
]
