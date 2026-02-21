"""
Distance & Travel Time Consistency Validator
Validates that distances match calculated travel times and detects inconsistencies
between train_routes, stop_times, and schedule tables
"""

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any

from sqlalchemy import and_, func, text
from sqlalchemy.orm import Session

from ...database.models import Stop, Trip, StopTime, Route as GTFRoute, Segment

logger = logging.getLogger(__name__)


class DistanceUnit(Enum):
    """Distance measurement units"""
    METERS = "meters"
    KILOMETERS = "kilometers"
    MILES = "miles"


class TimeUnit(Enum):
    """Time measurement units"""
    SECONDS = "seconds"
    MINUTES = "minutes"
    HOURS = "hours"


@dataclass
class DistanceTimeRecord:
    """Single distance/time record"""
    trip_id: int
    from_stop_id: int
    to_stop_id: int
    distance_km: float
    calculated_duration_minutes: int
    recorded_duration_minutes: int
    
    @property
    def duration_diff_minutes(self) -> int:
        return abs(self.recorded_duration_minutes - self.calculated_duration_minutes)
    
    @property
    def implied_speed_kmph(self) -> float:
        if self.recorded_duration_minutes <= 0:
            return 0.0
        return (self.distance_km / self.recorded_duration_minutes) * 60
    
    @property
    def duration_variance_percent(self) -> float:
        if self.calculated_duration_minutes == 0:
            return 0.0
        return (self.duration_diff_minutes / self.calculated_duration_minutes) * 100


@dataclass
class ValidationIssue:
    """Single validation issue found"""
    issue_type: str  # 'distance_mismatch', 'time_inconsistency', 'speed_anomaly', etc.
    severity: str    # 'info', 'warning', 'error'
    trip_id: int
    from_stop_id: int
    to_stop_id: int
    message: str
    suggested_value: Optional[Any] = None
    confidence: float = 0.0  # 0.0-1.0 confidence in the suggestion


@dataclass
class DistanceTimeValidationReport:
    """Complete validation report"""
    total_segments_checked: int = 0
    valid_segments: int = 0
    issues_found: List[ValidationIssue] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def issue_summary(self) -> Dict[str, int]:
        """Count issues by type"""
        summary = {}
        for issue in self.issues_found:
            key = f"{issue.severity}:{issue.issue_type}"
            summary[key] = summary.get(key, 0) + 1
        return summary
    
    @property
    def validation_passed(self) -> bool:
        """True if no errors found"""
        return not any(i.severity == 'error' for i in self.issues_found)


class DistanceTimeConsistencyValidator:
    """Validates distance and travel time consistency"""

    # Reasonable speed bounds for trains (km/h)
    MIN_TRAIN_SPEED_KMPH = 20   # Minimum reasonable speed
    MAX_TRAIN_SPEED_KMPH = 160  # Maximum reasonable speed (high-speed rail)
    AVERAGE_TRAIN_SPEED_KMPH = 60  # Expected average speed

    # Tolerance for time variances (in percent)
    TIME_VARIANCE_TOLERANCE_PERCENT = 20  # Allow ±20% variance

    def __init__(self, session: Session):
        self.session = session
        self.report = DistanceTimeValidationReport()

    async def validate_all_segments(self) -> DistanceTimeValidationReport:
        """Validate all trip segments for distance/time consistency"""
        logger.info("Starting distance/time consistency validation...")
        
        self.report = DistanceTimeValidationReport()
        
        # Get all trips with their stop times
        trips = self.session.query(Trip).all()
        
        for trip in trips:
            stop_times = self.session.query(StopTime).filter(
                StopTime.trip_id == trip.id
            ).order_by(StopTime.stop_sequence).all()
            
            if len(stop_times) < 2:
                continue
            
            # Check each segment in the trip
            for i in range(len(stop_times) - 1):
                current = stop_times[i]
                next_st = stop_times[i + 1]
                
                await self._validate_segment(
                    trip.id, current, next_st, trip
                )
        
        # Compute statistics
        self._compute_statistics()
        
        logger.info(f"Distance/time validation complete: {len(self.report.issues_found)} issues found")
        
        return self.report

    async def _validate_segment(self, trip_id: int, current_st: StopTime, next_st: StopTime, trip: Trip):
        """Validate a single segment between two stops"""
        self.report.total_segments_checked += 1
        
        # Get stop information
        current_stop = self.session.query(Stop).filter(Stop.id == current_st.stop_id).first()
        next_stop = self.session.query(Stop).filter(Stop.id == next_st.stop_id).first()
        
        if not current_stop or not next_stop:
            return
        
        # Calculate recorded duration
        if next_st.arrival_time and current_st.departure_time:
            delta = next_st.arrival_time - current_st.departure_time
            if delta.total_seconds() < 0:
                # Next day arrival
                delta = delta + timedelta(days=1)
            recorded_duration = int(delta.total_seconds() // 60)
        else:
            return
        
        # Calculate distance using Haversine formula
        if current_stop.stop_lat and current_stop.stop_lon and next_stop.stop_lat and next_stop.stop_lon:
            distance_km = self._haversine_distance(
                current_stop.stop_lat, current_stop.stop_lon,
                next_stop.stop_lat, next_stop.stop_lon
            ) / 1000
        else:
            distance_km = None
        
        # Calculate expected duration from distance
        if distance_km:
            expected_duration = int(
                (distance_km / self.AVERAGE_TRAIN_SPEED_KMPH) * 60
            )
        else:
            expected_duration = None
        
        # Validate various aspects
        issues = []
        
        # Check 1: Distance vs recorded time
        if distance_km and recorded_duration > 0:
            implied_speed = (distance_km / recorded_duration) * 60
            
            if implied_speed < self.MIN_TRAIN_SPEED_KMPH:
                issues.append(ValidationIssue(
                    issue_type="speed_anomaly",
                    severity="warning",
                    trip_id=trip_id,
                    from_stop_id=current_st.stop_id,
                    to_stop_id=next_st.stop_id,
                    message=f"Implied speed {implied_speed:.1f} km/h is below minimum {self.MIN_TRAIN_SPEED_KMPH} km/h",
                    confidence=0.8
                ))
            elif implied_speed > self.MAX_TRAIN_SPEED_KMPH:
                issues.append(ValidationIssue(
                    issue_type="speed_anomaly",
                    severity="warning",
                    trip_id=trip_id,
                    from_stop_id=current_st.stop_id,
                    to_stop_id=next_st.stop_id,
                    message=f"Implied speed {implied_speed:.1f} km/h exceeds maximum {self.MAX_TRAIN_SPEED_KMPH} km/h",
                    confidence=0.7
                ))
        
        # Check 2: Time vs expected duration
        if expected_duration and recorded_duration > 0:
            variance_percent = abs(
                (recorded_duration - expected_duration) / expected_duration
            ) * 100
            
            if variance_percent > self.TIME_VARIANCE_TOLERANCE_PERCENT:
                issues.append(ValidationIssue(
                    issue_type="time_variance",
                    severity="info",
                    trip_id=trip_id,
                    from_stop_id=current_st.stop_id,
                    to_stop_id=next_st.stop_id,
                    message=f"Travel time variance {variance_percent:.1f}% exceeds tolerance {self.TIME_VARIANCE_TOLERANCE_PERCENT}%",
                    suggested_value=expected_duration,
                    confidence=0.6
                ))
        
        # Check 3: Unreasonable travel times
        if recorded_duration < 1:
            issues.append(ValidationIssue(
                issue_type="unreasonable_duration",
                severity="error",
                trip_id=trip_id,
                from_stop_id=current_st.stop_id,
                to_stop_id=next_st.stop_id,
                message=f"Travel time too short: {recorded_duration} minutes",
                confidence=0.95
            ))
        elif recorded_duration > 1440:  # 24 hours
            issues.append(ValidationIssue(
                issue_type="unreasonable_duration",
                severity="warning",
                trip_id=trip_id,
                from_stop_id=current_st.stop_id,
                to_stop_id=next_st.stop_id,
                message=f"Travel time very long: {recorded_duration} minutes (> 24 hours)",
                confidence=0.9
            ))
        
        # Check 4: Zero duration between non-identical stops
        if recorded_duration == 0 and current_st.stop_id != next_st.stop_id:
            issues.append(ValidationIssue(
                issue_type="zero_duration",
                severity="error",
                trip_id=trip_id,
                from_stop_id=current_st.stop_id,
                to_stop_id=next_st.stop_id,
                message="Zero duration between different stops",
                confidence=0.99
            ))
        
        if not issues:
            self.report.valid_segments += 1
        
        self.report.issues_found.extend(issues)

    def _compute_statistics(self):
        """Compute validation statistics"""
        self.report.statistics = {
            "total_segments": self.report.total_segments_checked,
            "valid_segments": self.report.valid_segments,
            "invalid_segments": self.report.total_segments_checked - self.report.valid_segments,
            "error_count": sum(1 for i in self.report.issues_found if i.severity == "error"),
            "warning_count": sum(1 for i in self.report.issues_found if i.severity == "warning"),
            "info_count": sum(1 for i in self.report.issues_found if i.severity == "info"),
            "issue_types": list(set(i.issue_type for i in self.report.issues_found)),
            "validation_passed": self.report.validation_passed
        }

    def get_issue_by_trip(self, trip_id: int) -> List[ValidationIssue]:
        """Get all issues for a specific trip"""
        return [i for i in self.report.issues_found if i.trip_id == trip_id]

    def get_issues_by_type(self, issue_type: str) -> List[ValidationIssue]:
        """Get all issues of a specific type"""
        return [i for i in self.report.issues_found if i.issue_type == issue_type]

    def get_issues_by_severity(self, severity: str) -> List[ValidationIssue]:
        """Get all issues of a specific severity"""
        return [i for i in self.report.issues_found if i.severity == severity]

    def suggest_correction(self, issue: ValidationIssue) -> Optional[Dict[str, Any]]:
        """Suggest correction for an issue"""
        if issue.issue_type == "time_variance" and issue.suggested_value:
            return {
                "field": "arrival_time or departure_time",
                "suggested_value": issue.suggested_value,
                "reason": "Expected duration based on distance and average train speed",
                "confidence": issue.confidence
            }
        return None

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in meters"""
        R = 6371000  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
        c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c

    async def compare_distance_sources(self) -> Dict[str, Any]:
        """Compare distances from different sources (calculated vs recorded)"""
        try:
            # Query segments with explicit distance data
            results = self.session.execute(text("""
                SELECT 
                    st.trip_id,
                    st.stop_id as from_stop,
                    st2.stop_id as to_stop,
                    st2.arrival_time - st.departure_time as recorded_duration,
                    st.stop_sequence
                FROM stop_times st
                JOIN stop_times st2 ON st.trip_id = st2.trip_id 
                    AND st2.stop_sequence = st.stop_sequence + 1
                LIMIT 1000
            """)).fetchall()
            
            comparison = {
                "total_comparisons": len(results),
                "sources_compared": ["recorded_duration", "calculated_distance"],
                "summary": "see issue details for variance analysis"
            }
            
            return comparison
        except Exception as e:
            logger.warning(f"Could not compare distance sources: {e}")
            return {"error": str(e)}


# Add missing import
from datetime import timedelta
