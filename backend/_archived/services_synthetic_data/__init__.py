# Synthetic Data Generation Framework

"""
Synthetic Data Generation Framework for cost-free route generation.

This package provides:
- Train schedule generation
- Fare data generation
- Availability data generation
- User behavior generation
- Data validation and quality checks
"""

from .generators import (
    TrainScheduleGenerator,
    FareGenerator,
    AvailabilityGenerator,
    UserBehaviorGenerator,
)

from .validation import (
    DistributionValidator,
    StatisticalValidator,
    RealismScorer,
)

from .storage import (
    FeatureStore,
    RouteGraph,
)

__all__ = [
    'TrainScheduleGenerator',
    'FareGenerator',
    'AvailabilityGenerator',
    'UserBehaviorGenerator',
    'DistributionValidator',
    'StatisticalValidator',
    'RealismScorer',
    'FeatureStore',
    'RouteGraph',
]