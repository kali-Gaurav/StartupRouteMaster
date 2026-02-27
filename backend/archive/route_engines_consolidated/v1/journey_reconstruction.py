# Consolidated wrapper - actual implementation is in backend.core.route_engine
# This file maintained for backwards compatibility
from core.route_engine import RouteEngine

# Export RouteEngine as JourneyReconstructionEngine (alias for compatibility)
JourneyReconstructionEngine = RouteEngine

__all__ = ["JourneyReconstructionEngine"]

