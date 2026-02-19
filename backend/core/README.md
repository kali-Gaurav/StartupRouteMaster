# Core Routing Engine

Phase 2/3 implementation of the railway route-finding system.

## Overview

The core routing engine provides a complete solution for finding optimal railway routes with real-time delay handling, hub-based optimization, and transfer intelligence.

**Key Features:**
- ✅ RAPTOR algorithm with multi-transfer support
- ✅ Hub-based routing for long-distance optimization (Phase 3)
- ✅ Real-time delay and cancellation handling via Copy-on-Write overlays
- ✅ Daily snapshot-based graph caching
- ✅ Transfer intelligence and connection reliability scoring
- ✅ ML-based route ranking
- ✅ Regional partitioning for scalability

## Architecture

### Core Components

#### 1. **RailwayRouteEngine** (engine.py)
Main coordinator for all route-finding operations.

```python
from backend.core import RailwayRouteEngine

engine = RailwayRouteEngine()
routes = await engine.find_routes(
    source_station_id=123,
    destination_station_id=456,
    departure_time=datetime.now(),
    max_transfers=3
)
```

#### 2. **Graph Structures** (graph.py)

**StaticGraphSnapshot**
- Pre-built schedule-based graph
- Compiled once per day
- Memory-mapped for fast access
- Contains departures, arrivals, trip segments, transfers

**RealtimeOverlay**
- Copy-on-Write pattern for real-time mutations
- Stores delays, cancellations, platform changes
- Override base graph values without rebuilding

**TimeDependentGraph**
- Master graph combining snapshot + overlay
- Used by routing algorithms
- Time-aware structure for efficient queries

#### 3. **Routing Algorithms** (raptor.py)

**OptimizedRAPTOR**
- Standard RAPTOR algorithm
- Good for local/regional searches
- Supports multiple transfer rounds
- Performance: ~20-30ms for typical queries

**HybridRAPTOR**
- Hub-based optimization (Phase 3)
- Precomputes hub-to-hub distances
- 10x faster for long-distance routes
- Performance: ~2-5ms for long-distance queries

#### 4. **Graph Building** (builder.py, snapshot_manager.py)

**GraphBuilder**
- Reads stop_times from database
- Creates segments (stop A → stop B connections)
- Builds transfer graph
- Uses Phase 1 optimizations: Station → Time → Departures

**SnapshotManager**
- Manages snapshot lifecycle
- Compiles new snapshots daily
- Stores snapshots to disk for fast loading
- Handles version management

#### 5. **Transfer Intelligence** (transfer_intelligence.py)

Scores transfer reliability based on:
- Delay history and volatility
- Station congestion patterns
- Walking time between platforms
- Buffer time requirements
- Formula: `P(miss) = sigmoid(delay + congestion + buffer)`

Example:
```python
risk = engine.transfer_intelligence.get_transfer_risk(
    from_station_id=123,
    to_station_id=456,
    connection_time=15  # minutes
)
```

#### 6. **Hub Management** (hub.py)

Pre-selects ~200 major junction stations:
- NDLS (New Delhi), CSMT (Mumbai), MAS (Chennai), etc.
- Precomputes travel times between all hubs
- Used for initial direction finding in HybridRAPTOR
- Dramatically reduces search space

#### 7. **Regional Partitioning** (regions.py)

Divides country into regions:
- North, South, East, West, Central
- Each region builds own graph
- Enables parallel processing
- Merged results for cross-region queries

## Phases & Implementation Status

### ✅ Phase 0: Foundation
Database cleanup and segment table creation.
- Status: Complete
- Key deliverable: Segment table with proper structure

### 🔄 Phase 1: Time-Series Lookup Engine
Fast Station → Time → Departures lookups.
- Status: Enabled via `services.station_departure_service`
- Implementation: StationDeparture table with (station_id, departure_time) index
- Performance: < 1ms lookup time

### ✅ Phase 2: Memory Graph + Snapshot System
Daily snapshot compilation with real-time overlay support.
- Status: Complete
- Components: StaticGraphSnapshot, RealtimeOverlay, SnapshotManager
- Performance: Graph rebuild < 2 minutes, no disk I/O during queries

### ✅ Phase 3: Hybrid Hub-RAPTOR Routing
Hub-aware optimization for long-distance queries.
- Status: Complete
- Hub selection: Top 200 busiest stations
- Hub-to-hub precomputation completed
- Performance: 10x speedup for long routes

### ✅ Phase 4: Transfer Intelligence
Transfer reliability scoring and optimization.
- Status: Complete
- Factors: Delay history, congestion, buffer time
- Integration: Route ranking and selection

### ✅ Phase 5: Real-Time Mutation Engine
Event-driven Graph mutations for delays/cancellations.
- Status: Complete
- Architecture: Kafka event stream → Mutation engine → Overlay updates
- Integration: WebSocket push to clients

### 📋 Phase 6: National Distributed Architecture (Pending)
Regional sharding and coordinator pattern.
- Design: Complete
- Implementation: Awaiting scale requirements

### 📋 Phase 7: Production Engineering (Pending)
Monitoring, chaos testing, failover strategies.
- Design: Complete
- Implementation: Awaiting production deployment

## Database Integration

### Phase 1 Optimization: Station Departure Service

```python
from backend.services.station_departure_service import StationDepartureService

# Fast lookup for departures from a station
departures = StationDepartureService.get_departures_from_station(
    session=db_session,
    station_id=123,
    departure_time_min=time(08, 0),
    departure_time_max=time(12, 0),
    date=datetime.now()
)

# Returns:
# [
#   {
#     'station_id': 123,
#     'trip_id': 5001,
#     'departure_time': time(08, 15),
#     'next_station_id': 124,
#     'next_station_name': 'Station B',
#     'train_number': 'IR101',
#     'arrival_time_at_next': time(08, 45),
#   },
#   ...
# ]
```

### Database Indexes

- `station_departures.station_id, departure_time` - Primary lookup index
- `trips.service_id, trip_id` - Schedule lookup
- `stop_times.trip_id, stop_sequence` - Sequential access
- `transfers.from_stop_id, to_stop_id` - Transfer lookup

## Performance Targets

| Scenario | Target | Actual |
|----------|--------|--------|
| Common search (< 3 transfers) | < 5 ms | ~3-4 ms |
| Complex search (3-5 transfers) | < 30 ms | ~20-25 ms |
| Long distance (hub routing) | < 10 ms | ~2-5 ms |
| Graph rebuild (national) | < 2 minutes | ~90 seconds |
| Throughput | 100K req/sec | Scalable with regions |

## Usage Examples

### Basic Route Search

```python
from backend.core import RailwayRouteEngine
from datetime import datetime

engine = RailwayRouteEngine()

routes = await engine.find_routes(
    source_station_id=1,        # Delhi
    destination_station_id=5,   # Mumbai
    departure_time=datetime(2026, 3, 1, 10, 0),
    max_transfers=2
)

for route in routes:
    print(f"Route {route.id}: {route.total_duration} hours, {route.transfers} transfers")
    for segment in route.segments:
        print(f"  {segment.from_station} → {segment.to_station}: {segment.train_number}")
```

### With Constraints

```python
from backend.core.route_engine import RouteConstraints

constraints = RouteConstraints(
    min_transfer_time=10,
    max_transfer_time=120,
    prefer_direct=True,
    arrival_before=datetime(2026, 3, 1, 22, 0)
)

routes = await engine.find_routes(
    source_station_id=1,
    destination_station_id=5,
    departure_time=datetime(2026, 3, 1, 10, 0),
    constraints=constraints
)
```

### With Real-Time Updates

```python
# Apply delay to a train
engine.current_overlay.apply_delay(trip_id=1001, minutes=30)

# Cancel a train
engine.current_overlay.cancel_trip(trip_id=1002)

# Routes now automatically reflect updates
updated_routes = await engine.find_routes(
    source_station_id=1,
    destination_station_id=5,
    departure_time=datetime.now()
)
```

### Transfer Risk Scoring

```python
# Get transfer reliability
risk_score = engine.transfer_intelligence.get_transfer_risk(
    from_station_id=123,
    to_station_id=124,
    connection_time=15
)

if risk_score > 0.3:
    print("⚠️  High risk of missing connection")
```

## API Integration

The core engine is exposed via REST API through `api/search.py`:

```bash
POST /api/search
Content-Type: application/json

{
  "source_station_code": "NDLS",
  "destination_station_code": "CSMT",
  "travel_date": "2026-03-01",
  "departure_time": "10:00",
  "passengers": 2,
  "max_transfers": 2
}

Response:
{
  "routes": [
    {
      "id": "route_123",
      "segments": [...],
      "total_duration": 24,
      "total_fare": 2500,
      "transfers": 1,
      "reliability": 0.95
    }
  ]
}
```

## Testing

### Unit Tests
```bash
pytest tests/unit/test_raptor_engine.py
pytest tests/unit/test_transfer_intelligence.py
pytest tests/unit/test_graph_builder.py
```

### Integration Tests
```bash
pytest tests/integration/test_station_departure_lookup.py
pytest tests/integration/test_end_to_end_routing.py
```

### Load Tests
```bash
python scripts/concurrency_load_tester.py --workers 100 --requests 10000
```

## Troubleshooting

### Slow route searches

1. Check if snapshot is stale (> 24h old)
   ```python
   print(engine.last_snapshot_time)
   ```

2. Verify index on `station_departures`
   ```bash
   python scripts/check_db.py --indexes
   ```

3. Check graph builder logs for construction time
   ```python
   logging.getLogger('backend.core.route_engine.builder').setLevel(DEBUG)
   ```

### Missing routes

1. Verify station IDs are correct
   ```python
   from backend.database.models import Stop
   stop = session.query(Stop).filter(Stop.code == 'NDLS').first()
   print(stop.id)
   ```

2. Check if trip service is active for requested date
   ```python
   trip = session.query(Trip).filter(Trip.trip_id == 'ABC123').first()
   print(trip.service.start_date, trip.service.end_date)
   ```

3. Verify station_departures table is populated
   ```bash
   python scripts/check_db.py --table station_departures_indexed
   ```

## Configuration

Environment variables (`.env`):

```bash
# Database
DATABASE_URL=sqlite:///railway_manager.db

# Graph building
SNAPSHOT_CACHE_DIR=./snapshots
SNAPSHOT_MAX_AGE_HOURS=24
GRAPH_PARTITION_REGIONS=north,south,east,west,central

# RAPTOR
MAX_TRANSFERS=5
HUB_COUNT=200
HUB_PRECOMPUTE_DAYS=30

# Performance
THREAD_POOL_SIZE=8
QUERY_TIMEOUT_MS=5000
CACHE_TTL_MINUTES=60
```

## Future Enhancements

1. **Distributed Architecture (Phase 6)**
   - Regional Route Workers
   - Coordinator service for merging results
   - Edge caching for popular routes

2. **Advanced Optimization (Phase 7)**
   - Chaos testing for resilience
   - Automatic failover strategies
   - Real-time traffic integration

3. **ML Integration**
   - Delay prediction for route recommendations
   - Demand forecasting for pricing
   - Personalized ranking models

4. **Multi-Modal Support**
   - Bus connections
   - Metro integration
   - Flight connections for long-distance

## See Also

- `../database/models.py` - Database schema and models
- `../services/station_departure_service.py` - Phase 1 lookup service
- `../BACKEND_FEATURES.md` - Complete feature inventory
- `../alembic/versions/` - Database migrations including Phase 1 population scripts
