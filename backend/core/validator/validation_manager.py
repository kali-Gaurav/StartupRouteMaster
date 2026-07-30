"""
ValidationManager - Orchestrates all validators in a modular, scalable way

This module provides a centralized validation orchestration system that:
1. Registers and manages all validator modules
2. Provides clean API for running validation checks
3. Supports validation strategies and filtering
4. Decouples validators from route_engine
5. Makes adding/removing validators trivial
6. Enables different validation profiles (quick, full, custom)
"""

from typing import Dict, List, Optional, Any, Callable, Set
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import logging, inspect

logger = logging.getLogger(__name__)


class ValidationProfile(Enum):
    """Validation execution profiles"""
    QUICK = "quick"  # Essential validations only
    STANDARD = "standard"  # Normal validations
    FULL = "full"  # All validations
    CUSTOM = "custom"  # User-specified validations


class ValidationCategory(Enum):
    """Validation categories for grouping"""
    ROUTE_LOGIC = "route_logic"  # RT-001-020
    REAL_TIME = "real_time"  # RT-031-050
    MULTIMODAL = "multimodal"  # RT-051-070
    FARE_AVAILABILITY = "fare_availability"  # RT-071-090
    PERFORMANCE = "performance"  # RT-091-110
    API_SECURITY = "api_security"  # RT-111-130
    DATA_INTEGRITY = "data_integrity"  # RT-131-150
    AI_RANKING = "ai_ranking"  # RT-151-170
    RESILIENCE = "resilience"  # RT-171-200 (chaos & failure recovery)
    PRODUCTION_EXCELLENCE = "production_excellence"  # RT-201-220 (production readiness)


@dataclass
class ValidationResult:
    """Result from a single validation check"""
    validation_id: str
    category: ValidationCategory
    passed: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
    duration_ms: float = 0.0
    severity: str = "error"  # error, warning, info


@dataclass
class ValidationReport:
    """Comprehensive validation report"""
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    total_duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    results: List[ValidationResult] = field(default_factory=list)
    profile_used: ValidationProfile = ValidationProfile.STANDARD

    @property
    def success_rate(self) -> float:
        """Calculate overall success rate"""
        if self.total_checks == 0:
            return 0.0
        return (self.passed_checks / self.total_checks) * 100

    @property
    def all_passed(self) -> bool:
        """Check if all validations passed"""
        return self.failed_checks == 0


class ValidatorRegistry:
    """Registry to track and manage all available validators"""

    def __init__(self):
        """Initialize the validator registry"""
        self.validators: Dict[ValidationCategory, Dict[str, Any]] = {}
        self.validation_profiles: Dict[ValidationProfile, Set[ValidationCategory]] = {
            ValidationProfile.QUICK: {
                ValidationCategory.ROUTE_LOGIC,
                ValidationCategory.API_SECURITY,
            },
            ValidationProfile.STANDARD: {
                ValidationCategory.ROUTE_LOGIC,
                ValidationCategory.REAL_TIME,
                ValidationCategory.API_SECURITY,
                ValidationCategory.DATA_INTEGRITY,
                ValidationCategory.PRODUCTION_EXCELLENCE,
            },
            ValidationProfile.FULL: set(ValidationCategory),
        }

    def register_validator(self, category: ValidationCategory,
                          validator_class: Any,
                          validator_instance: Any = None) -> None:
        """
        Register a validator module.

        Args:
            category: Validation category
            validator_class: The validator class
            validator_instance: Optional pre-initialized instance
        """
        if category not in self.validators:
            self.validators[category] = {}

        self.validators[category]['class'] = validator_class
        self.validators[category]['instance'] = validator_instance or validator_class()

        logger.info(f"Registered validator {validator_class.__name__} for category {category.value}")

    def get_validator(self, category: ValidationCategory) -> Optional[Any]:
        """Get validator instance for a category"""
        if category in self.validators:
            return self.validators[category].get('instance')
        return None

    def get_categories_for_profile(self, profile: ValidationProfile) -> Set[ValidationCategory]:
        """Get validation categories for a profile"""
        if profile == ValidationProfile.CUSTOM:
            return set()  # Custom profiles specify their own
        return self.validation_profiles.get(profile, set())


class ValidationManager:
    """
    Centralized validation orchestrator.

    This manager decouples validators from route_engine and provides:
    - Clean, composable validation API
    - Support for different validation profiles
    - Easy addition/removal of validators
    - Comprehensive reporting
    - Performance tracking
    """

    def __init__(self):
        """Initialize the validation manager"""
        self.registry = ValidatorRegistry()
        self.validation_history: List[ValidationReport] = []

    def register_all_validators(self, validator_instances: Dict[ValidationCategory, Any]) -> None:
        """
        Register all validators at once.

        Args:
            validator_instances: Dict mapping categories to validator instances
        """
        for category, instance in validator_instances.items():
            self.registry.register_validator(category, instance.__class__, instance)

    def validate(self, config: Dict[str, Any],
                profile: ValidationProfile = ValidationProfile.STANDARD,
                specific_categories: Optional[Set[ValidationCategory]] = None) -> ValidationReport:
        """
        Execute validation checks. Runs all public `validate_*` methods on each registered
        validator when the configuration provides the required parameters for that method.

        Args:
            config: Validation configuration (route, fares, security context, etc.)
            profile: Validation profile to use
            specific_categories: Optional specific categories to validate (overrides profile)

        Returns:
            Comprehensive validation report
        """
        report = ValidationReport(profile_used=profile)
        start_time = datetime.utcnow()

        # Determine which categories to validate
        if specific_categories:
            categories_to_validate = specific_categories
        else:
            categories_to_validate = self.registry.get_categories_for_profile(profile)

        # Normalize config keys for parameter-matching
        config_keys = set(config.keys()) if isinstance(config, dict) else set()

        # Execute validations for each category
        for category in categories_to_validate:
            validator = self.registry.get_validator(category)
            if not validator:
                logger.warning(f"No validator registered for category: {category.value}")
                continue

            # Collect all public validate_* methods from the validator
            methods = [m for name, m in inspect.getmembers(validator, predicate=callable)
                       if name.startswith('validate_')]

            # If no public validate_* methods found, fall back to representative method
            if not methods:
                representative = self._get_validation_method(validator, category)
                if representative:
                    methods = [representative]
                else:
                    logger.debug(f"No callable validation methods for {category.value}")
                    continue

            # Execute every method whose required params are satisfied by config
            for method in methods:
                sig = inspect.signature(method)

                # Determine required parameter names (exclude 'self')
                required_params = [p.name for p in sig.parameters.values()
                                   if p.default is p.empty and p.name != 'self']

                # If the method requires params that are not present in config, skip it
                if required_params and not set(required_params).issubset(config_keys):
                    logger.debug(
                        f"Skipping {method.__name__} for {category.value} - missing params: "
                        f"{set(required_params) - config_keys}")
                    continue

                # Run the method and record the result
                result = self._run_validation(method, category, config)
                report.results.append(result)
                report.total_checks += 1

                if result.passed:
                    report.passed_checks += 1
                else:
                    report.failed_checks += 1

        # Calculate totals
        end_time = datetime.utcnow()
        report.total_duration_ms = (end_time - start_time).total_seconds() * 1000
        report.timestamp = end_time

        # Store in history
        self.validation_history.append(report)

        return report

    def validate_route(self, route: Any,
                      constraints: Any = None) -> ValidationReport:
        """Quick validation for route operations"""
        config = {
            'route': route,
            'constraints': constraints,
        }
        return self.validate(config, ValidationProfile.QUICK)

    def validate_api_request(self, request: Any,
                            security_context: Any) -> ValidationReport:
        """Validate API request with security checks"""
        config = {
            'request': request,
            'security_context': security_context,
        }
        return self.validate(config, profile=ValidationProfile.STANDARD,
                           specific_categories={ValidationCategory.API_SECURITY,
                                               ValidationCategory.ROUTE_LOGIC})

    def validate_complete(self, route: Any,
                         fares: Any,
                         data: Any,
                         request: Any = None,
                         security_context: Any = None,
                         ai_context: Any = None) -> ValidationReport:
        """Full validation across all domains"""
        config = {
            'route': route,
            'fares': fares,
            'data': data,
            'request': request,
            'security_context': security_context,
            'ai_context': ai_context,
        }
        return self.validate(config, ValidationProfile.FULL)

    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of validation history"""
        if not self.validation_history:
            return {'message': 'No validations run'}

        total_reports = len(self.validation_history)
        successful_reports = sum(1 for r in self.validation_history if r.all_passed)
        avg_success_rate = sum(r.success_rate for r in self.validation_history) / total_reports

        return {
            'total_validations_run': total_reports,
            'successful_validations': successful_reports,
            'average_success_rate': avg_success_rate,
            'total_time_ms': sum(r.total_duration_ms for r in self.validation_history),
        }

    @staticmethod
    def _get_validation_method(validator: Any,
                              category: ValidationCategory) -> Optional[Callable]:
        """Get the main validation method for a validator"""
        method_names = {
            ValidationCategory.ROUTE_LOGIC: 'validate_route_constraints',
            ValidationCategory.REAL_TIME: 'validate_realtime_delay_propagation',
            ValidationCategory.MULTIMODAL: 'validate_train_bus_integration',
            ValidationCategory.FARE_AVAILABILITY: 'validate_fare_calculation_per_segment',
            ValidationCategory.PERFORMANCE: 'validate_query_performance',
            ValidationCategory.API_SECURITY: 'validate_invalid_parameters_rejected',
            ValidationCategory.DATA_INTEGRITY: 'validate_station_graph_connectivity',
            ValidationCategory.AI_RANKING: 'validate_ranking_stability',
            ValidationCategory.RESILIENCE: 'validate_db_unavailable_during_query',
            ValidationCategory.PRODUCTION_EXCELLENCE: 'validate_end_to_end_booking_integration',
        }

        method_name = method_names.get(category)
        if method_name and hasattr(validator, method_name):
            return getattr(validator, method_name)

        return None

    @staticmethod
    def _run_validation(method: Callable,
                       category: ValidationCategory,
                       config: Dict[str, Any]) -> ValidationResult:
        """Run a single validation method safely"""
        start = datetime.utcnow()

        try:
            # Call the validation method with flexible arguments
            result = method(**config) if isinstance(config, dict) else method(config)
            passed = bool(result) if result is not None else True
            error_msg = None
        except Exception as e:
            passed = False
            error_msg = str(e)
            logger.error(f"Validation error in {category.value}: {error_msg}", exc_info=True)

        end = datetime.utcnow()
        duration = (end - start).total_seconds() * 1000

        return ValidationResult(
            validation_id=f"{category.value}_check",
            category=category,
            passed=passed,
            error_message=error_msg,
            duration_ms=duration,
        )


def create_validation_manager_with_defaults() -> ValidationManager:
    """
    Factory function to create and configure a ValidationManager with all default validators.
    This is the recommended way to initialize the manager.
    """
    from .route_validators import RouteValidator
    from .multimodal_validators import MultimodalValidator
    from .fare_availability_validators import FareAndAvailabilityValidator
    from .api_security_validators import APISecurityValidator
    from .data_integrity_validators import DataIntegrityValidator
    from .ai_ranking_validators import AIRankingValidator
    from .resilience_validators import ResilienceValidator
    from .production_validators import ProductionExcellenceValidator

    manager = ValidationManager()

    # Register all validators
    validators = {
        ValidationCategory.ROUTE_LOGIC: RouteValidator(),
        ValidationCategory.MULTIMODAL: MultimodalValidator(),
        ValidationCategory.FARE_AVAILABILITY: FareAndAvailabilityValidator(),
        ValidationCategory.API_SECURITY: APISecurityValidator(),
        ValidationCategory.DATA_INTEGRITY: DataIntegrityValidator(),
        ValidationCategory.AI_RANKING: AIRankingValidator(),
        ValidationCategory.RESILIENCE: ResilienceValidator(),
        ValidationCategory.PRODUCTION_EXCELLENCE: ProductionExcellenceValidator(),
    }

    manager.register_all_validators(validators)
    logger.info(f"ValidationManager initialized with {len(validators)} validators")

    return manager
