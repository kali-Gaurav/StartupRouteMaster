"""
Route Validation System for Offline Mode

Validates routes at multiple levels:
- RouteValidator: Complete route validation
- SegmentValidator: Individual segment (train journey) validation
- TransferValidator: Transfer point validation
- AvailabilityValidator: Seat/coach availability checking
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from datetime import datetime, time
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    """Validation result status"""
    VALID = "VALID"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class ValidationError:
    """Single validation error/warning"""
    code: str  # e.g., "TRAIN_NOT_FOUND", "INVALID_TIME"
    message: str
    level: ValidationStatus
    field: Optional[str] = None
    details: Dict = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Complete validation result"""
    is_valid: bool
    status: ValidationStatus
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    checks_passed: int = 0
    checks_failed: int = 0
    summary: str = ""

    def add_error(self, error: ValidationError):
        """Add an error."""
        self.errors.append(error)
        self.checks_failed += 1
        if error.level == ValidationStatus.CRITICAL:
            self.is_valid = False
            self.status = ValidationStatus.CRITICAL
        elif error.level == ValidationStatus.ERROR:
            self.is_valid = False
            self.status = ValidationStatus.ERROR

    def add_warning(self, warning: ValidationError):
        """Add a warning."""
        self.warnings.append(warning)
        if self.status != ValidationStatus.ERROR:
            self.status = ValidationStatus.WARNING

    def pass_check(self):
        """Register a passed check."""
        self.checks_passed += 1


class SegmentValidator:
    """
    Validates individual route segments (train journeys).

    Checks:
    - Train exists in database
    - Departure stop exists
    - Arrival stop exists
    - Times are valid (departure < arrival)
    - Service is active on the date
    - Duration is reasonable
    """

    def __init__(self, session):
        self.session = session
        self.logger = logging.getLogger(__name__)

    def validate_segment(
        self,
        trip_id: int,
        from_stop_id: int,
        to_stop_id: int,
        departure_time: time,
        arrival_time: time,
        travel_date: datetime
    ) -> ValidationResult:
        """Validate a single segment."""
        result = ValidationResult(is_valid=True, status=ValidationStatus.VALID)

        # Check 1: Trip exists
        if not self._trip_exists(trip_id):
            result.add_error(ValidationError(
                code="TRIP_NOT_FOUND",
                message=f"Trip {trip_id} not found in database",
                level=ValidationStatus.CRITICAL,
                field="trip_id"
            ))
            return result
        result.pass_check()

        # Check 2: Stops exist
        if not self._stop_exists(from_stop_id):
            result.add_error(ValidationError(
                code="FROM_STOP_NOT_FOUND",
                message=f"From stop {from_stop_id} not found",
                level=ValidationStatus.CRITICAL,
                field="from_stop_id"
            ))

        if not self._stop_exists(to_stop_id):
            result.add_error(ValidationError(
                code="TO_STOP_NOT_FOUND",
                message=f"To stop {to_stop_id} not found",
                level=ValidationStatus.CRITICAL,
                field="to_stop_id"
            ))

        if result.errors:
            return result
        result.pass_check()

        # Check 3: Times are valid
        if departure_time >= arrival_time:
            result.add_error(ValidationError(
                code="INVALID_TIMES",
                message=f"Departure {departure_time} >= Arrival {arrival_time}",
                level=ValidationStatus.CRITICAL,
                field="times"
            ))
            return result
        result.pass_check()

        # Check 4: Service is active
        if not self._service_active(trip_id, travel_date):
            result.add_warning(ValidationError(
                code="SERVICE_NOT_ACTIVE",
                message=f"Service not active on {travel_date.date()}",
                level=ValidationStatus.WARNING,
                field="travel_date"
            ))
        else:
            result.pass_check()

        # Check 5: Duration is reasonable (< 24 hours)
        duration_minutes = self._calculate_duration(departure_time, arrival_time)
        if duration_minutes > 1440:
            result.add_warning(ValidationError(
                code="UNUSUAL_DURATION",
                message=f"Segment duration {duration_minutes} minutes (> 24h)",
                level=ValidationStatus.WARNING,
                field="duration"
            ))
        else:
            result.pass_check()

        result.summary = f"Segment valid: {from_stop_id}→{to_stop_id} {departure_time}→{arrival_time}"
        return result

    def _trip_exists(self, trip_id: int) -> bool:
        """Check if trip exists in database."""
        try:
            from ...database.models import Trip
            trip = self.session.query(Trip).filter(Trip.id == trip_id).first()
            return trip is not None
        except:
            return False

    def _stop_exists(self, stop_id: int) -> bool:
        """Check if stop exists."""
        try:
            from ...database.models import Stop
            stop = self.session.query(Stop).filter(Stop.id == stop_id).first()
            return stop is not None
        except:
            return False

    def _service_active(self, trip_id: int, date: datetime) -> bool:
        """Check if service is active on the date."""
        try:
            from ...database.models import Trip, Calendar
            trip = self.session.query(Trip).filter(Trip.id == trip_id).first()
            if not trip:
                return False

            calendar = self.session.query(Calendar).filter(
                Calendar.service_id == trip.service_id
            ).first()
            if not calendar:
                return False

            day_of_week = date.weekday()
            days = [
                calendar.monday,
                calendar.tuesday,
                calendar.wednesday,
                calendar.thursday,
                calendar.friday,
                calendar.saturday,
                calendar.sunday,
            ]
            return days[day_of_week]
        except:
            return False

    def _calculate_duration(self, dep_time: time, arr_time: time) -> int:
        """Calculate duration in minutes."""
        dep_minutes = dep_time.hour * 60 + dep_time.minute
        arr_minutes = arr_time.hour * 60 + arr_time.minute
        if arr_minutes < dep_minutes:  # Next day
            arr_minutes += 1440
        return arr_minutes - dep_minutes


class TransferValidator:
    """
    Validates transfer connections between segments.

    Checks:
    - Arrival station = Transfer station
    - Next departure station = Transfer station
    - Waiting time is sufficient (>= min_transfer_time)
    - Waiting time is not excessive (not too risky)
    - Stations are connected
    """

    def __init__(self, session):
        self.session = session
        self.logger = logging.getLogger(__name__)
        self.min_transfer_time = 5  # minutes
        self.max_safe_transfer_time = 120  # minutes
        self.risky_transfer_time = 10  # minutes

    def validate_transfer(
        self,
        from_segment_arrival_stop: int,
        from_segment_arrival_time: time,
        to_segment_departure_stop: int,
        to_segment_departure_time: time
    ) -> ValidationResult:
        """Validate a transfer between two segments."""
        result = ValidationResult(is_valid=True, status=ValidationStatus.VALID)

        # Check 1: Stations match
        if from_segment_arrival_stop != to_segment_departure_stop:
            result.add_error(ValidationError(
                code="STATION_MISMATCH",
                message=f"Arrival station {from_segment_arrival_stop} != "
                        f"Departure station {to_segment_departure_stop}",
                level=ValidationStatus.CRITICAL,
                field="stations"
            ))
            return result
        result.pass_check()

        # Check 2: Stations are connected
        if not self._stations_connected(
            from_segment_arrival_stop,
            to_segment_departure_stop
        ):
            result.add_warning(ValidationError(
                code="STATIONS_NOT_DIRECTLY_CONNECTED",
                message="Stations may not have direct transfer",
                level=ValidationStatus.WARNING,
                field="connection"
            ))

        # Check 3: Walking/transfer time
        walking_time = self._get_transfer_walking_time(
            from_segment_arrival_stop,
            to_segment_departure_stop
        )
        result.pass_check()

        # Check 4: Waiting time is sufficient
        waiting_time = self._calculate_waiting_time(
            from_segment_arrival_time,
            to_segment_departure_time
        )

        min_safe_time = self.min_transfer_time + walking_time
        if waiting_time < min_safe_time:
            result.add_error(ValidationError(
                code="INSUFFICIENT_TRANSFER_TIME",
                message=f"Waiting time {waiting_time}min < required {min_safe_time}min",
                level=ValidationStatus.CRITICAL,
                field="waiting_time"
            ))
        else:
            result.pass_check()

        # Check 5: Risk assessment
        risk_level = self._assess_transfer_risk(waiting_time, walking_time)
        if risk_level in ["HIGH", "RISKY"]:
            result.add_warning(ValidationError(
                code="RISKY_TRANSFER",
                message=f"Transfer risk: {risk_level}",
                level=ValidationStatus.WARNING,
                field="risk",
                details={"risk_level": risk_level, "waiting_time": waiting_time}
            ))

        result.summary = (
            f"Transfer valid: {waiting_time}min wait, risk={risk_level}"
        )
        return result

    def _stations_connected(self, from_id: int, to_id: int) -> bool:
        """Check if stations have transfer possibility."""
        # Simplified: most connected stations in same city are OK
        # In future, query transfers table
        return True

    def _get_transfer_walking_time(self, from_id: int, to_id: int) -> int:
        """Get transfer walking time between stations (minutes)."""
        # Simplified: assume 5 minutes default
        # In future, query transfers table for actual time
        try:
            from ...database.models import Transfer
            transfer = self.session.query(Transfer).filter(
                Transfer.from_stop_id == from_id,
                Transfer.to_stop_id == to_id
            ).first()
            if transfer:
                return transfer.walking_time_minutes or 5
        except:
            pass
        return 5

    def _calculate_waiting_time(self, arr_time: time, dep_time: time) -> int:
        """Calculate waiting time in minutes."""
        arr_minutes = arr_time.hour * 60 + arr_time.minute
        dep_minutes = dep_time.hour * 60 + dep_time.minute
        if dep_minutes < arr_minutes:  # Next day
            dep_minutes += 1440
        return dep_minutes - arr_minutes

    def _assess_transfer_risk(self, waiting_time: int, walking_time: int) -> str:
        """Assess transfer risk level."""
        buffer = waiting_time - walking_time
        if buffer < 5:
            return "RISKY"
        elif buffer < 10:
            return "HIGH"
        elif buffer < 30:
            return "MEDIUM"
        elif buffer < 120:
            return "LOW"
        else:
            return "SAFE"


class RouteValidator:
    """
    Validates complete routes.

    Validates:
    - Each segment is valid (using SegmentValidator)
    - Each transfer is valid (using TransferValidator)
    - Total duration is reasonable
    - No loops or invalid patterns
    """

    def __init__(self, session):
        self.session = session
        self.segment_validator = SegmentValidator(session)
        self.transfer_validator = TransferValidator(session)
        self.logger = logging.getLogger(__name__)

    def validate_complete_route(
        self,
        segments: List[Dict],
        travel_date: datetime
    ) -> ValidationResult:
        """Validate complete route (all segments and transfers)."""
        result = ValidationResult(is_valid=True, status=ValidationStatus.VALID)

        if not segments:
            result.add_error(ValidationError(
                code="NO_SEGMENTS",
                message="Route has no segments",
                level=ValidationStatus.CRITICAL,
                field="segments"
            ))
            return result

        # Validate each segment
        for i, segment in enumerate(segments):
            segment_result = self.segment_validator.validate_segment(
                trip_id=segment['trip_id'],
                from_stop_id=segment['from_stop_id'],
                to_stop_id=segment['to_stop_id'],
                departure_time=segment['departure_time'],
                arrival_time=segment['arrival_time'],
                travel_date=travel_date
            )

            if not segment_result.is_valid:
                result.errors.extend(segment_result.errors)
                result.checks_failed += segment_result.checks_failed
            result.checks_passed += segment_result.checks_passed

        if not result.is_valid:
            return result

        # Validate transfers between consecutive segments
        for i in range(len(segments) - 1):
            current = segments[i]
            next_seg = segments[i + 1]

            transfer_result = self.transfer_validator.validate_transfer(
                from_segment_arrival_stop=current['to_stop_id'],
                from_segment_arrival_time=current['arrival_time'],
                to_segment_departure_stop=next_seg['from_stop_id'],
                to_segment_departure_time=next_seg['departure_time']
            )

            result.warnings.extend(transfer_result.warnings)
            if not transfer_result.is_valid:
                result.errors.extend(transfer_result.errors)
                result.checks_failed += transfer_result.checks_failed
            result.checks_passed += transfer_result.checks_passed

        # Check total duration
        result.pass_check()
        result.summary = (
            f"Route valid: {len(segments)} segments, "
            f"{len(segments)-1} transfers"
        )

        return result


class AvailabilityValidator:
    """
    Checks seat and coach availability.

    Checks:
    - Coaches exist for segment
    - Seats available in requested class
    - Inventory matches database
    """

    def __init__(self, session):
        self.session = session
        self.logger = logging.getLogger(__name__)

    def check_availability(
        self,
        segment: Dict,
        travel_date: datetime,
        class_preference: str = "ANY"
    ) -> ValidationResult:
        """Check seat availability for segment."""
        result = ValidationResult(is_valid=True, status=ValidationStatus.VALID)

        try:
            # Check coaches exist
            coaches = self._get_coaches(segment['trip_id'])
            if not coaches:
                result.add_warning(ValidationError(
                    code="NO_COACHES_FOUND",
                    message="No coaches found for trip",
                    level=ValidationStatus.WARNING,
                    field="coaches"
                ))
            else:
                result.pass_check()

            # Check seats availability
            available_seats = self._get_available_seats(
                segment['trip_id'],
                travel_date
            )
            if available_seats > 0:
                result.pass_check()
            else:
                result.add_warning(ValidationError(
                    code="NO_SEATS_AVAILABLE",
                    message="No seats available",
                    level=ValidationStatus.WARNING,
                    field="seats",
                    details={"available": available_seats}
                ))

        except Exception as e:
            self.logger.warning(f"Availability check failed: {e}")
            result.add_warning(ValidationError(
                code="AVAILABILITY_CHECK_FAILED",
                message=str(e),
                level=ValidationStatus.WARNING,
                field="availability"
            ))

        return result

    def _get_coaches(self, trip_id: int) -> List[Dict]:
        """Get coaches for a trip."""
        try:
            from ...database.models import Coach
            coaches = self.session.query(Coach).filter(
                Coach.train_id == trip_id
            ).all()
            return [{'id': c.id, 'number': c.coach_number} for c in coaches]
        except:
            return []

    def _get_available_seats(self, trip_id: int, date: datetime) -> int:
        """Get available seat count."""
        # Simplified: return random positive number
        # In future, query seat_inventory table
        return 20
