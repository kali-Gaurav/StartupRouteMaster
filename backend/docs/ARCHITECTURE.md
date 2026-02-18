# RouteMaster Backend Architecture

## Overview

RouteMaster is a high-performance travel route optimization platform designed for sub-100ms response times on typical queries. The backend uses a time-expanded graph representation of transport networks combined with advanced caching and pruning techniques.

## Core Components

### 1. Route Engine (services/route_engine.py)

**Purpose**: Generate optimized multi-segment routes

**Algorithm**: Dijkstra with A* Heuristic

```
┌─────────────────────────────────┐
│   Route Search Request          │
│  (source, dest, date, budget)   │
└────────────┬────────────────────┘
             │
             ▼
     ┌───────────────────┐
     │  Check Cache      │
     └───────┬───────────┘
             │
      ┌──────┴──────┐
      │             │
    MISS          HIT
      │             │
      ▼             ▼
    Build      Return Cached
    Graph      Results
      │          (0ms)
      ▼
┌──────────────────────────┐
│  Dijkstra Search         │
│  - Start: source_station │
│  - End: dest_station     │
│  - Weight: time + cost   │
│  - Constraints:          │
│    • Max 3 transfers     │
│    • 15-60m transfer win │
│    • Max duration: 24h   │
│    • Budget pruning      │
└──────────────────────────┘
      │
      ▼
┌──────────────────────────┐
│  Build Result Paths      │
│  - Reconstruct segments  │
│  - Format durations      │
│  - Sort by cost          │
└──────────────────────────┘
      │
      ▼
┌──────────────────────────┐
│  Cache Results (LRU)     │
│  - Key: (src,dst,d,bud)  │
│  - TTL: 3600 seconds     │
└──────────────────────────┘
      │
      ▼
  Return Routes
```

**Key Optimizations**:

1. **A* Heuristic**: Haversine distance to destination
   - Reduces nodes explored by ~60%
   - Prioritizes paths toward destination

2. **Constraint Pruning**:
   - Discard if duration > 1440 minutes
   - Discard if cost > budget
   - Discard if transfers > 3

3. **Graph Structure**:
   - Time-expanded nodes: (station_id, time_minutes)
   - Edges: Represent available segments
   - Pre-computed and cached at startup

## Cache Service (services/cache_service.py)

**Purpose**: Reduce repeated computations and database load using a distributed cache.

**Technology**: Redis

**Structure**:
```
SearchCache (Redis)
├── Type: Hash
├── Key: "cache:search:{md5_hash_of_query}"
├── TTL: 3600 seconds (configurable)
└── Value: JSON string of route results

GraphCache (In-Memory + Redis)
├── Stations: Loaded into memory at startup from DB.
├── Segments: Loaded into memory at startup from DB.
└── Updated by: RealtimeUpdateService
```

**Performance**:
- Cache hit: <5ms (Redis)
- Cache miss: 40-120ms (depending on route complexity)
- A high cache-hit ratio is critical for performance at scale.

### 3. Real-time Update Service

**Purpose**: Ingest real-time data feeds (GTFS-RT) to provide live updates.

**Flow**:
```
┌──────────────────────────┐
│ GTFS-RT Feed URL         │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│ Poll Feed (every 30s)    │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│ Parse Trip Updates/Alerts│
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│ Update In-Memory Graph   │
│ - Adjust segment delays │
│ - Mark cancelled trips  │
└──────────────────────────┘
```
**Impact**: This service ensures that route results reflect real-world conditions, such as delays and cancellations, making the system far more reliable and useful.

### 4. Payment Service (services/payment_service.py)

**Purpose**: Razorpay integration for seamless payments.

**Flow**:
```
POST /api/create_order
    ↓
Check Razorpay Config
    ├─ Not configured: Return error message
    └─ Configured: Create order via Razorpay API
    ↓
POST /api/payment/webhook
    ↓
Verify Signature: HMAC-SHA256
    ├─ Valid: Mark booking as completed
    └─ Invalid: Reject payment
```

### 5. Booking Service (services/booking_service.py)

**Purpose**: Manages the lifecycle of user bookings.

**Lifecycle**:
```
1. Route Found → User selects a route.
2. Booking Initiated → Create Booking (user_id, route_id), status 'pending'.
3. Payment Verified → Update booking.payment_status to 'confirmed'.
4. Review Submitted → Create Review (user_id, booking_id).
```

## Time-Expanded Graph

The core algorithm uses a time-expanded graph representation:

```
Stations:  Mumbai (19.07°N, 72.87°E)
           Goa (15.29°N, 73.82°E)

Segments:  Train departing 10:00 → arrives 22:00 (cost ₹450)
           Flight departing 09:00 → arrives 11:00 (cost ₹3500)

Graph Nodes:
           (Mumbai, 600m)  ─train→  (Goa, 1320m)
           (Mumbai, 540m)  ─flight→ (Goa, 660m)

Search: Find path from (Mumbai, 0m) to (Goa, inf)
Output: List of paths, each with cost and duration
```

## Performance Characteristics

### Time Complexity

| Operation | Complexity | Typical Time |
|-----------|------------|--------------|
| Route Search | O(E log V) | 40-120ms (miss)|
| Cache Hit | O(1) | <5ms (Redis) |
| Graph Build | O(S + E) | 2s (at startup) |

Where:
- S = number of stations
- E = number of segments
- V = time-expanded nodes

### Space Complexity

| Component | Memory |
|-----------|--------|
| Graph (in-memory) | ~50MB - 500MB (depends on network size) |
| Redis Cache | Scaled independently |
| API Instance | ~50MB |

## API Request Flow (with Authentication)

```
┌─────────────────────────────────────────┐
│ Frontend Request (POST /api/search)     │
│ Authorization: Bearer <JWT_TOKEN>       │
└────────────────┬────────────────────────┘
                 │
                 ▼
        ┌────────────────────┐
        │ Authenticate User  │
        │ (Validate JWT)     │
        └────────┬───────────┘
                 │
                 ▼
        ┌────────────────────┐
        │ Validate Input     │
        └────────┬───────────┘
                 │
                 ▼
        ┌────────────────────┐
        │ Check Redis Cache  │
        └────────┬───────────┘
                 │
         ┌───────┴────────┐
         │                │
       HIT              MISS
         │                │
         ▼                ▼
    Return from      RouteEngine
    Cache            .search_routes()
    (<5ms)                │
         │                ▼
         │         Graph.Dijkstra()
         │              │
         │        Build & Sort Results
         │              │
         │         Save to Redis Cache
         │              │
         └─────┬────────┘
               │
               ▼
    ┌──────────────────────────┐
    │ Format & Return Response │
    └──────────────────────────┘
```

## Database Schema & Relationships

```
Users
├── id (UUID, PK)
├── email (VARCHAR, UNIQUE)
├── password_hash (VARCHAR)
└── phone_number (VARCHAR)
     ▲
     │ (one-to-many)
     │
  Bookings ───────────────────► Reviews
  ├── id (UUID, PK)            ├── id (UUID, PK)
  ├── user_id (FK)             ├── user_id (FK)
  ├── route_id (FK)            ├── booking_id (FK)
  ├── travel_date (VARCHAR)    ├── rating (INT)
  ├── payment_status (VARCHAR) └── comment (TEXT)
  └── booking_details (JSONB)
       │           ▲
       │(one-to-one)│ (one-to-many)
       │           │
  Payments      Routes
  ├── id (UUID, PK)            ├── id (UUID, PK)
  ├── booking_id (FK)          ├── source (VARCHAR)
  ├── razorpay_order_id (VARCHAR)├── destination (VARCHAR)
  └── status (VARCHAR)         ├── segments (JSONB)
                               ├── total_duration (VARCHAR)
                               └── total_cost (FLOAT)

Vehicles ◄─────────────────── Segments ───────────────────► Stations
├── id (UUID, PK)            ├── id (UUID, PK)            ├── id (UUID, PK)
├── vehicle_number (VARCHAR) ├── vehicle_id (FK)          ├── name (VARCHAR)
├── type (VARCHAR)           ├── source_station_id (FK)   ├── city (VARCHAR)
└── operator (VARCHAR)       ├── dest_station_id (FK)     ├── latitude (FLOAT)
                             ├── departure_time (VARCHAR) └── longitude (FLOAT)
                             ├── arrival_time (VARCHAR)
                             ├── duration_minutes (INT)
                             ├── cost (FLOAT)
                             └── operating_days (VARCHAR)
```

## Error Handling Strategy

```
try:
    Perform Operation
catch ValidationError:
    Return 400 (Bad Request)
catch NotFoundError:
    Return 404 (Not Found)
catch AuthenticationError:
    Return 401 (Unauthorized)
catch Exception:
    Log Error
    Return 500 (Internal Server Error)
```

## Security

1. **Authentication**: JWT Bearer Tokens for user sessions.
2. **Admin Auth**: Separate X-Admin-Token header.
3. **Payment Verification**: HMAC-SHA256 signature.
4. **Input Validation**: Pydantic schemas.
5. **SQL Injection Prevention**: SQLAlchemy ORM.
6. **CORS**: Configured for frontend domain.

## Monitoring & Observability

### Logging
- Structured logs (JSON) with request IDs.
- Log levels: DEBUG, INFO, WARNING, ERROR.

### Metrics (Prometheus/Grafana via an exporter)
- `requests_total`: Total number of API requests.
- `request_latency_seconds`: Histogram of request latencies.
- `cache_hits_total`, `cache_misses_total`: Cache performance.
- `realtime_updates_total`: Number of real-time updates processed.

## Deployment Considerations

### Horizontal Scaling
- Stateless API instances can be added behind a load balancer.
- Redis provides a shared cache for all instances.
- The database remains the single source of truth.

## Testing Strategy

### Unit Tests
- Algorithm correctness (Dijkstra).
- Service logic (user creation, booking state changes).
- Utility functions (time formatting, validation).

### Integration Tests
- API endpoints with a test database and mock Redis.
- Full user journey: Register → Search → Book → Pay → Review.
- Real-time update service parsing and applying updates.

### Performance Tests (Load Testing)
- Use tools like Locust or k6.
- Target P95 latency < 100ms for cached responses.
- Target P95 latency < 250ms for uncached searches.
- Ensure the system can handle N concurrent users without degradation.
