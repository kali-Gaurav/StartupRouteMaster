"""
Shim module for DemandRedistributionService to maintain compatibility.
The actual implementation has been moved to services.ml.demand_redistribution.
"""

from services.ml.demand_redistribution import (
    DemandRedistributionService,
    DemandSnapshot,
    RedistributionOpportunity,
    PassengerOffer
)

def get_redistribution_service(db=None):
    """Factory function for DemandRedistributionService"""
    from services.ml.demand_redistribution import DemandRedistributionService
    return DemandRedistributionService(db=db)

__all__ = [
    "DemandRedistributionService",
    "DemandSnapshot",
    "RedistributionOpportunity",
    "PassengerOffer",
    "get_redistribution_service"
]
