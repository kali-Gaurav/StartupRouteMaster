"""
Live Validators - Phase 3 Intelligent System

Optional real-time validators that are loaded only when:
- REAL_TIME_ENABLED = true
- AND corresponding live APIs are configured

These validators are not loaded in offline mode, keeping the system lean.
Existing offline validators are always available as the base/fallback.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationStatus(str, Enum):
    """Status of a validation check."""
    VALID = "VALID"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LiveValidationResult:
    """Result of a live validation check."""

    def __init__(self, status: ValidationStatus, message: str = "", details: Dict = None):
        self.status = status
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.now()


class LiveAvailabilityValidator:
    """
    Validates current seat availability using live seat API.

    Only loaded when REAL_TIME_ENABLED=true and LIVE_SEAT_API is configured.
    """

    def __init__(self, data_provider=None):
        """
        Initialize live availability validator.

        Args:
            data_provider: DataProvider instance for getting live seat data
        """
        self.data_provider = data_provider
        self.logger = logging.getLogger(__name__)

    async def validate_seats_available(
        self,
        trip_id: int,
        required_seats: int,
        travel_date: datetime
    ) -> LiveValidationResult:
        """
        Validate that required number of seats are available for trip.

        Args:
            trip_id: Trip ID
            required_seats: Number of seats needed
            travel_date: Travel date

        Returns:
            LiveValidationResult with availability status
        """
        if not self.data_provider:
            return LiveValidationResult(
                ValidationStatus.WARNING,
                "No data provider configured"
            )

        try:
            # Get current availability from live API (via DataProvider)
            availability = await self.data_provider.get_seats(trip_id, travel_date)

            total_available = sum(availability.values())

            if total_available < required_seats:
                return LiveValidationResult(
                    ValidationStatus.ERROR,
                    f"Insufficient seats: need {required_seats}, available {total_available}",
                    {
                        'required': required_seats,
                        'available': total_available,
                        'by_class': availability
                    }
                )

            return LiveValidationResult(
                ValidationStatus.VALID,
                f"Sufficient seats available ({total_available} total)",
                {
                    'required': required_seats,
                    'available': total_available,
                    'by_class': availability
                }
            )

        except Exception as e:
            self.logger.warning(f"Live availability validation failed: {e}")
            return LiveValidationResult(
                ValidationStatus.WARNING,
                f"Could not validate live availability: {e}"
            )

    async def validate_class_availability(
        self,
        trip_id: int,
        class_type: str,
        travel_date: datetime
    ) -> LiveValidationResult:
        """
        Validate that specific class has seats available.

        Args:
            trip_id: Trip ID
            class_type: Class (e.g., 'AC_1', 'AC_2')
            travel_date: Travel date

        Returns:
            LiveValidationResult
        """
        if not self.data_provider:
            return LiveValidationResult(
                ValidationStatus.WARNING,
                "No data provider configured"
            )

        try:
            availability = await self.data_provider.get_seats(trip_id, travel_date)

            if class_type not in availability:
                return LiveValidationResult(
                    ValidationStatus.ERROR,
                    f"Class {class_type} not available on this trip",
                    {'available_classes': list(availability.keys())}
                )

            seats = availability[class_type]
            if seats <= 0:
                return LiveValidationResult(
                    ValidationStatus.ERROR,
                    f"No seats available in class {class_type}",
                    {'available_seats': seats}
                )

            return LiveValidationResult(
                ValidationStatus.VALID,
                f"{seats} seats available in class {class_type}",
                {
                    'class': class_type,
                    'available_seats': seats
                }
            )

        except Exception as e:
            self.logger.warning(f"Live class availability validation failed: {e}")
            return LiveValidationResult(
                ValidationStatus.WARNING,
                f"Could not validate {class_type} availability: {e}"
            )


class LiveDelayValidator:
    """
    Validates current delays using live delay API.

    Only loaded when REAL_TIME_ENABLED=true and LIVE_DELAY_API is configured.
    """

    def __init__(self, data_provider=None):
        """
        Initialize live delay validator.

        Args:
            data_provider: DataProvider instance for getting live delay data
        """
        self.data_provider = data_provider
        self.logger = logging.getLogger(__name__)
        self.max_acceptable_delay_minutes = 30  # Configurable

    async def validate_acceptable_delay(
        self,
        trip_id: int,
        max_delay_minutes: int = 30
    ) -> LiveValidationResult:
        """
        Validate that trip delay is acceptable.

        Args:
            trip_id: Trip ID
            max_delay_minutes: Maximum acceptable delay in minutes

        Returns:
            LiveValidationResult
        """
        if not self.data_provider:
            return LiveValidationResult(
                ValidationStatus.WARNING,
                "No data provider configured"
            )

        try:
            # Get current delay from live API (via DataProvider)
            delay_minutes = await self.data_provider.get_delays(trip_id)

            if delay_minutes > max_delay_minutes:
                return LiveValidationResult(
                    ValidationStatus.WARNING,
                    f"Trip delayed by {delay_minutes} minutes (max acceptable: {max_delay_minutes})",
                    {
                        'delay_minutes': delay_minutes,
                        'max_acceptable': max_delay_minutes,
                        'exceedance': delay_minutes - max_delay_minutes
                    }
                )

            if delay_minutes < 0:
                return LiveValidationResult(
                    ValidationStatus.VALID,
                    f"Trip running {abs(delay_minutes)} minutes early",
                    {'delay_minutes': delay_minutes}
                )

            return LiveValidationResult(
                ValidationStatus.VALID,
                f"Trip on-time (delay: {delay_minutes} min)",
                {'delay_minutes': delay_minutes}
            )

        except Exception as e:
            self.logger.warning(f"Live delay validation failed: {e}")
            return LiveValidationResult(
                ValidationStatus.WARNING,
                f"Could not validate live delays: {e}"
            )

    async def validate_transfer_feasibility_with_delays(
        self,
        from_trip_id: int,
        to_trip_id: int,
        transfer_window_minutes: int
    ) -> LiveValidationResult:
        """
        Validate transfer feasibility considering live delays.

        Args:
            from_trip_id: First train trip ID
            to_trip_id: Second train trip ID
            transfer_window_minutes: Available window for transfer

        Returns:
            LiveValidationResult
        """
        if not self.data_provider:
            return LiveValidationResult(
                ValidationStatus.WARNING,
                "No data provider configured"
            )

        try:
            # Get delays for both trains
            from_delay = await self.data_provider.get_delays(from_trip_id)
            to_delay = await self.data_provider.get_delays(to_trip_id)

            # Worst case: first train late, second train leaves early
            effective_window = transfer_window_minutes - from_delay

            if effective_window < 15:  # Minimum 15 min transfer time
                return LiveValidationResult(
                    ValidationStatus.ERROR,
                    f"Transfer not feasible with current delays",
                    {
                        'from_delay': from_delay,
                        'to_delay': to_delay,
                        'transfer_window': transfer_window_minutes,
                        'effective_window': effective_window
                    }
                )

            if effective_window < 30:
                return LiveValidationResult(
                    ValidationStatus.WARNING,
                    f"Transfer risky with current delays",
                    {
                        'from_delay': from_delay,
                        'to_delay': to_delay,
                        'transfer_window': transfer_window_minutes,
                        'effective_window': effective_window
                    }
                )

            return LiveValidationResult(
                ValidationStatus.VALID,
                f"Transfer feasible ({effective_window} min window)",
                {
                    'from_delay': from_delay,
                    'to_delay': to_delay,
                    'transfer_window': transfer_window_minutes,
                    'effective_window': effective_window
                }
            )

        except Exception as e:
            self.logger.warning(f"Transfer feasibility validation failed: {e}")
            return LiveValidationResult(
                ValidationStatus.WARNING,
                f"Could not validate transfer feasibility: {e}"
            )


class LiveFareValidator:
    """
    Validates current fares using live fare API.

    Only loaded when REAL_TIME_ENABLED=true and LIVE_FARES_API is configured.
    """

    def __init__(self, data_provider=None):
        """
        Initialize live fare validator.

        Args:
            data_provider: DataProvider instance for getting live fare data
        """
        self.data_provider = data_provider
        self.logger = logging.getLogger(__name__)

    async def validate_fares_within_budget(
        self,
        segment_id: int,
        budget: float
    ) -> LiveValidationResult:
        """
        Validate that segment fares are within budget.

        Args:
            segment_id: Segment ID
            budget: Maximum acceptable fare

        Returns:
            LiveValidationResult
        """
        if not self.data_provider:
            return LiveValidationResult(
                ValidationStatus.WARNING,
                "No data provider configured"
            )

        try:
            # Get current fares from live API (via DataProvider)
            fares = await self.data_provider.get_fares(segment_id)

            min_fare = min(fares.values()) if fares else 0
            max_fare = max(fares.values()) if fares else 0

            if min_fare > budget:
                return LiveValidationResult(
                    ValidationStatus.ERROR,
                    f"Minimum fare {min_fare} exceeds budget {budget}",
                    {
                        'min_fare': min_fare,
                        'max_fare': max_fare,
                        'budget': budget,
                        'by_class': fares
                    }
                )

            return LiveValidationResult(
                ValidationStatus.VALID,
                f"Fares available within budget",
                {
                    'min_fare': min_fare,
                    'max_fare': max_fare,
                    'budget': budget,
                    'by_class': fares
                }
            )

        except Exception as e:
            self.logger.warning(f"Live fare validation failed: {e}")
            return LiveValidationResult(
                ValidationStatus.WARNING,
                f"Could not validate live fares: {e}"
            )


# Factory function for conditional loading
def create_live_validators(data_provider=None, config=None) -> Dict[str, object]:
    """
    Create live validators conditionally based on config.

    Only creates validators when:
    - REAL_TIME_ENABLED = true
    - AND corresponding API is configured

    Args:
        data_provider: DataProvider instance
        config: Configuration object

    Returns:
        Dict of validator names -> instances (may be empty if feature disabled)
    """
    validators = {}

    if config is None:
        # attempt to import using package-relative or top-level path
        try:
            from ... import config as cfg
            config = cfg.Config
        except ImportError:
            try:
                # fallback if workspace root is in PYTHONPATH
                from database import config as cfg
                config = cfg.Config
            except ImportError:
                logger.warning("Config not available, live validators disabled")
                return validators

    # Only load if real-time is enabled
    if not getattr(config, 'REAL_TIME_ENABLED', False):
        logger.info("Real-time disabled, live validators not loaded")
        return validators

    # Load based on configured APIs
    if getattr(config, 'LIVE_SEAT_API', None):
        validators['availability'] = LiveAvailabilityValidator(data_provider)
        logger.info("✅ LiveAvailabilityValidator loaded")

    if getattr(config, 'LIVE_DELAY_API', None):
        validators['delays'] = LiveDelayValidator(data_provider)
        logger.info("✅ LiveDelayValidator loaded")

    if getattr(config, 'LIVE_FARES_API', None):
        validators['fares'] = LiveFareValidator(data_provider)
        logger.info("✅ LiveFareValidator loaded")

    if not validators:
        logger.info("No live APIs configured, using offline-only validators")

    return validators
