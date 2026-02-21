# Critical System Implementation: Transfer Graph, ETL Mapping & Distance-Time Validation

## Overview

This document explains the three critical production systems that have been implemented to complete the remaining 30-40% of the RouteEngine integration:

1. **Transfer Graph Generation Pipeline** - Builds complete transfer connectivity
2. **ETL Mapping & Validation** - Ensures data integrity between databases
3. **Distance/Time Consistency Validator** - Validates travel data accuracy

All three systems are integrated into the graph building workflow via the `GraphBuildingValidationPipeline`.

---

## 1. Transfer Graph Generation Pipeline

**File:** `backend/core/route_engine/transfer_graph_builder.py`

### Problem Solved

Your system had transfer logic defined but no complete pipeline that:
- Built explicit transfers from the Transfer table
- Computed implicit transfers between nearby stops using walking times
- Validated transfer feasibility
- Handled platform connectivity
- Provided quick lookups for routing

### Architecture

```
Transfer Table (GTFS DB)
    ↓
TransferGraphBuilder
    ├── Phase 1: Load explicit transfers
    ├── Phase 2: Compute implicit transfers (walking distances)
    ├── Phase 3: Validate transfers
    └── Phase 4: Build adjacency graph
        ↓
    TimeDependentGraph
        ↓
    RAPTOR Algorithm

```

### Key Components

#### `TransferEdge`
Represents a single transfer opportunity:
```python
@dataclass
class TransferEdge:
    from_stop_id: int
    to_stop_id: int
    min_transfer_time_minutes: int
    walking_time_minutes: int
    is_same_platform: bool
    platform_from: Optional[str]
    platform_to: Optional[str]
    transfer_type: int  # GTFS standard
```

#### `TransferGraphBuilder` Methods

| Method | Purpose |
|--------|---------|
| `build_transfer_graph()` | Main entry point - builds complete graph |
| `_load_explicit_transfers()` | Reads Transfer table from DB |
| `_compute_implicit_transfers()` | Calculates walking paths between nearby stops |
| `_validate_transfers()` | Ensures transfers are feasible |
| `_build_adjacency_graph()` | Creates lookup structure |
| `get_transfers_from_stop()` | Fast lookup for routing |
| `get_transfer_time()` | Get min time between stops |

### Configuration

**Station Types & Min Transfer Times:**
```python
MIN_TRANSFER_TIMES = {
    'major_junction': 8,      # Large stations with clear transfers
    'regular_station': 12,    # Standard stations
    'small_station': 15,      # Small stations
    'metros': 5,              # Metro/urban rail
}
```

**Walking Path Configuration:**
- Max walking distance: 2000 meters
- Walking speed: 1.4 km/h (~4 minutes per 100m)
- Automatic bidirectional transfer creation

### Usage Example

```python
from backend.core.route_engine.transfer_graph_builder import TransferGraphBuilder
from backend.database import SessionLocal

session = SessionLocal()
builder = TransferGraphBuilder(session)

# Build complete transfer graph
transfer_graph = await builder.build_transfer_graph()

# Query transfers
transfers_from_delhi = builder.get_transfers_from_stop(stop_id=123)
time_delhi_to_agra = builder.get_transfer_time(123, 456)

session.close()
```

### Validation Rules Applied

Each transfer is validated against:
1. **Feasibility**: Both stops must exist
2. **Time bounds**: 5-120 minutes total (walking + waiting)
3. **Deduplication**: Keep shortest transfer time between any two stops
4. **Consistency**: Validate against historical platform data

---

## 2. ETL Mapping & Validation Layer

**File:** `backend/core/etl_mapping_validator.py`

### Problem Solved

Your system had monthly ETL scheduled but missing:
- Clear mapping definitions between source and target schemas
- Validation that data relationships are preserved
- Lineage tracking for debugging
- Foreign key consistency checks

### Architecture

```
railway_data.db (Human-readable)
    ↓
ETL Process (Scheduled monthly)
    ├── Transform via registered mappings
    ├── Validate referential integrity
    ├── Track lineage
    └── Report issues
    ↓
transit_graph DB (GTFS-optimized)
    ↓
Graph Building (with validation)

```

### Core Mappings Defined

#### 1. Stations Master → Stops
```
stations_master.station_code → stops.stop_id
stations_master.station_name → stops.stop_name
stations_master.latitude + longitude → stops.geom (PostGIS)
```

Validation Rules:
- All source rows must map to target rows
- Coordinates must be valid (lat ±90, lon ±180)
- Stop IDs must be unique

#### 2. Train Schedule → Stop Times
```
train_no + service_id + date → trip_id
seq_no → stop_sequence
station_code → stop_id (FK to stops)
arrival_time/departure_time → normalized HH:MM:SS
```

Validation Rules:
- Arrival time ≤ Departure time (or next day)
- Sequences must be consecutive starting at 0
- All ForeignKeys must exist in target

#### 3. Train Routes → Trips/Routes
```
train_no → basis for trip_id
source/dest stations → route_id
distance_km → preserved for distance validation
```

Validation Rules:
- Source and destination stations must exist
- Distance must be positive
- Route must be consistent across all trips

#### 4. Train Running Days → Calendar
```
day-of-week flags → GTFS calendar fields
train_no → service_id
```

Validation Rules:
- At least one day must be True
- Service ID must be referenced by trips table

### Key Classes

#### `ETLValidator`
Runs validation checks on ETL data:

```python
validator = ETLValidator(source_session, target_session)

# Run all checks
passed, errors, warnings = await validator.validate_all()

# Or individual checks
await validator.validate_referential_integrity()
await validator.validate_temporal_consistency()
await validator.validate_geometric_consistency()
await validator.validate_distance_consistency()
```

Checks Performed:
1. **Referential Integrity** - Foreign keys exist
2. **Temporal Consistency** - Times are monotonic, logical
3. **Geometric Consistency** - Coordinates are valid
4. **Distance Consistency** - Travel times align with distances

#### `ETLLineageTracker`
Tracks data lineage for debugging:

```python
tracker = ETLLineageTracker(session)

# Record transformations
tracker.record_transformation(
    source_id=1, target_id=42,
    source_table="stations_master",
    target_table="stops",
    lineage_type=DataLineageType.SOURCE_TO_TARGET
)

# Get full lineage chain
lineage = tracker.get_lineage(target_id=42, target_table="stops")

# Export report
report = tracker.export_lineage_report()
```

### ETL Execution Log

Each ETL run is logged:
```python
@dataclass
class ETLExecutionLog:
    execution_id: str  # UUID for this run
    status: ETLStatus
    start_time: datetime
    end_time: Optional[datetime]
    total_records_processed: int
    successful_records: int
    failed_records: int
    validation_errors: List[str]
    warnings: List[str]
    data_lineage: List[DataLineageRecord]
```

### Usage Example

```python
from backend.core.etl_mapping_validator import ETLValidator, ETLMappingRegistry

# Get registered mappings
mappings = ETLMappingRegistry.get_all_mappings()
for m in mappings:
    print(f"{m.source_table} → {m.target_table}")

# Validate ETL
validator = ETLValidator(source_session, target_session)
passed, errors, warnings = await validator.validate_all()

if not passed:
    for error in errors:
        logger.error(error)
else:
    logger.info("ETL validation passed")
```

---

## 3. Distance & Travel Time Consistency Validator

**File:** `backend/core/distance_time_validator.py`

### Problem Solved

Your system had distance data in train_routes but missing:
- Validation that distances match calculated travel times
- Detection of inconsistencies between schedule tables
- Speed anomaly detection
- Travel time variance analysis

### Architecture

```
Stop Times Table
    ↓
DistanceTimeConsistencyValidator
    ├── Calculate distance via Haversine (lat/lon)
    ├── Extract recorded duration (arrival - departure)
    ├── Compare: implied_speed = distance / time
    ├── Check bounds and consistency
    └── Report anomalies
    ↓
Validation Report
    (issues sorted by severity & confidence)

```

### Key Validations

#### 1. Speed Bounds Check
```
MIN_TRAIN_SPEED = 20 km/h (too slow)
AVERAGE_SPEED = 60 km/h (expected)
MAX_TRAIN_SPEED = 160 km/h (too fast)
```

Issues detected:
- **Warning**: Speed < 20 km/h (unrealistic)
- **Warning**: Speed > 160 km/h (exceeds high-speed rail)

#### 2. Time Variance Check
```
TOLERANCE = ±20%

variance = |recorded_time - expected_time| / expected_time

If variance > 20%:
    Issue: Recorded duration differs from calculated
```

#### 3. Duration Bounds
```
MIN_DURATION: 1 minute (Error if less)
MAX_DURATION: 1440 minutes = 24 hours (Warning if greater)
ZERO_DURATION: Error between different stops
```

#### 4. Distance Calculation
Uses Haversine formula:
```python
distance = 2 * R * arcsin(sqrt(sin²(Δφ/2) + cos(φ1)*cos(φ2)*sin²(Δλ/2)))

Where:
  φ = latitude, λ = longitude
  R = 6,371 km (Earth radius)
```

### `DistanceTimeRecord`

Represents a single segment:
```python
@dataclass
class DistanceTimeRecord:
    trip_id: int
    from_stop_id: int
    to_stop_id: int
    distance_km: float
    calculated_duration_minutes: int
    recorded_duration_minutes: int
    
    # Computed properties
    @property
    def implied_speed_kmph(self) -> float
    @property
    def duration_variance_percent(self) -> float
```

### `ValidationIssue`

Each issue is classified:
```python
@dataclass
class ValidationIssue:
    issue_type: str      # distance_mismatch, time_inconsistency, speed_anomaly, etc.
    severity: str        # info, warning, error
    trip_id: int
    message: str
    suggested_value: Optional[Any]
    confidence: float    # 0.0-1.0
```

### Usage Example

```python
from backend.core.distance_time_validator import DistanceTimeConsistencyValidator

validator = DistanceTimeConsistencyValidator(session)
report = await validator.validate_all_segments()

print(f"Total segments checked: {report.total_segments_checked}")
print(f"Valid segments: {report.valid_segments}")
print(f"Issues found: {len(report.issues_found)}")

# Get specific issues
errors = validator.get_issues_by_severity("error")
for error in errors:
    print(f"  {error.issue_type}: {error.message}")

# Get statistics
print(report.issue_summary)
```

### Correction Suggestions

For some issues, the validator suggests corrections:
```python
issue = report.issues_found[0]
correction = validator.suggest_correction(issue)

if correction:
    print(f"Suggested: {correction['field']} = {correction['suggested_value']}")
    print(f"Reason: {correction['reason']}")
    print(f"Confidence: {correction['confidence']}")
```

---

## 4. Integration: Graph Building Validation Pipeline

**File:** `backend/core/graph_validation_pipeline.py`

### Architecture

The three validators are orchestrated by a single pipeline that runs before graph building:

```
Graph Build Request
    ↓
GraphBuildingValidationPipeline
    ├── Phase 1: ETL Validation
    │       ├── Load explicit transfers
    │       ├── Referential integrity
    │       ├── Temporal consistency
    │       ├── Geometric consistency
    │       └── Distance consistency
    │
    ├── Phase 2: Distance-Time Validation
    │       ├── Check all segments
    │       ├── Compute implied speeds
    │       ├── Detect anomalies
    │       └── Generate report
    │
    ├── Phase 3: Transfer Graph Build
    │       ├── Explicit transfers
    │       ├── Implicit transfers (walking)
    │       ├── Validation
    │       └── Adjacency graph
    │
    └── Final Status: PASSED / FAILED / WARNINGS
        ↓
        GraphBuilder._build_graph_sync()
        ↓
        TimeDependentGraph + Snapshot
```

### Key Methods

```python
pipeline = GraphBuildingValidationPipeline()

# Run complete validation
results = await pipeline.validate_and_prepare_for_graph_build(date)

# Get report
report = pipeline.get_validation_report()

# Apply validated data to snapshot
snapshot = await pipeline.apply_validated_data_to_graph(snapshot)
```

### Validation Status Codes

```python
class ETLStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"                    # ✅ All checks passed
    PARTIAL_SUCCESS = "partial_success"    # ⚠️  Some warnings
    FAILED = "failed"                      # ❌ Critical errors
    VALIDATION_ERROR = "validation_error"  # ❌ Validation logic failed
```

### Integrated into GraphBuilder

The validation pipeline is automatically called in `GraphBuilder.build_graph()`:

```python
async def build_graph(self, date: datetime) -> TimeDependentGraph:
    # Step 1: Run validation
    if GraphBuildingValidationPipeline:
        logger.info("Running pre-build validation...")
        pipeline = GraphBuildingValidationPipeline()
        validation_results = await pipeline.validate_and_prepare_for_graph_build(date)
        
        if not validation_results["overall_passed"]:
            logger.warning(f"Validation issues: {validation_results['errors']}")
    
    # Step 2: Build graph (with validated data)
    graph = TimeDependentGraph(...)
    
    # Step 3: Apply validated transfer graph
    if GraphBuildingValidationPipeline:
        graph.snapshot = await pipeline.apply_validated_data_to_graph(graph.snapshot)
    
    return graph
```

---

## Workflow: Complete Data Pipeline 

### Monthly ETL Sync

1. **Trigger** (1st of month, 2 AM)
   ```
   /api/admin/etl-sync endpoint
   ```

2. **ETL Process**
   ```
   railway_data.db (sqlite)
   ├── stations_master
   ├── train_schedule
   ├── train_routes
   └── train_running_days
   
   ↓ (Transform via ETLMappingRegistry)
   
   transit_graph DB (postgres + GTFS)
   ├── stops (with geometry)
   ├── stop_times
   ├── trips
   ├── routes
   └── calendar
   
   ↓ (Validate)
   
   Referential integrity ✓
   Temporal consistency ✓
   Geometric consistency ✓
   ```

3. **Validation Results**
   - Success: Green light for graph building
   - Warnings: Log issues, continue
   - Errors: Stop and alert admin

### Daily Graph Building

1. **Pre-Build Validation**
   ```
   Distance-time consistency
   Transfer graph completeness
   Data freshness checks
   ```

2. **Graph Construction**
   ```
   PostgreSQL GTFS DB
   ├── Stations (with locations)
   ├── Routes (with schedules)
   └── Transfers (explicit + implicit walking paths)
   
   ↓
   
   TransferGraphBuilder
   ├── Explicit transfers from DB
   ├── Implicit transfers (walking)
   ├── Validation
   └── Adjacency structure
   
   ↓
   
   GraphBuilder
   ├── Time-dependent graph
   ├── Route patterns
   ├── Departure indexes
   └── Snapshot
   
   ↓
   
   Static Snapshot (cached on disk)
   ```

3. **Ready for RAPTOR**
   ```
   Route Engine
   ├── Static graph
   ├── Transfer graph
   ├── Realtime overlay (if needed)
   └── Ready for queries
   ```

---

## Testing & Verification

### Test Validation Pipeline

```python
# Test ETL validation
async def test_etl_validation():
    pipeline = GraphBuildingValidationPipeline()
    results = await pipeline._validate_etl()
    assert results["passed"]

# Test distance-time validator
async def test_distance_time():
    validator = DistanceTimeConsistencyValidator(session)
    report = await validator.validate_all_segments()
    assert report.validation_passed

# Test transfer graph
async def test_transfer_graph():
    builder = TransferGraphBuilder(session)
    graph = await builder.build_transfer_graph()
    assert len(graph) > 0
```

### Validation Report Inspection

```python
pipeline = GraphBuildingValidationPipeline()
results = await pipeline.validate_and_prepare_for_graph_build(date)

# Check results
print(results["overall_passed"])  # True/False
print(results["etl_validation"])  # Validation results
print(results["distance_time_validation"])  # Issues list
print(results["transfer_graph_preparation"])  # Graph stats

# Get human-readable report
report = pipeline.get_validation_report()
print(f"Status: {report['overall_status']}")
print(f"Errors: {report.get('errors', [])}")
print(f"Warnings: {report.get('warnings', [])}")
```

---

## Deployment

### Configuration

Add to `backend/config.py`:
```python
# Validation settings
ENABLE_GRAPH_VALIDATION = True  # Enable pre-build validation
TRANSFER_GRAPH_VALIDATION_ENABLED = True
DISTANCE_TIME_VALIDATION_ENABLED = True
ETL_VALIDATION_ENABLED = True

# Thresholds
ALLOW_WARNINGS_FOR_GRAPH_BUILD = True  # Continue if only warnings
FAIL_ON_ERRORS = False  # Log errors but don't fail build
```

### Monitoring

Log entries for each phase:
```
[2026-02-21 10:30:00] INFO: Running pre-build validation for 2026-02-21...
[2026-02-21 10:30:01] INFO: Phase 1: Running ETL validation...
[2026-02-21 10:30:02] INFO: ✓ ETL validation passed
[2026-02-21 10:30:05] INFO: Phase 2: Running distance/time consistency validation...
[2026-02-21 10:30:08] INFO: ✓ Distance/time validation passed (checked 15,234 segments)
[2026-02-21 10:30:10] INFO: Phase 3: Preparing transfer graph...
[2026-02-21 10:30:15] INFO: ✓ Transfer graph prepared: 1,247 stops, 18,934 transfers
[2026-02-21 10:30:15] INFO: ✅ All validations passed - ready for graph building
```

---

## Summary of Gaps Now Closed

| Gap | Solution | File |
|-----|----------|------|
| No transfer graph pipeline | TransferGraphBuilder | `transfer_graph_builder.py` |
| ETL mapping not clear | Explicit mapping registry | `etl_mapping_validator.py` |
| No ETL validation | ETLValidator with 4-phase checks | `etl_mapping_validator.py` |
| Distance/time inconsistencies unchecked | DistanceTimeConsistencyValidator | `distance_time_validator.py` |
| No lineage tracking | ETLLineageTracker | `etl_mapping_validator.py` |
| Validation not integrated into build | GraphBuildingValidationPipeline | `graph_validation_pipeline.py` |

---

## Next Steps (If Desired)

1. **Graph Correctness Verification**
   - Add checksums to snapshots
   - Validate graph connectivity
   - Test RAPTOR correctness

2. **Performance Optimizations**
   - Cache transfer graphs
   - Parallel validation
   - Incremental ETL (only changed records)

3. **Real-time Integration**
   - Validate delay propagation
   - Check realtime overlay logic
   - Conflict resolution tests

4. **ML Integration**
   - Validate feature normalization
   - Check model retraining hooks
   - Add confidence scores

5. **Advanced Monitoring**
   - Alert on validation failures
   - Dashboard for data quality
   - SLA tracking
