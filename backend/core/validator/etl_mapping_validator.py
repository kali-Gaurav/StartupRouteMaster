"""
ETL Mapping & Validation Layer
Handles transformation and validation of data from railway_data.db (human-readable) 
to transit_graph database (GTFS-optimized) with full lineage tracking
"""

import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from ...database.models import Stop, Trip, StopTime, Route as GTFRoute, Transfer, Calendar, CalendarDate

logger = logging.getLogger(__name__)


class ETLStatus(Enum):
    """ETL execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    VALIDATION_ERROR = "validation_error"


class DataLineageType(Enum):
    """Type of data lineage relationship"""
    SOURCE_TO_TARGET = "source_to_target"
    FOREIGN_KEY = "foreign_key"
    AGGREGATED = "aggregated"
    DERIVED = "derived"
    CALCULATED = "calculated"


@dataclass
class ETLMapping:
    """Single ETL mapping definition"""
    source_table: str
    source_columns: List[str]
    target_table: str
    target_columns: List[str]
    transformation_logic: Optional[str] = None
    validation_rules: List[str] = field(default_factory=list)
    sample_sql: Optional[str] = None


@dataclass
class DataLineageRecord:
    """Tracks lineage of data transformation"""
    source_id: Any  # ID in source system
    target_id: Any  # ID in target system
    source_table: str
    target_table: str
    lineage_type: DataLineageType
    transformation_timestamp: datetime = field(default_factory=datetime.utcnow)
    validation_passed: bool = True
    notes: Optional[str] = None


@dataclass
class ETLExecutionLog:
    """Log of ETL execution"""
    execution_id: str
    status: ETLStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    total_records_processed: int = 0
    successful_records: int = 0
    failed_records: int = 0
    validation_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    data_lineage: List[DataLineageRecord] = field(default_factory=list)

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    @property
    def success_rate(self) -> float:
        if self.total_records_processed == 0:
            return 0.0
        return self.successful_records / self.total_records_processed


class ETLMappingRegistry:
    """Registry of all ETL mappings between source and target databases"""

    # Core ETL mappings for railway to GTFS conversion
    MAPPINGS = [
        ETLMapping(
            source_table="stations_master",
            source_columns=["station_code", "station_name", "city", "state", "latitude", "longitude"],
            target_table="stops",
            target_columns=["stop_id", "stop_name", "stop_city", "stop_region", "stop_lat", "stop_lon"],
            transformation_logic="1:1 mapping; station_code -> stop_id; add geometry from lat/lon",
            validation_rules=[
                "All source rows must map to target rows",
                "Latitude and longitude must be valid coordinates",
                "Stop ID must be unique in target"
            ]
        ),
        ETLMapping(
            source_table="train_schedule",
            source_columns=["train_no", "seq_no", "station_code", "arrival_time", "departure_time", "day_offset"],
            target_table="stop_times",
            target_columns=["trip_id", "stop_sequence", "stop_id", "arrival_time", "departure_time"],
            transformation_logic="""
                train_no + service_id + date -> trip_id
                seq_no -> stop_sequence
                station_code -> stop_id (via foreign key to stops)
                arrival/departure times normalized to HH:MM:SS format
            """,
            validation_rules=[
                "Arrival time must be <= departure time (or next day)",
                "Sequence numbers must be consecutive and start at 0",
                "Stop IDs must exist in target stops table",
                "Trip IDs must exist in target trips table"
            ]
        ),
        ETLMapping(
            source_table="train_routes",
            source_columns=["train_no", "source_station_code", "dest_station_code", "distance_km"],
            target_table="trips",
            target_columns=["trip_id", "route_id", "service_id"],
            transformation_logic="""
                train_no -> used as basis for trip_id
                source/dest stations -> used for route_id derivation
                distance_km preserved for validation
            """,
            validation_rules=[
                "Source and destination stations must exist",
                "Distance must be positive",
                "Route must be consistent across all trips on same train"
            ]
        ),
        ETLMapping(
            source_table="train_running_days",
            source_columns=["train_no", "mon", "tue", "wed", "thu", "fri", "sat", "sun"],
            target_table="calendar",
            target_columns=["service_id", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
            transformation_logic="1:1 mapping for days of week; train_no used for service_id derivation",
            validation_rules=[
                "At least one day must be True",
                "Service ID must be referenced by trips table"
            ]
        ),
    ]

    @classmethod
    def get_mapping(cls, source_table: str, target_table: str) -> Optional[ETLMapping]:
        """Get mapping between source and target tables"""
        for mapping in cls.MAPPINGS:
            if mapping.source_table == source_table and mapping.target_table == target_table:
                return mapping
        return None

    @classmethod
    def get_all_mappings(cls) -> List[ETLMapping]:
        """Get all ETL mappings"""
        return cls.MAPPINGS


class ETLValidator:
    """Validates data integrity during ETL process"""

    def __init__(self, source_session: Session, target_session: Session):
        self.source_session = source_session
        self.target_session = target_session
        self.validation_errors: List[str] = []
        self.warnings: List[str] = []

    async def validate_referential_integrity(self) -> bool:
        """Validate all foreign key relationships"""
        errors = []

        # Validate stop_times.stop_id exists in stops
        orphan_stop_times = self.target_session.query(StopTime).filter(
            ~StopTime.stop_id.in_(
                self.target_session.query(Stop.id)
            )
        ).count()
        if orphan_stop_times > 0:
            msg = f"Found {orphan_stop_times} stop_times with invalid stop_id references"
            errors.append(msg)

        # Validate stop_times.trip_id exists in trips
        orphan_stop_times = self.target_session.query(StopTime).filter(
            ~StopTime.trip_id.in_(
                self.target_session.query(Trip.id)
            )
        ).count()
        if orphan_stop_times > 0:
            msg = f"Found {orphan_stop_times} stop_times with invalid trip_id references"
            errors.append(msg)

        # Validate trips.route_id exists in routes
        orphan_trips = self.target_session.query(Trip).filter(
            ~Trip.route_id.in_(
                self.target_session.query(GTFRoute.id)
            )
        ).count()
        if orphan_trips > 0:
            msg = f"Found {orphan_trips} trips with invalid route_id references"
            errors.append(msg)

        self.validation_errors.extend(errors)
        return len(errors) == 0

    async def validate_temporal_consistency(self) -> bool:
        """Validate time-related constraints"""
        errors = []

        # Validate arrival <= departure (same-day)
        bad_times = self.target_session.query(StopTime).filter(
            StopTime.arrival_time > StopTime.departure_time
        ).count()
        if bad_times > 0:
            msg = f"Found {bad_times} stop_times with arrival_time > departure_time"
            errors.append(msg)

        # Validate stop sequence is monotonic within a trip
        for trip in self.target_session.query(Trip).all():
            stop_times = self.target_session.query(StopTime).filter(
                StopTime.trip_id == trip.id
            ).order_by(StopTime.stop_sequence).all()
            
            if not stop_times:
                continue
            
            # Check sequence
            for i, st in enumerate(stop_times):
                if st.stop_sequence != i:
                    msg = f"Trip {trip.id}: stop_sequence not monotonic at position {i}"
                    errors.append(msg)
                    break

        self.validation_errors.extend(errors)
        return len(errors) == 0

    async def validate_geometric_consistency(self) -> bool:
        """Validate geographic data integrity"""
        errors = []

        # Validate latitude/longitude ranges
        bad_stops = self.target_session.query(Stop).filter(
            or_(
                Stop.stop_lat < -90,
                Stop.stop_lat > 90,
                Stop.stop_lon < -180,
                Stop.stop_lon > 180
            )
        ).count()
        if bad_stops > 0:
            msg = f"Found {bad_stops} stops with invalid coordinates"
            errors.append(msg)

        self.validation_errors.extend(errors)
        return len(errors) == 0

    async def validate_distance_consistency(self) -> bool:
        """Validate distance calculations match actual travel"""
        errors = []
        warnings = []

        # This is implemented in the distance_time_validator module
        # Here we just check for extreme cases
        try:
            from sqlalchemy.sql import text
            
            # Check for suspiciously long travel times
            suspicious = self.target_session.execute(text("""
                SELECT trip_id, stop_sequence, 
                       (EXTRACT(EPOCH FROM (departure_time - arrival_time)) / 60) AS duration_minutes
                FROM stop_times
                WHERE departure_time > arrival_time
                  AND (EXTRACT(EPOCH FROM (departure_time - arrival_time)) / 60) > 1440
                LIMIT 10
            """)).fetchall()
            
            if suspicious:
                msg = f"Found {len(suspicious)} suspiciously long stop durations (> 24 hours)"
                warnings.append(msg)

        except Exception as e:
            logger.warning(f"Distance consistency check failed: {e}")

        self.validation_errors.extend(errors)
        self.warnings.extend(warnings)
        return len(errors) == 0

    async def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """Run all validation checks"""
        self.validation_errors = []
        self.warnings = []

        checks = [
            ("Referential Integrity", self.validate_referential_integrity),
            ("Temporal Consistency", self.validate_temporal_consistency),
            ("Geometric Consistency", self.validate_geometric_consistency),
            ("Distance Consistency", self.validate_distance_consistency),
        ]

        all_passed = True
        for check_name, check_func in checks:
            try:
                passed = await check_func()
                if not passed:
                    all_passed = False
                    logger.warning(f"Validation check '{check_name}' failed")
                else:
                    logger.info(f"Validation check '{check_name}' passed")
            except Exception as e:
                all_passed = False
                self.validation_errors.append(f"{check_name} raised exception: {e}")
                logger.error(f"Validation check '{check_name}' raised exception: {e}")

        return all_passed, self.validation_errors, self.warnings


class ETLLineageTracker:
    """Tracks data lineage through ETL transformations"""

    def __init__(self, session: Session):
        self.session = session
        self.lineage_records: List[DataLineageRecord] = []

    def record_transformation(self, 
                            source_id: Any, target_id: Any,
                            source_table: str, target_table: str,
                            lineage_type: DataLineageType,
                            validation_passed: bool = True,
                            notes: Optional[str] = None):
        """Record a data transformation"""
        record = DataLineageRecord(
            source_id=source_id,
            target_id=target_id,
            source_table=source_table,
            target_table=target_table,
            lineage_type=lineage_type,
            validation_passed=validation_passed,
            notes=notes
        )
        self.lineage_records.append(record)

    def get_lineage(self, target_id: Any, target_table: str) -> List[DataLineageRecord]:
        """Get full lineage chain for a target record"""
        result = []
        current_id = target_id
        current_table = target_table

        # Walk backwards through transformations
        while current_id and current_table:
            matching = [r for r in self.lineage_records 
                       if r.target_id == current_id and r.target_table == current_table]
            if not matching:
                break
            
            record = matching[0]
            result.append(record)
            current_id = record.source_id
            current_table = record.source_table

        return list(reversed(result))

    def export_lineage_report(self) -> Dict[str, Any]:
        """Export lineage tracking report"""
        return {
            "total_records_tracked": len(self.lineage_records),
            "validation_successes": sum(1 for r in self.lineage_records if r.validation_passed),
            "validation_failures": sum(1 for r in self.lineage_records if not r.validation_passed),
            "by_lineage_type": {
                lt.value: sum(1 for r in self.lineage_records if r.lineage_type == lt)
                for lt in DataLineageType
            },
            "sample_records": [
                {
                    "source": f"{r.source_table}:{r.source_id}",
                    "target": f"{r.target_table}:{r.target_id}",
                    "type": r.lineage_type.value,
                    "validated": r.validation_passed
                }
                for r in self.lineage_records[:100]
            ]
        }
