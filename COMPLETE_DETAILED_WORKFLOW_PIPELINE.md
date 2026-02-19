# ROUTEMASTER - COMPLETE DETAILED WORKFLOW PIPELINE
## End-to-End Query Processing & Route Generation Architecture

**Date**: February 2026  
**Version**: 1.0 - CONSOLIDATED (Route Engine Only)  
**Status**: Production-Grade Implementation

---

## 📋 TABLE OF CONTENTS

1. [Overview](#overview)
2. [Architecture Layers](#architecture-layers)
3. [Complete Request Flow](#complete-request-flow)
4. [Detailed Component Pipeline](#detailed-component-pipeline)
5. [Route Generation Algorithm (RAPTOR)](#route-generation-algorithm)
6. [Validation & Quality Checks](#validation--quality-checks)
7. [Performance Optimizations](#performance-optimizations)

---

## 🎯 OVERVIEW

This document describes the complete workflow for processing a user's route search query from initial UI input through final route generation and delivery.

### Key Principles:
- ✅ Single consolidated routing engine (Route Engine Only)
- ✅ RAPTOR Algorithm for multi-transfer route optimization
- ✅ Time-dependent graph architecture
- ✅ Multi-layer caching (Redis + In-Memory)
- ✅ Real-time validation throughout pipeline
- ✅ Performance targets: <5ms cache hits, <50ms P95 complex queries

---

## 🏗️ ARCHITECTURE LAYERS

```
┌─────────────────────────────────────────────────────────────────┐
│                      FRONTEND (React/TypeScript)                │
│                      (src/pages/Index.tsx)                      │
│              Search Form → Station Selection → Filters           │
└────────────────────────────┬────────────────────────────────────┘
                            │ HTTP POST
                            │ SearchRequestSchema
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API LAYER (FastAPI)                           │
│           backend/api/search.py → /api/search endpoint          │
│        Input Validation → Station Resolution → Query Building   │
└────────────────────────────┬────────────────────────────────────┘
                            │ Async Call
                            │ RouteConstraints
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              CACHING LAYER (Multi-Layer Cache)                   │
│      backend/services/multi_layer_cache.py                      │
│   Redis (Distributed) + In-Memory (Local) Cache Check           │
└────────────────────────────┬────────────────────────────────────┘
                            │ If Cache Miss
                            │ Build Route Graph
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│           CORE ROUTING ENGINE (OptimizedRAPTOR)                  │
│       backend/core/route_engine.py::OptimizedRAPTOR              │
│                                                                   │
│  ├─ TimeDependentGraph Construction                              │
│  ├─ RAPTOR Algorithm Execution (0-N rounds)                      │
│  ├─ Route Constraint Validation                                  │
│  ├─ Multi-objective Scoring                                      │
│  └─ Deduplication & Ranking                                      │
└────────────────────────────┬────────────────────────────────────┘
                            │
                            ├─ Call Validators
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│        VALIDATOR FRAMEWORK (8 Specialized Validators)           │
│         backend/core/validator/ (Orchestrated)                   │
│                                                                   │
│  ├─ RouteValidator (RT-001-020)                                  │
│  ├─ MultimodalValidator (RT-051-070)                            │
│  ├─ FareAvailabilityValidator (RT-071-090)                      │
│  ├─ APISecurityValidator (RT-111-130)                            │
│  ├─ DataIntegrityValidator (RT-131-150)                         │
│  ├─ AIRankingValidator (RT-151-170)                             │
│  ├─ ResilienceValidator (RT-171-200)                            │
│  └─ ProductionExcellenceValidator (RT-201-220)                  │
└────────────────────────────┬────────────────────────────────────┘
                            │ Validated Routes
                            │ Cache & Return
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RESPONSE LAYER                                │
│    Return ranked routes to frontend with scores & metadata      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 COMPLETE REQUEST FLOW

### PHASE 1: FRONTEND USER INTERACTION

```
User Browser (React Client)
│
├─ src/pages/Index.tsx::Index Component
│  ├─ State Management
│  │  ├─ origin: Station | null
│  │  ├─ destination: Station | null
│  │  ├─ travelDate: string (YYYY-MM-DD)
│  │  ├─ isSearching: boolean
│  │  ├─ filterTransfers: number | null
│  │  ├─ filterDeparture: "morning" | "afternoon" | "evening" | null
│  │  ├─ filterMaxDurationHours: number | null
│  │  └─ filterMaxCost: number | null
│  │
│  ├─ Component Hierarchy
│  │  ├─ Navbar (Navigation)
│  │  ├─ StationSearch (Origin Input)
│  │  │  └─ Calls: searchStationsApi() → /api/search/stations
│  │  ├─ StationSearch (Destination Input)
│  │  │  └─ Calls: searchStationsApi() → /api/search/stations
│  │  ├─ DatePicker (Travel Date)
│  │  ├─ CategoryFilter (Budget/Class/Amenities)
│  │  ├─ RouteCard (Display Results)
│  │  │  ├─ Fare Display
│  │  │  ├─ Duration Display
│  │  │  ├─ Comfort Score Display
│  │  │  └─ Book Button
│  │  └─ BookingFlowModal (Payment/Confirmation)
│  │
│  └─ Search Trigger (User clicks Search)
│     ├─ Validate inputs (origin, destination, date)
│     ├─ Create SearchRequestSchema
│     └─ Call: searchRoutesApi()

Search API Call (src/services/railwayBackApi.ts)
│
├─ POST /api/search
├─ Payload:
│  {
│    "source": "Delhi",
│    "destination": "Mumbai",
│    "date": "2026-02-20",
│    "budget": 5000,
│    "journey_type": "single",
│    "passenger_type": "adult",
│    "concessions": []
│  }
│
└─ Returns: routes: Route[]
   Where Route = {
     segments: RouteSegment[],
     transfers: TransferConnection[],
     total_duration: number,
     total_fare: number,
     score: number
   }
```

### PHASE 2: API LAYER (FASTAPI BACKEND)

```
FastAPI Application (backend/app.py)
│
├─ Initialization
│  ├─ Database setup: init_db()
│  ├─ Cache initialization: FastAPICache with Redis
│  ├─ Prometheus metrics: SEARCH_LATENCY_SECONDS
│  ├─ Rate limiting: 5 requests per minute per IP
│  └─ CORS setup for localhost:5173 (frontend dev)
│
└─ Request Processing (/api/search endpoint)

Route Handler: backend/api/search.py::search_routes_endpoint()
│
├─ STEP 1: INPUT VALIDATION (SearchRequestValidator)
│  ├─ source: str (required, non-empty)
│  ├─ destination: str (required, different from source)
│  ├─ date: str (required, ISO format, today or future)
│  ├─ budget: float (optional, positive)
│  ├─ journey_type: "single" | "connecting" | "circular" | "multi_city"
│  ├─ passenger_type: "adult" | "senior" | "child" | "pwd"
│  └─ concessions: List[str] (optional)
│
│  Validation Functions:
│  ├─ validate_date_string() → datetime | None
│  ├─ validate_station_pair() → bool
│  └─ SearchRequestValidator.validate() → bool
│
├─ STEP 2: STATION RESOLUTION
│  ├─ Call: resolve_stations(db, source_name, destination_name)
│  │  ├─ Fuzzy match against StationMaster table
│  │  ├─ Support partial names ("Delhi" → "New Delhi Railway Station")
│  │  ├─ Handle abbreviations ("NDLS" → "New Delhi")
│  │  └─ Return: (source_stop: Stop, dest_stop: Stop)
│  │
│  └─ Error Handling
│     ├─ If not found → HTTP 404 with suggestions
│     ├─ Log: "Station resolution failed"
│     └─ Return helpful error message
│
├─ STEP 3: CONSTRAINT BUILDING
│  ├─ Create RouteConstraints object
│  │  {
│  │    max_transfers: 3,
│  │    max_journey_time: 24 hours,
│  │    min_transfer_time: 15 minutes,
│  │    max_layover_time: 8 hours,
│  │    women_safety_priority: False,
│  │    avoid_night_layovers: False,
│  │    preferred_class: "SL" (Sleeper),
│  │    include_wait_time: True,
│  │    max_results: 10,
│  │    weights: {
│  │      time: 1.0,
│  │      cost: 0.3,
│  │      comfort: 0.2,
│  │      safety: 0.1
│  │    }
│  │  }
│  │
│  └─ Apply user filters
│     ├─ filterTransfers → max_transfers = N
│     ├─ filterDeparture → time window constraints
│     └─ filterMaxCost → exclude expensive routes
│
├─ STEP 4: CREATE CACHE QUERY
│  ├─ RouteQuery(
│  │   from_station='NDLS',
│  │   to_station='MMCT',
│  │   date=datetime(2026, 2, 20),
│  │   class_preference='SL',
│  │   max_transfers=3,
│  │   include_wait_time=True
│  │ )
│  │
│  └─ Generate cache key (Redis)
│     Key format: "routes:NDLS:MMCT:2026-02-20:SL:3"
│
├─ STEP 5: LOG REQUEST METADATA
│  ├─ request_id: timestamp-based unique identifier
│  ├─ source: source_stop.stop_id
│  ├─ destination: dest_stop.stop_id
│  └─ travel_date: datetime object
│
└─ STEP 6: DELEGATE TO ROUTE ENGINE
   └─ Proceed to PHASE 3
```

### PHASE 3: CACHING LAYER

```
Multi-Layer Cache (backend/services/multi_layer_cache.py)
│
├─ LAYER 1: REDIS DISTRIBUTED CACHE
│  ├─ Hostname: redis://localhost:6379 or env var
│  ├─ Database: 0 (default)
│  ├─ TTL: 3600 seconds (1 hour) for route queries
│  │
│  ├─ GET Operation
│  │  ├─ Key: "routes:FROM:TO:DATE:CLASS:TRANSFERS"
│  │  ├─ Value: Serialized route list (JSON)
│  │  ├─ Latency target: <50ms
│  │  ├─ Validation: validate_cache_hit_performance()
│  │  └─ Log: "Route cache hit" → return deserialized routes
│  │
│  └─ SET Operation (after computation)
│     ├─ Store computed routes
│     ├─ Set TTL to 3600 seconds
│     ├─ Format: {
│     │   routes: [
│     │     {
│     │       segments: [...],
│     │       transfers: [...],
│     │       total_duration: int,
│     │       total_distance: float,
│     │       total_fare: float,
│     │       score: float,
│     │       cached_at: ISO timestamp
│     │     }
│     │   ],
│     │   count: int
│     │ }
│     └─ Invalidate cache on disruptions/cancellations
│
├─ LAYER 2: IN-MEMORY CACHE
│  ├─ Data structure: Dict[str, CacheEntry]
│  ├─ Faster than Redis (no network latency)
│  ├─ Scope: Single Python process
│  │
│  ├─ Hit scenario
│  │  ├─ Latency: <5ms (very fast)
│  │  └─ Use case: Same user searches multiple times in quick succession
│  │
│  └─ Management
│     ├─ Eviction: LRU (Least Recently Used) after 100 entries
│     └─ TTL: 300 seconds (5 minutes)
│
├─ CACHE HIT FLOW
│  ├─ Time: cache_start ← current time
│  ├─ Query Redis key
│  ├─ Time: cache_end ← current time
│  ├─ Calculate: cache_elapsed_ms = (cache_end - cache_start) * 1000
│  │
│  ├─ Validation (PerformanceValidator.validate_cache_hit_performance)
│  │  ├─ Check: cache_elapsed_ms ≤ 50ms
│  │  ├─ Pass: Return cached routes immediately
│  │  │        Log: "RT-093: Cache hit latency OK"
│  │  │
│  │  └─ Fail: Log warning "RT-093: cache-hit latency exceeded"
│  │           (Still return routes, but mark as +log for monitoring)
│  │
│  └─ Deserialize Routes
│     ├─ Parse JSON to Route objects
│     ├─ Reconstruct RouteSegment[],
│     ├─ Reconstruct TransferConnection[]
│     ├─ Set scores and metadata
│     └─ Return to frontend (sub-50ms total)
│
└─ CACHE MISS FLOW
   ├─ Proceed to PHASE 4 (Route Computation)
   └─ After computation, populate cache
      ├─ Serialize routes to JSON
      ├─ Store in Redis with TTL
      ├─ Also populate in-memory cache
      └─ Return results to frontend
```

### PHASE 4: ROUTE ENGINE COMPUTATION (RAPTOR)

```
OptimizedRAPTOR::find_routes()
Entry Point: backend/core/route_engine.py::OptimizedRAPTOR.find_routes()
│
Inputs:
├─ source_stop_id: int (e.g., 1 for NDLS)
├─ dest_stop_id: int (e.g., 42 for MMCT)
├─ departure_date: datetime object
└─ constraints: RouteConstraints

Output:
└─ routes: List[Route] (sorted by score)

EXECUTION FLOW:
│
├─ STEP 1: CHECK CACHE (Already covered in PHASE 3)
│  └─ If hit → Return cached routes
│
├─ STEP 2: CALL _compute_routes() (Async)
│  │
│  └─ STEP 2A: BUILD TIME-DEPENDENT GRAPH
│     │
│     ├─ Time Measurement: graph_build_start ← time()
│     │
│     ├─ Execute: graph = await _build_graph(departure_date)
│     │  │
│     │  ├─ Use ThreadPoolExecutor for DB operations
│     │  │  └─ self.executor = ThreadPoolExecutor(max_workers=4)
│     │  │
│     │  ├─ Call: loop.run_in_executor()
│     │  │
│     │  └─ Synchronous Function: _build_graph_sync(date)
│     │     │
│     │     ├─ Create database session
│     │     │  └─ session = SessionLocal()
│     │     │
│     │     ├─ STEP 2A-i: GET ACTIVE SERVICE IDS
│     │     │  ├─ Query Calendar table for weekday
│     │     │  │  WHERE tuesday=True (for Tuesday travel)
│     │     │  │  AND   start_date ≤ 2026-02-20
│     │     │  │  AND   end_date ≥ 2026-02-20
│     │     │  │
│     │     │  ├─ Query CalendarDate exceptions
│     │     │  │  WHERE date=2026-02-20
│     │     │  │  AND   exception_type=1 (added services)
│     │     │  │
│     │     │  ├─ Query CalendarDate removals
│     │     │  │  WHERE date=2026-02-20
│     │     │  │  AND   exception_type=2 (removed services)
│     │     │  │
│     │     │  └─ Result: active_service_ids = {
│     │     │       service1_id, service2_id, service3_id, ...
│     │     │     }
│     │     │
│     │     ├─ STEP 2A-ii: QUERY STOP TIMES
│     │     │  ├─ Query StopTime table
│     │     │  │  JOIN Trip ON StopTime.trip_id = Trip.id
│     │     │  │  WHERE Trip.service_id IN (active_service_ids)
│     │     │  │  ORDER BY Trip.id, StopTime.stop_sequence
│     │     │  │
│     │     │  ├─ Join load relationships (optimization)
│     │     │  │  ├─ StopTime.trip (Trip object metadata)
│     │     │  │  └─ StopTime.stop (Stop object metadata)
│     │     │  │
│     │     │  └─ Result: stop_times = [
│     │     │       StopTime(trip_id=1, stop_id=1, seq=1, dept_time=08:00),
│     │     │       StopTime(trip_id=1, stop_id=5, seq=2, arr_time=09:30, dept_time=09:35),
│     │     │       ...
│     │     │     ]
│     │     │
│     │     ├─ STEP 2A-iii: GROUP BY TRIP
│     │     │  ├─ trip_groups: Dict[trip_id, List[StopTime]]
│     │     │  └─ Example:
│     │     │     {
│     │     │       1: [ST(stop=1, seq=1), ST(stop=5, seq=2), ST(stop=10, seq=3)],
│     │     │       2: [ST(stop=2, seq=1), ST(stop=6, seq=2)],
│     │     │       ...
│     │     │     }
│     │     │
│     │     ├─ STEP 2A-iv: CREATE ROUTE SEGMENTS
│     │     │  ├─ For each trip
│     │     │  │  ├─ For each pair of consecutive stops
│     │     │  │  │  ├─ current = stop_times[i]
│     │     │  │  │  ├─ next_stop = stop_times[i+1]
│     │     │  │  │  │
│     │     │  │  │  ├─ Convert times to datetime
│     │     │  │  │  │  ├─ dep_dt = _time_to_datetime(2026-02-20, 08:00:00)
│     │     │  │  │  │  │                           = datetime(2026, 2, 20, 8, 0)
│     │     │  │  │  │  │
│     │     │  │  │  │  └─ arr_dt = _time_to_datetime(2026-02-20, 09:30:00)
│     │     │  │  │  │                           = datetime(2026, 2, 20, 9, 30)
│     │     │  │  │  │
│     │     │  │  │  │ Handle overnight crossing:
│     │     │  │  │  │  while arr_dt < dep_dt:
│     │     │  │  │  │    arr_dt += timedelta(days=1)
│     │     │  │  │  │
│     │     │  │  │  ├─ Calculate duration
│     │     │  │  │  │  duration_minutes = (arr_dt - dep_dt).total_seconds() // 60
│     │     │  │  │  │                   = (9:30 - 8:00) = 90 minutes
│     │     │  │  │  │
│     │     │  │  │  └─ Create RouteSegment
│     │     │  │  │     RouteSegment(
│     │     │  │  │       trip_id=1,
│     │     │  │  │       departure_stop_id=1,
│     │     │  │  │       arrival_stop_id=5,
│     │     │  │  │       departure_time=2026-02-20 08:00,
│     │     │  │  │       arrival_time=2026-02-20 09:30,
│     │     │  │  │       duration_minutes=90,
│     │     │  │  │       distance_km=120.0,
│     │     │  │  │       fare=500.0,
│     │     │  │  │       train_name="Rajdhani Express",
│     │     │  │  │       train_number="12001"
│     │     │  │  │     )
│     │     │  │  │
│     │     │  │  ├─ Add to departures index
│     │     │  │  │  departures[1].append((2026-02-20 08:00, trip_id=1))
│     │     │  │  │
│     │     │  │  └─ Add to arrivals index
│     │     │  │     arrivals[5].append((2026-02-20 09:30, trip_id=1))
│     │     │  │
│     │     │  └─ Build segments dictionary
│     │     │     segments: Dict[trip_id, List[RouteSegment]]
│     │     │
│     │     ├─ STEP 2A-v: CREATE TRANSFER GRAPH
│     │     │  ├─ For each stop in the network
│     │     │  │  ├─ For each hour (0-23) and minute (0, 15, 30, 45)
│     │     │  │  │  ├─ Create potential transfer window
│     │     │  │  │  │  arr_time ← datetime(2026, 2, 20, hour, minute)
│     │     │  │  │  │  dep_time ← arr_time + timedelta(minutes=15)
│     │     │  │  │  │
│     │     │  │  │  └─ Create TransferConnection
│     │     │  │  │     TransferConnection(
│     │     │  │  │       station_id=5,
│     │     │  │  │       arrival_time=arr_time,
│     │     │  │  │       departure_time=dep_time,
│     │     │  │  │       duration_minutes=15,
│     │     │  │  │       station_name="Gwalior Junction",
│     │     │  │  │       facilities_score=0.7,
│     │     │  │  │       safety_score=0.8
│     │     │  │  │     )
│     │     │  │  │
│     │     │  │  └─ transfers[5].append(TransferConnection)
│     │     │  │
│     │     │  └─ Result: TimeDependentGraph with all connections
│     │     │
│     │     └─ Return graph_data dictionary
│     │        {
│     │          'departures': departures,
│     │          'arrivals': arrivals,
│     │          'segments': segments,
│     │          'transfers': transfers,
│     │          'stops': stops
│     │        }
│     │
│     ├─ Time Measurement: graph_build_ms = (time() - graph_build_start) * 1000
│     │
│     └─ Performance Validation
│        ├─ Check: graph_build_ms ≤ 1500ms
│        ├─ Pass: Log "RT-096: Graph built in Xms"
│        └─ Fail: Log warning "RT-096: graph rebuild time high"
│
│  └─ STEP 2B: INITIALIZE RAPTOR STRUCTURES
│     ├─ routes_by_round: Dict[round_num, List[Route]]
│     ├─ earliest_arrival: Dict[stop_id, datetime]
│     └─ best_routes: Dict[route_key, Route]
│
│  └─ STEP 2C: ROUND 0 - DIRECT CONNECTIONS
│     ├─ Get departures from source after target time
│     │  departures = graph.get_departures_from_stop(1, 2026-02-20 08:00)
│     │  Result: [(2026-02-20 08:00, trip_1), (2026-02-20 10:30, trip_2), ...]
│     │
│     ├─ Limit to first 50 departures (optimization)
│     │
│     └─ For each departure (dep_time, trip_id):
│        ├─ Get trip segments from graph
│        │  segments = graph.get_trip_segments(trip_id)
│        │
│        ├─ Find segment starting from source
│        │  for segment in segments:
│        │    if segment.departure_stop_id == source (1):
│        │      if segment.departure_time >= dep_time:
│        │        └─ FOUND starting segment
│        │
│        ├─ Create Route and add segment
│        │  route = Route()
│        │  route.add_segment(segment)  # segment: 1→5
│        │
│        ├─ Check if this segment reaches destination
│        │  if segment.arrival_stop_id == dest (42):
│        │    ├─ Validate route against constraints
│        │    │  _validate_route_constraints(route, constraints)
│        │    │  - Check: duration ≤ max_journey_time
│        │    │  - Check: transfers count ≤ max_transfers
│        │    │  - Check: transfer durations within limits
│        │    │  - Check: women safety if required
│        │    │
│        │    ├─ Calculate score
│        │    │  score = _calculate_score(route, constraints)
│        │    │  score = (
│        │    │    constraints.weights.time * duration_hours +
│        │    │    constraints.weights.cost * fare_amount / 1000 +
│        │    │    constraints.weights.comfort * (1 - comfort_score) +
│        │    │    constraints.weights.safety * (1 - safety_score)
│        │    │  )
│        │    │
│        │    ├─ Store/update best route
│        │    │  key = f"direct_{trip_id}"
│        │    │  best_routes[key] = route  (if score is better)
│        │    │
│        │    └─ Log: "Found direct route: 1→42"
│        │
│        └─ Else: Store in routes_by_round[0] for transfer processing
│           routes_by_round[0].append(route)  # e.g., 1→5 segment added for further transfers
│
│  └─ STEP 2D: RAPTOR TRANSFER ROUNDS (1 to max_transfers)
│     │
│     ├─ for round_num in range(1, max_transfers + 1):  # 1, 2, 3
│     │  │
│     │  ├─ Get routes from previous round
│     │  │  current_routes = routes_by_round[round_num - 1]
│     │  │  Example for round 1: routes that reached stop 5 but not destination
│     │  │
│     │  ├─ Process routes in parallel batches (async for performance)
│     │  │  batch_size = 10
│     │  │  for i in range(0, len(current_routes), batch_size):
│     │  │    batch = current_routes[i:i+batch_size]
│     │  │
│     │  │    transfer_routes = await asyncio.gather(*[
│     │  │      self._process_route_transfers(route, graph, dest, constraints)
│     │  │      for route in batch
│     │  │    ])
│     │  │
│     │  └─ For each route in batch: _process_route_transfers()
│     │     │
│     │     ├─ Get last segment
│     │     │  last_segment = route.segments[-1]
│     │     │  Example: last_segment.arrival_stop_id = 5
│     │     │           last_segment.arrival_time = 2026-02-20 09:30
│     │     │
│     │     ├─ Find feasible transfers from current arrival stop
│     │     │  transfers = graph.get_transfers_from_stop(
│     │     │    stop_id=5,
│     │     │    arrival_time=2026-02-20 09:30,
│     │     │    min_transfer_time=15
│     │     │  )
│     │     │
│     │     │  Inside get_transfers_from_stop():
│     │     │  ├─ for transfer in transfer_graph[5]:
│     │     │  │  ├─ Check: arrival_time ≤ actual_arrival ≤ departure_time
│     │     │  │  │         09:30 ≤ 09:30 ≤ 09:45 ✓
│     │     │  │  │
│     │     │  │  ├─ Calculate transfer  duration
│     │     │  │  │  duration_min = (departure_time - arrival_time) / 60
│     │     │  │  │                = (09:45 - 09:30) = 15 minutes
│     │     │  │  │
│     │     │  │  ├─ Check: min_transfer ≤ duration ≤ max_layover
│     │     │  │  │         15 ≤ 15 ≤ 480 ✓
│     │     │  │  │
│     │     │  │  └─ Add to feasible transfers
│     │     │  │     feasible.append(TransferConnection(...))
│     │     │  │
│     │     │  └─ Result: ~5-30 feasible transfers depending on transfers availability
│     │     │
│     │     └─ For each feasible transfer:
│     │        │
│     │        ├─ Validation
│     │        │  _is_feasible_transfer(transfer, constraints)
│     │        │  ├─ Duration within range? ✓
│     │        │  ├─ Avoid night layover? ✓ (if constraint set)
│     │        │  └─ Platform compatibility? (warning only)
│     │        │
│     │        ├─ Find onward connections from transfer point
│     │        │  onward_departures = graph.get_departures_from_stop(
│     │        │    stop_id=5,
│     │        │    after_time=2026-02-20 09:45  # transfer departure time
│     │        │  )
│     │        │  Result: [(09:45, trip_7), (10:15, trip_8), ...]
│     │        │
│     │        │  Limit to first 20 (optimization)
│     │        │
│     │        └─ For each onward departure (dep_time, trip_id):
│     │           │
│     │           ├─ Get trip segments
│     │           │  segments = graph.get_trip_segments(trip_id)
│     │           │
│     │           ├─ Find segment from transfer point
│     │           │  for segment in segments:
│     │           │    if segment.departure_stop_id == 5 and
│     │           │       segment.departure_time >= 09:45:
│     │           │      └─ FOUND onward segment (e.g., 5→10)
│     │           │
│     │           ├─ Cycle Prevention (Critical)
│     │           │  existing_stations = route.get_all_stations()
│     │           │                     = {1, 5}
│     │           │  if segment.arrival_stop_id (10) in existing_stations:
│     │           │    continue  # Skip to prevent loop
│     │           │
│     │           ├─ Create new route with transfer + segment
│     │           │  new_route = Route(
│     │           │    segments=[...old segments + segment(5→10)],
│     │           │    transfers=[...old transfers + transfer(5)],
│     │           │    total_distance=old + segment.distance,
│     │           │  )
│     │           │
│     │           ├─ Check if destination reached
│     │           │  if segment.arrival_stop_id == dest (42):
│     │           │    ├─ Validate full route
│     │           │    ├─ Calculate score
│     │           │    ├─ Add to new_routes
│     │           │    └─ Continue searching (for ranked results)
│     │           │
│     │           └─ Else: store for next round
│     │              if len(new_route.transfers) < max_transfers:
│     │                new_routes.append(new_route)
│     │
│     │
│     ├─ Extend routes_by_round[round_num] with new routes
│     │  routes_by_round[round_num].extend(route_list)
│     │
│     └─ Continue to next round (if routes exist)
│
│  └─ STEP 2E: COLLECT AND RANK RESULTS
│     │
│     ├─ Collect all valid routes from all rounds
│     │  all_routes = []
│     │  for key, route in best_routes.items():
│     │    if _validate_route_constraints(route, constraints):
│     │      all_routes.append(route)
│     │
│     ├─ Sort by score (ascending = better)
│     │  all_routes.sort(key=lambda r: r.score)
│     │
│     ├─ Limit results (typically top 10)
│     │  final_routes = all_routes[:constraints.max_results]
│     │
│     └─ Return to caller
│        return final_routes
│
├─ STEP 3: SERIALIZE FOR CACHE
│  ├─ Convert Route objects to dictionary format
│  ├─ Include segment data + transfers
│  ├─ Set cached_at timestamp
│  └─ Format for JSON serialization
│
├─ STEP 4: STORE IN CACHE
│  ├─ Call: multi_layer_cache.set_route_query(cache_query, serialized)
│  ├─ Key:  "routes:NDLS:MMCT:2026-02-20:SL:3"
│  ├─ Value: JSON with all route details
│  ├─ TTL: 3600 seconds
│  └─ Update both Redis + in-memory cache
│
└─ STEP 5: RETURN ROUTES
   └─ Return to API layer with List[Route]
```

---

## 📊 DETAILED COMPONENT PIPELINE

### Data Flow: From Input to Output

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1: INPUT (Frontend)                                  │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  SearchRequestSchema {                                       │
│    source: "Delhi",              ← Station name (fuzzy)     │
│    destination: "Mumbai",        ← Station name (fuzzy)     │
│    date: "2026-02-20",           ← ISO date format          │
│    budget: 5000,                 ← Optional budget (INR)    │
│    journey_type: "single",       ← single|connecting|...    │
│    passenger_type: "adult",      ← adult|senior|child|pwdpwd│
│    concessions: []               ← Applicable concessions   │
│  }                                                           │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                            ↓ HTTP POST /api/search
┌─────────────────────────────────────────────────────────────┐
│  LAYER 2: VALIDATION & NORMALIZATION                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  SearchRequestValidator.validate() {                         │
│    ├─ source_valid: True                                    │
│    ├─ destination_valid: True                               │
│    ├─ source ≠ destination: True                            │
│    ├─ date_valid: True (≥today)                            │
│    ├─ budget_valid: True (if provided)                      │
│    ├─ journey_type_valid: True                              │
│    ├─ passenger_type_valid: True                            │
│    └─ concessions_valid: True                               │
│  } → Returns boolean                                        │
│                                                               │
│  If invalid → HTTPException(400, detail=error_msg)          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 3: STATION RESOLUTION                                │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  resolve_stations(db, "Delhi", "Mumbai") {                  │
│                                                               │
│    DB Query (Fuzzy Match):                                  │
│    SELECT * FROM StationMaster                              │
│    WHERE name ILIKE '%Delhi%'                               │
│    ORDER BY name                                            │
│    LIMIT 10                                                 │
│                                                               │
│    Results:                                                  │
│    ├─ New Delhi Railway Station (NDLS) ← Best match         │
│    ├─ Delhi Cantt (DEC)                                    │
│    └─ East Delhi (ED)                                      │
│                                                               │
│    Scoring logic:                                            │
│    ├─ Exact match: NDLS (100%)                              │
│    ├─ Prefix match: "New Delhi" (95%)                       │
│    ├─ Contains: "Delhi Station" (80%)                       │
│    ├─ Abbreviation: "NDLS" for "Delhi" (70%)                │
│    └─ Levenshtein distance fallback                         │
│                                                               │
│    Selected: (Stop{id: 1, code: NDLS}, Stop{id: 42, ...})  │
│                                                               │
│  } → Returns (source_stop, dest_stop) tuple                │
│                                                               │
│  If not found → HTTPException(404)                          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 4: CONSTRAINT BUILDING                               │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  RouteConstraints {                                         │
│    max_transfers: 3                                         │
│    max_journey_time: 86400  (24 hours in seconds)          │
│    min_transfer_time: 15    (minutes)                       │
│    max_layover_time: 480    (8 hours in minutes)           │
│    women_safety_priority: False                             │
│    avoid_night_layovers: False                              │
│    preferred_class: "SL"    (Sleeper)                       │
│    include_wait_time: True                                  │
│    max_results: 10                                          │
│    Weights {                                                │
│      time: 1.0               (duration importance)          │
│      cost: 0.3               (fare importance)              │
│      comfort: 0.2            (comfort importance)           │
│      safety: 0.1             (safety importance)            │
│    }                                                         │
│  }                                                          │
│                                                               │
│  User filters applied:                                      │
│  ├─ filterTransfers: max_transfers = N                      │
│  ├─ filterDeparture: Add time window contraints             │
│  └─ filterMaxCost: Exclude expensive routes                 │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 5: CACHE QUERY BUILDING                              │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  RouteQuery {                                               │
│    from_station: "1"  (NDLS stop_id)                        │
│    to_station: "42"   (MMCT stop_id)                        │
│    date: 2026-02-20                                         │
│    class_preference: "SL"                                   │
│    max_transfers: 3                                         │
│    include_wait_time: True                                  │
│  }                                                          │
│                                                               │
│  Cache Key Generated:                                       │
│  "routes:1:42:2026-02-20:SL:3:True"                         │
│                                                               │
│  Cache Hit Check:                                           │
│  ├─ Query Redis with key                                   │
│  ├─ Measure latency (<50ms target)                          │
│  ├─ If exists: Deserialize and return                       │
│  └─ If not: Proceed to route computation                    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 6: ROUTE COMPUTATION (RAPTOR)                        │
├─────────────────────────────────────────────────────────────┤
│  (See detailed RAPTOR section below)                        │
│                                                               │
│  Outputs: List[Route] where Route contains                 │
│  ├─ segments: List[RouteSegment]                            │
│  ├─ transfers: List[TransferConnection]                     │
│  ├─ total_duration: int (minutes)                           │
│  ├─ total_distance: float (km)                              │
│  ├─ total_fare: float (INR)                                 │
│  └─ score: float (lower is better)                          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 7: VALIDATION (Multi-Check)                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  For each Route:                                            │
│  ├─ _validate_route_constraints()                           │
│  │  ├─ Check: total_duration ≤ max_journey_time            │
│  │  ├─ Check: transfers_count ≤ max_transfers              │
│  │  ├─ For each transfer:                                   │
│  │  │  ├─ Check: transfer_duration ≥ min_transfer_time     │
│  │  │  ├─ Check: transfer_duration ≤ max_layover_time      │
│  │  │  └─ Check: no night layover (if required)            │
│  │  ├─ Check: all stations are safe (if required)          │
│  │  └─ Return: boolean (pass/fail)                          │
│  │                                                           │
│  └─ Using ValidationManager (orchestrator)                  │
│     ├─ validateRoute validators (RT-001-020)               │
│     ├─ validate_multimodal_route (RT-051-070)               │
│     ├─ validate_fare_availability (RT-071-090)              │
│     ├─ validate_api_security (RT-111-130)                   │
│     └─ [other validators as needed]                         │
│                                                               │
│  Only routes passing validations are included in results    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 8: SCORING & RANKING                                 │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  For each valid Route:                                      │
│  ├─ score = calculate_score(route, constraints)            │
│  │                                                           │
│  │  score = (                                               │
│  │    weights.time * (duration_hours) +                    │
│  │    weights.cost * (fare / 1000) +                        │
│  │    weights.comfort * (1 - comfort_score) +              │
│  │    weights.safety * (1 - safety_score)                  │
│  │  )                                                        │
│  │                                                           │
│  │  Example calculation:                                    │
│  │  ├─ Duration: 12 hours × 1.0 = 12.0                     │
│  │  ├─ Fare: 2500 INR × 0.3 / 1000 = 0.75                  │
│  │  ├─ Comfort: (1 - 0.75) × 0.2 = 0.05                    │
│  │  ├─ Safety: (1 - 0.85) × 0.1 = 0.015                    │
│  │  └─ TOTAL SCORE: 12.815                                  │
│  │                                                           │
│  └─ route.score = final_score                              │
│                                                               │
│  Sort routes by score (ascending):                         │
│  ├─ Route 1: score=12.815 (Best)                           │
│  ├─ Route 2: score=13.200                                  │
│  ├─ Route 3: score=14.050                                  │
│  ├─ Route 4: score=15.300                                  │
│  └─ Route 5: score=16.750                                  │
│                                                               │
│  Take top N (typically 10):                                 │
│  ranked_routes = all_routes[:max_results]                   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 9: CACHE STORAGE                                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. Serialize routes to JSON                                │
│     {                                                        │
│       "routes": [                                            │
│         {                                                    │
│           "segments": [                                      │
│             {                                                │
│               "trip_id": 1,                                  │
│               "departure_stop_id": 1,                        │
│               "arrival_stop_id": 5,                          │
│               "departure_time": "2026-02-20T08:00:00",       │
│               "arrival_time": "2026-02-20T09:30:00",         │
│               "duration_minutes": 90,                        │
│               "distance_km": 120.0,                          │
│               "fare": 500,                                   │
│               "train_name": "Rajdhani Express",              │
│               "train_number": "12001"                        │
│             }                                                │
│           ],                                                 │
│           "transfers": [...],                               │
│           "total_duration": 720,                             │
│           "total_distance": 1500,                            │
│           "total_fare": 5000,                                │
│           "score": 12.815,                                   │
│           "cached_at": "2026-02-20T14:30:00"                 │
│         }                                                    │
│       ],                                                     │
│       "count": 5                                             │
│     }                                                        │
│                                                               │
│  2. Store in Redis                                          │
│     SETEX "routes:1:42:2026-02-20:SL:3:True"               │
│            3600  (1 hour TTL)                               │
│            {json_data}                                       │
│                                                               │
│  3. Update in-memory cache                                  │
│     in_memory_cache[key] = routes                           │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 10: RESPONSE BUILDING                                │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Response JSON {                                            │
│    "request_id": "1708421400.123456",                        │
│    "routes": [                                               │
│      {                                                       │
│        "segments": [                                         │
│          {                               │
│            "trip_id": 1,                                     │
│            "departure_stop_id": 1,                           │
│            "arrival_stop_id": 5,                             │
│            "departure_time": "2026-02-20T08:00:00",          │
│            ...                                               │
│          }                                                   │
│        ],                                                    │
│        "transfers": [                                        │
│          {                                                   │
│            "station_id": 5,                                  │
│            "arrival_time": "2026-02-20T09:30:00",            │
│            "departure_time": "2026-02-20T09:45:00",          │
│            "duration_minutes": 15,                           │
│            "station_name": "Gwalior Junction",               │
│            "facilities_score": 0.7,                          │
│            "safety_score": 0.8                               │
│          }                                                   │
│        ],                                                    │
│        "total_duration": 720,                                │
│        "total_distance": 1500,                               │
│        "total_fare": 5000,                                   │
│        "score": 12.815                                       │
│      }                                                       │
│    ],                                                        │
│    "disruption_alerts": [                                    │
│      {                                                       │
│        "type": "delay",                                      │
│        "description": "Route 12001 delayed by 30 minutes",   │
│        "severity": "high",                                   │
│        "affected_routes": "12001"                            │
│      }                                                       │
│    ],                                                        │
│    "source": "Delhi",                                        │
│    "destination": "Mumbai",                                  │
│    "travel_date": "2026-02-20",                              │
│    "total_options": 5,                                       │
│    "message": "Found 5 options"                              │
│  }                                                           │
│                                                               │
│  HTTP 200 Response                                          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 11: FRONTEND DISPLAY                                 │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Frontend receives JSON response                            │
│  ├─ Parse routes                                            │
│  ├─ Map to Route type                                       │
│  ├─ Render RouteCard components                             │
│  │  ├─ Departure & arrival times                            │
│  │  ├─ Duration                                             │
│  │  ├─ Fare (with payment options)                          │
│  │  ├─ Comfort score                                        │
│  │  ├─ Number of transfers                                  │
│  │  └─ Book button                                          │
│  │                                                           │
│  ├─ Apply user filters                                      │
│  │  ├─ filterTransfers: Hide routes with too many transfers │
│  │  ├─ filterDeparture: Show only morning/afternoon/evening │
│  │  ├─ filterMaxDurationHours: Hide longer routes           │
│  │  └─ filterMaxCost: Hide more expensive routes            │
│  │                                                           │
│  └─ Display sorted by selected sortBy                       │
│     ├─ "duration": Sort by total_duration                   │
│     ├─ "cost": Sort by total_fare                           │
│     └─ "score": Sort by composite score (default)           │
│                                                               │
│  User clicks "Book" on selected route                       │
│     → Proceed to booking flow                              │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔍 ROUTE GENERATION ALGORITHM (RAPTOR)

### Algorithm Overview

RAPTOR = **RA**pid **P**ublic **T**ransport **R**outer

**Key Concept**: Explore routes in rounds:
- **Round 0**: Direct connections (no transfers)
- **Round 1**: Routes with 1 transfer
- **Round 2**: Routes with 2 transfers
- **Round 3**: Routes with 3 transfers (max)

### Mathematical Model

```
Input:
  G = (V, E) where V = {stations}, E = {connections}
  t_dept = departure time from source
  max_k = maximum transfers
  w = {time, cost, comfort, safety} weights

Output:
  R = [r1, r2, ..., rn] (ranked routes to destination)

Algorithm:

1. INITIALIZE
   ├─ earliest_arrival[v] = ∞ for all v ∈ V
   ├─ earliest_arrival[source] = t_dept
   ├─ best_routes = {}
   └─ k = 0  // transfer count

2. FOR k = 0 TO max_k:

   2A. DIRECT CONNECTIONS (k=0)
       FOR each departure (t, trip_j) from source at time ≥ t_dept:
         FOR each stop v ∈ trip_j.stops:
           IF earliest_arrival[v] > arrival_time(v):
             earliest_arrival[v] = arrival_time(v)
             best_routes[v] = route_via_trip_j

   2B. TRANSFERS (k≥1)
       FOR each stop u that improved in round k-1:
         arr_time = earliest_arrival[u]
         FOR each transfer_connection t_ij where:
           arr_time ≤ t_ij.start_time ≤ t_ij.end_time:
           
           FOR each trip_j starting from stop u after t_ij.end_time:
             FOR each stop v ∈ trip_j.stops:
               new_arrival_time = arrival_time(v via trip_j)
               
               IF new_arrival_time < earliest_arrival[v]:
                 earliest_arrival[v] = new_arrival_time
                 best_routes[v] = extend(best_routes[u], trip_j)

3. RANKING
   ├─ FOR each route in best_routes:
   ├─   score = aggregate_score(route, weights)
   ├─   route.score = score
   └─ SORT routes by score (ascending)

4. RETURN
   TOP k routes where k = max_results
```

### Execution Example

```
Source: Station 1 (Delhi)
Destination: Station 42 (Mumbai)
Departure: 2026-02-20 08:00
Max Transfers: 3

ROUND 0: DIRECT CONNECTIONS
└─ Departures from Station 1 after 08:00:
   ├─ 08:00, Trip 100 (Rajdhani Express)
   │  └─ Segments: 1→5→10→15→20→...
   │     Best for: 1→5 (arr 09:30), 1→10 (arr 11:30), ...
   │
   ├─ 10:30, Trip 101
   │  └─ Segments: 1→3→8→12→...
   │
   └─ [no direct route to 42 found in round 0]
   
   Result: routes_by_round[0] = [
     Route(segments=[1→5], transfers=[]),
     Route(segments=[1→10], transfers=[]),
     ...
   ]

ROUND 1: ONE TRANSFER
└─ Last arrival points from Round 0: {5, 10, 15, ...}
   
   From Station 5 (arr 09:30):
   ├─ Feasible transfers at 05: dep 09:45, 10:00, 10:15, ...
   │
   ├─ After transfer at 09:45:
   │  ├─ Departures from 5 after 09:45:
   │  │  ├─ 09:45, Trip 200: 5→22→30→38→42 ✓ (reaches destination!)
   │  │  │  └─ new_route = Route(
   │  │  │      segments=[1→5, 5→22, 22→30, 30→38, 38→42],
   │  │  │      transfers=[{station:5, arr:09:30, dep:09:45}],
   │  │  │      arrival_time_at_dest = 20:30
   │  │  │    )
   │  │  │
   │  │  └─ Score = 1.0 * 12.5 + 0.3 * 2.5 + 0.2 * 0.25 + 0.1 * 0.15
   │  │           = 12.5 + 0.75 + 0.05 + 0.015 = 13.315
   │  │
   │  └─ 10:15, Trip 201: 5→25→35→42 ✓
   │     └─ new_route = Route(..., arrival = 18:45)
   │        └─ Score = 10.75 (better)
   │
   └─ Store best route to 42: score 10.75
   
   Also from Station 10, 15, ..., process similarly
   
   Result: routes_by_round[1] = [
     Route(..., score=10.75),  ← Better option found!
     Route(..., score=11.20),
     ...
   ]

ROUND 2: TWO TRANSFERS
└─ [Similar process with routes having 2 transfers]
   └─ May find suboptimal routes (longer detours)

ROUND 3: THREE TRANSFERS
└─ [Similar process with routes having 3 transfers]
   └─ Likely finds worst options (too many stops)

FINAL RANKING
└─ best_routes = {
     "direct_100": Route(score=24.50),  ← No direct available
     "transfer1_200": Route(score=10.75),
     "transfer1_201": Route(score=11.20),
     "transfer2_300": Route(score=12.30),
     ...
   }
   
   Sorted by score:
   ├─ Route 1: score=10.75 (1 transfer, 12.5h, 2500₹) ← BEST
   ├─ Route 2: score=11.20 (1 transfer, 13h, 2300₹)
   ├─ Route 3: score=12.30 (2 transfers, 11.5h, 2800₹)
   └─ Route 4: score=13.50 (2 transfers, 13h, 3000₹)
   
   RETURN: [Route1, Route2, Route3, Route4] (top 10, here 4 found)
```

---

## ✅ VALIDATION & QUALITY CHECKS

### Validation Framework (8 Validators)

```
ValidationManager (Orchestrator)
│
├─ RouteValidator (RT-001-020)
│  ├─ validate_route_constraints()
│  │  ├─ Max journey time ≤ 24h
│  │  ├─ Transfers ≤ max_transfers
│  │  ├─ Transfer durations valid
│  │  └─ No night layovers
│  │
│  ├─ validate_transfer_time()
│  │  ├─ min_transfer_time ≤ actual ≤ max_layover_time
│  │  └─ Platform compatibility checks
│  │
│  └─ validate_segment_continuity()
│     └─ Prev arrival == next departure
│
├─ MultimodalValidator (RT-051-070)
│  ├─ validate_mode_transitions()
│  │  └─ Valid rail→bus, rail→metro transfers
│  │
│  └─ validate_modal_distribution()
│     └─ Ensure balanced use of transport modes
│
├─ FareAvailabilityValidator (RT-071-090)
│  ├─ validate_seat_availability()
│  │  └─ Check: available_seats > 0 in each segment
│  │
│  ├─ validate_fare_calculation()
│  │  └─ Fare = distance_based + surge + concession
│  │
│  └─ validate_concession_eligibility()
│     └─ Passenger_type matches concession_type
│
├─ APISecurityValidator (RT-111-130)
│  ├─ validate_auth_token()
│  │  └─ Token valid and not expired
│  │
│  ├─ validate_rate_limit()
│  │  └─ Request rate < 5/minute
│  │
│  └─ validate_payload_schema()
│     └─ Request matches SearchRequestSchema
│
├─ DataIntegrityValidator (RT-131-150)
│  ├─ validate_graph_consistency()
│  │  └─ All references resolve (stop IDs, trip IDs)
│  │
│  ├─ validate_no_circular_routes()
│  │  └─ No route revisits same station
│  │
│  └─ validate_temporal_ordering()
│     └─ departure < arrival for each segment
│
├─ AIRankingValidator (RT-151-170)
│  ├─ validate_score_calculation()
│  │  └─ Score = f(time, cost, comfort, safety)
│  │
│  └─ validate_personalization_weights()
│     └─ Weights sum to ~1.0
│
├─ ResilienceValidator (RT-171-200)
│  ├─ validate_handles_disruptions()
│  │  └─ Routes exclude cancelled legs
│  │
│  └─ validate_alternative_paths_exist()
│     └─ Min 2-3 alternative routes available
│
└─ ProductionExcellenceValidator (RT-201-220)
   ├─ validate_performance_targets()
   │  └─ Cache hits <50ms, computations <5s
   │
   └─ validate_monitoring_coverage()
      └─ All metrics instrumented
```

### Validation Flow in Find_Routes

```
After computing routes:

FOR each route in computed_routes:
  
  1. Constraint Validation
     └─ _validate_route_constraints(route, constraints)
        ├─ IF duration > max: SKIP route
        ├─ IF transfers > max: SKIP route
        └─ Return: boolean (valid/invalid)
  
  2. Transfer Feasibility
     └─ _is_feasible_transfer(transfer, constraints)
        ├─ Duration ∈ [min_transfer, max_layover_time]
        └─ Return: boolean
  
  3. Segment Continuity
     └─ _validate_segment_continuity(segments)
        └─ Previous arrival ≤ next departure
           Return: boolean
  
  4. ValidationManager Checks
     └─ validation_manager.validate(route)
        ├─ Run category-specific validators
        │  ├─ RouteValidator checks
        │  ├─ FareAvailabilityValidator checks
        │  └─ [others as configured]
        │
        └─ Return: ValidationReport {
             all_passed: bool,
             failed_checks: List[str],
             warnings: List[str]
           }
  
  5. Decision
     ├─ IF all_passed: Include in results ✓
     └─ ELSE: Exclude from results ✗

Collect valid_routes
Sort by score
Return top N
```

---

## ⚡ PERFORMANCE OPTIMIZATIONS

### Caching Strategy

```
MULTI-TIER CACHE ARCHITECTURE

Tier 1: In-Memory Cache (Python Dict)
├─ Latency: ~1-5ms
├─ Scope: Single process
├─ TTL: 5 minutes
├─ Eviction: LRU when size > 100
└─ Use case: Same user, quick repeat searches

Tier 2: Redis Distributed Cache
├─ Latency: ~10-50ms
├─ Scope: Entire application cluster
├─ TTL: 60 minutes
├─ Capacity: Depends on Redis config (typically 10GB+)
└─ Use case: Multiple users, same origin-destination pairs

Cache Key Structure:
"routes:<from_id>:<to_id>:<date>:<class>:<max_transfers>:<include_wait>"
Example:
"routes:1:42:2026-02-20:SL:3:True"

Cache Value:
{
  "routes": [
    {
      "segments": [...],
      "transfers": [...],
      "total_duration": 720,
      "score": 12.815,
      "cached_at": "2026-02-20T14:30:00"
    }
  ],
  "count": 5
}

Cache Hit Rate Targets:
├─ Peak hours: 60-70% hit rate
├─ Off-peak: 40-50% hit rate
└─ Overall: 55%+ (depends on travel date variety)
```

### Graph Building Optimization

```
Parallel Execution:
├─ ThreadPoolExecutor with 4 workers
├─ Each worker handles DB query + processing
└─ Result: ~3-4x faster than sequential

Database Query Optimization:
├─ Use joinedload() for eager loading
├─ Fetch StopTime + Trip + Stop in single query
├─ Avoid N+1 query problems
└─ Typical: 5000 stop times in <500ms

In-Memory Graph:
├─ Departures index: Dict[stop_id, List[(time, trip_id)]]
├─ Arrivals index: Dict[stop_id, List[(time, trip_id)]]
├─ Segments cache: Dict[trip_id, List[RouteSegment]]
└─ Transfer graph: Dict[stop_id, List[TransferConnection]]

Memory Usage:
├─ Typical network (5000 stops, 1000 daily trips)
├─ Graph size: ~50-100 MB
└─ Cost: ~10ms to build + cache in memory
```

### Algorithm Optimizations (RAPTOR)

```
1. LIMITING EXPLORATION
   ├─ First 50 departures from source (vs all)
   ├─ First 20 onward connections per transfer (vs all)
   ├─ First 10 batches of 10 routes in parallel (vs sequential)
   └─ Result: ~10-50x speedup without quality loss

2. CYCLE PREVENTION
   ├─ Track visited stations per route
   ├─ Skip if next arrival is already visited
   ├─ Zero cycles without complex detection
   └─ Cost: O(n) per route where n = station count

3. DEDUPLICATION
   ├─ Routes with same (stations, transfers) → keep best score
   ├─ Run after all rounds
   └─ Result: Reduce redundant routes 20-50%

4. EARLY TERMINATION
   ├─ If destination reached in round k
   ├─ Still explore round k+1 (for alternatives)
   ├─ Stop at round=max_transfers
   └─ Typical: 80% of routes found in round 1-2

5. ASYNC BATCH PROCESSING
   ├─ asyncio.gather() for parallel processing
   ├─ Process 10 routes concurrently
   └─ Result: 5-8x faster than sequential
```

### Performance Metrics

```
TARGET METRICS:

Cache Hits:
├─ Latency: <50ms (RT-093 validator)
├─ Expected: 55-70% hit rate in normal operations
└─ Log: Every cache operation

Graph Building:
├─ Latency: <1500ms (RT-096 validator)
├─ Expected: 300-800ms for typical network
└─ Executed once per unknown (from, to, date) pair

Route Computation:
├─ Latency: <5000ms P95
├─ Expected: 200-1000ms for typical queries
├─ Breakdown:
│  ├─ Graph build: 300-500ms
│  ├─ RAPTOR execution: 100-400ms
│  ├─ Validation: 50-200ms
│  └─ Serialization: 10-50ms
└─ Parallelization: 4x workers, 10 batch size

End-to-End Search:
├─ Latency target: <100ms for cached, <5s for computed
├─ P50: 50-100ms (cache hits typical)
├─ P95: 1-3s (cache misses on peak)
└─ P99: 4-8s (complex multi-transfer searches)

Throughput:
├─ Single instance: 10,000+ req/sec (cached)
├─ Single instance: 100-200 req/sec (computed)
└─ Cluster (10 instances): 50,000+ req/sec sustained
```

---

## 🏁 SUMMARY: COMPLETE WORKFLOW

```
USER INPUT
    ↓
[FRONTEND VALIDATION]
    ↓
[API INPUT VALIDATION]
    ↓
[STATION RESOLUTION]
    ↓
[CONSTRAINT BUILDING]
    ↓
[CACHE QUERY BUILD]
    ↓
[CACHE CHECK]
    ├─ HIT (50-70%) → DESERIALIZE → VALIDATE → RETURN (50ms)
    │
    └─ MISS → [GRAPH BUILDING] (500ms)
              ↓
            [RAPTOR ALGORITHM]
            ├─ Round 0: Direct routes
            ├─ Round 1: 1-transfer routes
            ├─ Round 2: 2-transfer routes
            └─ Round 3: 3-transfer routes
              ↓
            [VALIDATION]
              ├─ 8-validator checks
              └─ Remove invalid routes
              ↓
            [SCORING & RANKING]
              ├─ Calculate composite score
              ├─ Sort by score
              └─ Take top 10
              ↓
            [CACHE STORAGE]
              ├─ Redis SETEX
              └─ In-memory cache
              ↓
            [RETURN] (1-5s total)
              ↓
    [RESPONSE TO FRONTEND]
    ├─ routes: List[Route]
    ├─ metadata: request_id, total_count
    └─ disruptions: List[Alert]
              ↓
    [FRONTEND DISPLAYS RESULTS]
    ├─ Route cards with details
    ├─ Filtering & sorting
    └─ Booking flow on selection
```

---

## 📚 APPENDIX: KEY FILES & LOCATIONS

### Backend Core
- **Route Engine**: `backend/core/route_engine.py`
  - `OptimizedRAPTOR` class
  - `TimeDependentGraph` class
  - Data models: `Route`, `RouteSegment`, `TransferConnection`

- **Validators**: `backend/core/validator/`
  - `validation_manager.py` (orchestrator)
  - `route_validators.py`
  - `multimodal_validators.py`
  - `fare_availability_validators.py`
  - `api_security_validators.py`
  - `data_integrity_validators.py`
  - `ai_ranking_validators.py`
  - `resilience_validators.py`
  - `production_validators.py`

### API Layer
- **Search Endpoint**: `backend/api/search.py`
  - `search_routes_endpoint()` handler
  - Input validation
  - Station resolution
  - Constraint building

- **Admin**: `backend/api/admin.py`
  - Graph reload endpoint
  - Performance checks

### Services
- **Caching**: `backend/services/multi_layer_cache.py`
  - Redis integration
  - In-memory cache
  - Cache hit/miss handling

- **Station Utils**: `backend/utils/station_utils.py`
  - Station resolution with fuzzy matching

- **Validation Utils**: `backend/utils/validation.py`
  - SearchRequestValidator
  - Date validation

### Frontend
- **Search Page**: `src/pages/Index.tsx`
  - `useSearchParams()` for URL state
  - Station selection
  - Result display

- **API Calls**: `src/services/railwayBackApi.ts`
  - `searchRoutesApi()` POST call
  - Response mapping

### Database
- **Models**: `backend/database/models.py`
  - `Trip`, `Stop`, `StopTime`, `Transfer`
  - `Calendar`, `CalendarDate`

- **Schemas**: `backend/schemas.py`
  - `SearchRequestSchema`
  - `RouteSchema`

---

**End of Document**  
Version: 1.0 (Consolidated - Route Engine Only)  
Last Updated: February 2026
