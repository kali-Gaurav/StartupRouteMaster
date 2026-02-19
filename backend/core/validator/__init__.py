"""
Validator Module - Comprehensive validation framework for routing system

This module organizes all validators into a single, importable namespace:
- ValidationManager: Main orchestrator for all validations
- Validator classes: Individual validators for different domains
- Supporting classes: Enums, dataclasses, etc.
"""

# Main orchestrator
from .validation_manager import (
    ValidationManager,
    ValidationProfile,
    ValidationCategory,
    ValidationResult,
    BaseValidator,
    create_validation_manager_with_defaults,
)

# Individual validators
from .route_validators import RouteValidator
from .multimodal_validators import MultimodalValidator
from .fare_availability_validators import FareAndAvailabilityValidator
from .api_security_validators import APISecurityValidator
from .data_integrity_validators import DataIntegrityValidator
from .ai_ranking_validators import AIRankingValidator
from .resilience_validators import ResilienceValidator
from .production_validators import ProductionExcellenceValidator
from .performance_validators import PerformanceValidator

__all__ = [
    # Orchestrator and core classes
    "ValidationManager",
    "ValidationProfile",
    "ValidationCategory",
    "ValidationResult",
    "BaseValidator",
    "create_validation_manager_with_defaults",
    # Individual validators
    "RouteValidator",
    "MultimodalValidator",
    "FareAndAvailabilityValidator",
    "APISecurityValidator",
    "DataIntegrityValidator",
    "AIRankingValidator",
    "ResilienceValidator",
    "ProductionExcellenceValidator",
    "PerformanceValidator",
]
