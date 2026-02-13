# Database Architecture Deep Dive 🏗️

## Overview: Two Database Systems

Your project uses **TWO SEPARATE DATABASE SYSTEMS** with different purposes:

### 1. **railway_manager.db** (SQLite) 📦
- **Type**: SQLite (file-based, local)
- **Purpose**: Raw railway data source (master data for trains, schedules, fares)
- **Location**: `backend/railway_manager.db` 
- **Owner**: External data provider / legacy system
- **Access**: Read-only scripts pull data from here

### 2. **Supabase PostgreSQL** (Cloud) ☁️
- **Type**: PostgreSQL (managed cloud service)
- **Purpose**: Application-specific tables (user bookings, sessions, routes, preferences)
- **Config**: `DATABASE_URL` env variable (Supabase connection string)
- **Owner**: Your RouteMaster application
- **Access**: FastAPI application reads/writes daily

---

## Database Schemas Comparison 🔍

### SQLite: `railway_manager.db` Tables
From the screenshot you showed, the SQLite database contains:

```
Tables (Railway Master Data):
├── audit_logs              # User activity tracking
├── bot_metrics             # Chatbot performance stats
├── error_logs              # System errors
├── geocode_cache           # Lat/lon lookup cache
├── journey_history         # User journey logs
├── migration_history       # Schema change history
├── notification_preferences
├── notifications
├── passenger_locations     # Real-time passenger location
├── saved_routes            # User favorite routes
├── sos_chat_history        # SOS chatbot history
├── sos_requests            # Emergency requests
├── sqlite_sequence         # Internal SQLite metadata
├── stations_master         # ALL STATIONS with codes, cities, states
├── train_fares             # Fare information (class-wise, season-based)
├── train_routes            # 🔴 MAIN: Train routes (raw from external source)
├── train_running_days      # Train operating schedule (Mon-Sun)
├── train_schedule          # Detailed train timetables (departure/arrival times)
├── trains_active           # Currently active trains list
├── trains_master           # All registered trains (metadata)
├── user_preferences        # User profile settings
├── user_sessions           # Active sessions
└── webhook_logs            # API webhook events
```

#### Key Tables in SQLite:

**stations_master** (Master station list)
```sql
CREATE TABLE stations_master (
  id INTEGER PRIMARY KEY,
  station_code TEXT UNIQUE,        -- e.g., "NDLS", "BCT", "KOTA"
  station_name TEXT,               -- e.g., "New Delhi", "Mumbai Central"
  city TEXT,
  state TEXT,
  is_junction BOOLEAN,
  latitude FLOAT,
  longitude FLOAT,
  geo_hash TEXT
);
```

**train_routes** (Raw route data - the main table you asked about!)
```sql
CREATE TABLE train_routes (
  id INTEGER PRIMARY KEY,
  train_id INTEGER,                -- FK to trains_master
  source_station_code TEXT,        -- FK to stations_master
  destination_station_code TEXT,   -- FK to stations_master
  route_sequence INTEGER,          -- 1, 2, 3... (order of stops)
  distance_km FLOAT,
  estimated_duration MINUTES,
  route_type TEXT,                 -- e.g., "express", "mail", "passenger"
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

**train_schedule** (Timetable for each train-route combo)
```sql
CREATE TABLE train_schedule (
  id INTEGER PRIMARY KEY,
  train_id INTEGER,
  route_segment_id INTEGER,        -- Links train_routes + train_running_days
  departure_time TIME,             -- 08:00, 14:30, etc.
  arrival_time TIME,
  halt_time_minutes INTEGER,
  platform_number TEXT,
  created_at TIMESTAMP
);
```

**train_running_days** (Operating days mask)
```sql
CREATE TABLE train_running_days (
  id INTEGER PRIMARY KEY,
  train_id INTEGER,
  monday BOOLEAN,
  tuesday BOOLEAN,
  wednesday BOOLEAN,
  thursday BOOLEAN,
  friday BOOLEAN,
  saturday BOOLEAN,
  sunday BOOLEAN
);
```

**train_fares** (Cost information)
```sql
CREATE TABLE train_fares (
  id INTEGER PRIMARY KEY,
  train_id INTEGER,
  route_segment_id INTEGER,
  seat_class TEXT,                 -- "1AC", "2AC", "3AC", "SL", "General"
  base_fare FLOAT,
  reservation_charge FLOAT,
  total_fare FLOAT,
  season TEXT,                     -- "peak", "normal", "off"
  effective_from DATE,
  effective_to DATE
);
```

---

### PostgreSQL: Supabase Schema
Your application-facing database with simplified, normalized tables:

```
Tables (Application Data):
├── stations                # Application stations (1:1 or derived from stations_master)
│   ├── id (UUID)
│   ├── name, city
│   ├── latitude, longitude
│   └── created_at
│
├── segments                # Travel segments (derived from train_schedule + train_routes)
│   ├── id (UUID)
│   ├── source_station_id → stations
│   ├── dest_station_id → stations
│   ├── transport_mode ("train", "bus", "flight")
│   ├── departure_time, arrival_time
│   ├── duration_minutes
│   ├── cost (single fare)
│   ├── operator
│   ├── operating_days (bitmask: "1111111")
│   └── created_at
│
├── routes                  # Computed route results (persisted for caching)
│   ├── id (UUID)
│   ├── source, destination (station names)
│   ├── segments (JSONB array) ← contains the actual journey steps
│   ├── total_duration, total_cost
│   ├── budget_category ("economy", "standard", "premium")
│   ├── num_transfers
│   └── created_at
│
├── bookings                # User bookings
│   ├── id (UUID)
│   ├── user_name, user_email, user_phone
│   ├── route_id → routes
│   ├── travel_date
│   ├── payment_status
│   ├── amount_paid
│   └── created_at
│
└── payments                # Payment records
    ├── id, booking_id → bookings
    ├── razorpay_order_id, razorpay_payment_id
    ├── status, amount
    └── created_at
```

---

## Data Flow Architecture 🔄

### **Current Flow (What Exists)**

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL DATA SOURCE                         │
│              (railway_manager.db - SQLite)                    │
│  Contains: trains, schedules, fares, routes, running days      │
└────────────────────────────┬────────────────────────────────────┘
                             │ (copy_tables.py)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              WORKSPACE LOCAL DATABASE                           │
│              (railway_manager.db - SQLite)                      │
│  Purpose: Backup/staging area for inspection & development     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                    (CURRENTLY NO ETL)
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              APPLICATION DATABASE                              │
│            (Supabase PostgreSQL - Cloud)                       │
│  Contains: stations, segments, routes, bookings, payments      │
│  Status: ⚠️ MANUALLY SEEDED or partially populated             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              API LAYER (FastAPI)                                │
│  - Uses RouteEngine to read segments/stations                  │
│  - Runs Dijkstra search to find routes                         │
│  - Persists results in routes table                            │
│  - Returns routes to frontend                                  │
└─────────────────────────────────────────────────────────────────┘
```

### **What's Missing: ETL Pipeline** 🔴

There is **NO integrated ETL (Extract, Transform, Load)** process that:
1. Reads from `railway_manager.db` (SQLite)
2. Transforms train_routes → segments (PostgreSQL model)
3. Loads into Supabase tables (stations, segments)

**Current State**:
- ✅ `copy_tables.py` copies SQLite tables locally (redundant)
- ✅ `seed_stations.py` loads stations from JSON manually
- ❌ No script to populate segments from train_schedule + train_routes
- ❌ No automated sync when railway_manager01.db updates
- ⚠️  Segments table may be empty or manually created in tests

---

## Critical Architecture Issues ⚠️

### Issue 1: Disconnected Data Sources
**Problem**: 
- SQLite has detailed train schedules, routes, fares
- Supabase has abstract "segments" that should represent train services
- **No bridge between them exists**

**Impact**:
- RouteEngine reads from Supabase `segments` table
- If `segments` is empty/incomplete, search returns no results
- User bookings can't reference real train data

**Solution**:
```python
# MISSING: ETL Script
def etl_sqlite_to_supabase():
    """
    Read from railway_manager.db:
      1. Load trains_master + train_schedule + train_routes + train_fares
      2. For each combination, create a Segment:
         - source_station_id, dest_station_id
         - departure_time, arrival_time (from train_schedule)
         - duration_minutes
         - cost (from train_fares)
         - operator (from trains_master)
         - operating_days (from train_running_days)
      3. Insert into Supabase segments table
    """
```

---

### Issue 2: Multiple Station Representations
**Problem**:
- SQLite: `stations_master` (comprehensive, with ~1000+ stations)
- Supabase: `stations` table (may be empty or test data only)
- Supabase: `StationMaster` model (separate table that duplicates stations_master)

**Impact**:
- Station search might fail if Supabase `stations` is not synced
- Redundant data structures cause inconsistency

**Solution**:
```python
# ETL sync stations_master → Supabase stations
def sync_stations():
    """Load stations_master from SQLite to Supabase"""
    sqlite_stations = read_from_sqlite('stations_master')
    for station in sqlite_stations:
        create_in_supabase(
            name=station.station_name,
            city=station.city,
            latitude=station.latitude,
            longitude=station.longitude
        )
```

---

### Issue 3: Routes Table Misuse
**Problem**:
- `routes` table is for persisting **search results** (computed routes)
- But code sometimes treats it as if it stores **train routes** (like SQLite's train_routes)
- Schema mismatch: routes.segments is JSON, not a foreign key to segments table

**Impact**:
- Routes are redundantly stored (once as segments JSONB, no normalized reference)
- Hard to query "which bookings used which trains"
- Data denormalization makes updates difficult

**Better Design**:
```
Route should reference Segment array, not duplicate data:
routes {
  id, source, destination, total_cost, total_duration,
  segment_ids: UUID[] ← reference actual segments, not duplicate JSON
}
```

---

## What Each Table Actually Stores 📋

### Supabase: `segments` Table (Core)
**Represents**: A single transportable leg (one train service from station A to B)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "source_station_id": "station_001",
  "dest_station_id": "station_002",
  "transport_mode": "train",
  "departure_time": "08:00",
  "arrival_time": "14:30",
  "duration_minutes": 390,
  "cost": 850.50,
  "operator": "Indian Railways",
  "operating_days": "1111111",  ← Mon=1, Tue=1, ... Sun=1
  "created_at": "2026-02-01T00:00:00Z"
}
```

**Source**: Should be derived from SQLite `train_schedule` + `train_routes` + `train_fares`

---

### Supabase: `routes` Table (Results Cache)
**Represents**: A computed multi-leg journey (result of search algorithm)

```json
{
  "id": "route-550e8400-e29b-41d4-a716-446655440050",
  "source": "New Delhi",
  "destination": "Mumbai Central",
  "segments": [
    {
      "segment_id": "550e8400-e29b-41d4-a716-446655440001",
      "mode": "train",
      "from": "NDLS",
      "to": "BRC",
      "duration": "3h 20m",
      "cost": 800.0,
      "departure": "08:00",
      "arrival": "11:20",
      "operator": "Central Railways",
      "details": "Train 12345"
    },
    {
      "segment_id": "550e8400-e29b-41d4-a716-446655440002",
      "mode": "train",
      "from": "BRC",
      "to": "BCT",
      "duration": "18h 15m",
      "cost": 950.0,
      "departure": "14:00",
      "arrival": "08:15",
      "operator": "Central Railways",
      "details": "Train 12907"
    }
  ],
  "total_duration": "21h 35m (with 2h wait)",
  "total_cost": 1750.0,
  "budget_category": "economy",
  "num_transfers": 1,
  "created_at": "2026-02-12T10:30:00Z"
}
```

**Source**: Generated by `RouteEngine.search_routes()` from segments

---

## Data Relationships 🔗

### SQLite Relations
```
trains_master
  ├─ 1──N ──> train_schedule
  ├─ 1──N ──> train_routes
  ├─ 1──1 ──> train_running_days
  └─ 1──N ──> train_fares

train_routes
  ├─ N──1 ──> trains_master
  ├─ N──1 ──> stations_master (source_station_code)
  └─ N──1 ──> stations_master (destination_station_code)

train_schedule
  ├─ N──1 ──> trains_master
  └─ N──1 ──> train_routes (implicit via train_id)
```

### PostgreSQL Relations
```
stations
  ├─ 1──N ──> segments (as source_station_id)
  ├─ 1──N ──> segments (as dest_station_id)

segments
  └─ represents one train_schedule entry in Supabase form

routes
  └─ segments: JSONB array
     (denormalized copy of segment details for caching)

bookings
  ├─ N──1 ──> routes
  └─ 1──1 ──> payments
```

---

## How Routes are Produced 🏗️

### Step 1: User Search
```
Frontend POST /api/search
  → source: "New Delhi"
  → destination: "Mumbai"
  → date: "2026-02-15"
  → budget: "economy"
```

### Step 2: RouteEngine Queries
```python
# In route_engine.py search_routes()

# 1. Find stations by name
source_station = db.query(Station).filter(name="New Delhi").first()
dest_station = db.query(Station).filter(name="Mumbai").first()

# 2. Pre-filter segments by:
#    - Operating days (check bitmask against requested date)
#    - Duration (max 12 hours)
#    - Geography (corridor filter)
segments = db.query(Segment)\
  .filter(operating_days matches travel_date)\
  .filter(duration_minutes <= 720)\
  .filter(source/dest in valid_station_set)\
  .all()

# 3. Build in-memory graph
graph = TimeExpandedGraph()
for segment in segments:
  graph.add_edge(
    from_station=segment.source_id,
    to_station=segment.dest_id,
    from_time=parse_time(segment.departure_time),
    to_time=parse_time(segment.arrival_time),
    cost=segment.cost,
    segment_id=segment.id
  )

# 4. Run Dijkstra search
paths = dijkstra_search(graph, source_station, dest_station, ...)

# 5. Construct route objects from paths
for path in paths:
  route = _construct_route(path, segments_map, ...)
  routes.append(route)
```

### Step 3: Persist & Return
```python
# BookingService saves to routes table
booking_service.save_route(
  source=source,
  destination=destination,
  segments=route['segments'],  # JSONB array
  total_duration=route['total_duration'],
  total_cost=route['total_cost'],
  budget_category=budget_category
)
# Returns route ID

# Return to user
return {
  "routes": [
    {
      "id": "route_uuid",
      "source": "New Delhi",
      "destination": "Mumbai",
      "total_cost": 1750.0,
      "total_duration": "21h 35m",
      "budget_category": "economy",
      "num_transfers": 1
    }
  ]
}
```

### Step 4: User Selects & Books
```
Frontend POST /api/payments/create-order
  → route_id: "route_uuid"
  → user_name, email, phone
  → travel_date: "2026-02-15"
```

Creates Booking → references routes.id

---

## Current Code Flow 🔄

### Where Data is READ:
- **RouteEngine** (`backend/services/route_engine.py`):
  - Queries `Station` table
  - Queries `Segment` table
  - Builds/searches graph in memory
  - Returns route dicts

- **BookingService** (`backend/services/booking_service.py`):
  - Reads `Route` (to attach bookings)
  - Reads `Booking` (for user queries)

### Where Data is WRITTEN:
- **BookingService.save_route()**:
  - Inserts into `routes` table
  - Stores segments as JSONB
  - Returns route ID

- **BookingService.create_booking()**:
  - Inserts into `bookings` table
  - References route_id foreign key

- **search.py** endpoint:
  - Calls RouteEngine.search_routes()
  - Calls BookingService.save_route() for each result
  - Caches in CacheService (in-memory)

---

## Recommended Architecture (Improved) ✅

### Phase 1: Build ETL Pipeline
```
Create: backend/etl/sqlite_to_postgres.py
Steps:
  1. Read stations_master from SQLite
     → Sync to Supabase stations table
  
  2. Read train_schedule + train_routes + train_fares from SQLite
     → Transform to Segment rows
     → Sync to Supabase segments table
  
  3. Upsert (update if exists) to handle re-runs
  
  4. Index all location/time columns for performance

Run: Daily/hourly cron job via Cloud Functions
```

### Phase 2: Normalize Routes Table
```
Current (bad):
  routes {
    segments: JSONB (denormalized copy)
  }

Better:
  routes {
    segment_ids: UUID[] (references to segments)
  }

This allows:
  - Querying "which bookings used train 12345"
  - Updating segment info without re-storing
  - Consistent data
```

### Phase 3: Add Caching Layer
```
Current: CacheService (in-memory, per-search)

Better:
  - Redis: Cache route search results by (source, dest, date)
  - TTL: 1 hour
  - Invalidate on: segment.cost changes, etc.
```

---

## Summary Table 📊

| Aspect | SQLite | PostgreSQL | Status |
|--------|--------|------------|--------|
| **Purpose** | Raw railway master data | Application data | ✅ Both exist |
| **Stations** | stations_master (complete) | stations (may be empty) | ❌ Not synced |
| **Trains** | trains_master, train_routes | ❌ Not modeled | ❌ Gap |
| **Schedules** | train_schedule (detailed) | segments (simplified) | ⚠️ Manual mapping |
| **Fares** | train_fares (comprehensive) | segment.cost (single field) | ⚠️ Simplified |
| **Bookings** | ❌ Not in SQLite | bookings (user bookings) | ✅ Primary app |
| **ETL** | None | ❌ Missing | ❌ GAP |
| **Sync** | copy_tables.py (file copy) | Manual or none | ❌ Incomplete |

---

## Action Plan 🎯

To make the system production-ready:

1. **[ ] CREATE ETL SCRIPT**
   - File: `backend/etl/populate_segments.py`
   - Read from railway_manager.db (or 01.db)
   - Transform train_schedule → Segment rows
   - Load into Supabase segments table
   - Tag task: ~4 hours work

2. **[ ] SYNC STATIONS**
   - File: `backend/etl/sync_stations.py`
   - Read stations_master from SQLite
   - Insert/update in Supabase stations
   - Add indexes for city/name search
   - Tag task: ~1 hour work

3. **[ ] TEST WITH DATA**
   - Run ETL script
   - Verify segments table is populated
   - Test RouteEngine search with real data
   - Verify routes are returned
   - Tag task: ~2 hours work

4. **[ ] SCHEDULE RECURRING SYNC**
   - Supabase cron (or scheduler)
   - Run ETL daily at off-peak hours
   - Alert on failures
   - Tag task: ~1 hour work

---

## Files to Study 📚

### Understanding Current Architecture:
1. `backend/models.py` — Define all DB tables (ORM models)
2. `backend/services/route_engine.py` — How routes are created
3. `backend/services/booking_service.py` — How data is persisted
4. `supabase/migrations/20260211205016_create_routemaster_tables.sql` — PostgreSQL schema

### Understanding Data Sources:
1. `scripts/inspect_db.py` — Inspect SQLite schema
1. `scripts/copy_tables.py` — Copy logic between SQLite instances
3. `backend/seed_stations.py` — Load stations from JSON

### ETL/Integration (To Be Created):
1. `backend/etl/sqlite_to_postgres.py` — Main ETL *(Create This!)*
2. `backend/etl/tests/test_etl.py` — Test ETL *(Create This!)*

---

## Questions This Raises ❓

1. **Where should segment data come from in dev?**
   - Option A: ETL from railway_manager.db
   - Option B: Use test fixtures / sample data

2. **Should railway_manager.db stay in git?**
   - It's a data file (likely large)
   - Consider storing in cloud storage (S3) instead

3. **Should tests use real data or fixtures?**
   - Real: Slower, realistic
   - Fixtures: Fast, predictable

4. **How often to sync railway_manager.db?**
   - Daily? Weekly?
   - Should refresh on app startup?

---

## Next Steps 🚀

1. Confirm the ETL is missing (it is)
2. Decide on implementation approach
3. Build sync script
4. Add automated scheduling
5. Test end-to-end (search → booking)
