# COMPLETE ROUTEMASTER WORKFLOW PIPELINE
## End-to-End Journey Query Processing & Route Generation

---

## OVERVIEW
```
USER QUERY FLOW:
Browser (Frontend) → API Endpoint → Validation → Database Load →
Route Calculation Engine → Journey Reconstruction → Verification →
Seat Allocation → Response Generation → Browser (Frontend)
```

---

# 1. FRONTEND - USER INITIATION LAYER
## Location: `/src`

### 1.1 USER INTERFACE COMPONENTS
```
📱 src/pages/Index.tsx (Main Search Page) [948 lines]
   ├── State Management:
   │   ├── origin: Station | null                    (Source station)
   │   ├── destination: Station | null               (Destination station)
   │   ├── travelDate: string                        (YYYY-MM-DD format)
   │   ├── optimalRoutes: Route[]                    (Best routes)
   │   ├── allRoutes: Route[]                        (All alternatives)
   │   ├── sortPreset: "duration" | "cost"           (Sorting preference)
   │   ├── filterTransfers: number | null            (Max transfers)
   │   ├── filterDeparture: time | null              (Preferred time)
   │   └── journeyMessage: string | null             (UI feedback)
   │
   ├── Core UI Elements:
   │   ├── 📍 StationSearch Component (src/components/StationSearch.tsx)
   │   │   └── Handles: Fuzzy matching, Autocomplete, Station suggestions
   │   │
   │   ├── 📅 CalendarDays Component (lucide-react)
   │   │   └── Travel date selection
   │   │
   │   ├── 🔍 Search Button
   │   │   └── Triggers search workflow
   │   │
   │   └── 📊 RouteCard Component (src/components/RouteCard.tsx)
   │       └── Displays: Train name, departure/arrival times, fare, duration
   │
   └── Event Listeners:
       ├── rail-assistant-search (Custom event from chatbot)
       ├── rail-assistant-sort (Sort order change)
       └── route-unlock-payment (Route unlocking)

📱 src/components/StationSearch.tsx
   ├── searchStationsLocal() → Queries local station cache
   │   └── src/data/stations.ts (Preloaded station data)
   │
   └── searchStationsApi() → API call to backend for fuzzy matching
       └── POST /api/stations/fuzzy_search
           └── Response: Station[] with IDs and metadata

📱 src/components/RouteCard.tsx
   ├── Displays journey details
   ├── Shows availability indicators
   ├── Unlock button (for premium routes)
   └── OnClick → BookingFlowModal (src/components/booking/)

📱 src/components/booking/BookingFlowModal.tsx [FULL FLOW]
   └── Multi-step booking process
```

### 1.2 SEARCH INITIATION LOGIC
```javascript
// File: src/pages/Index.tsx (lines 200-300)

async function handleSearch() {
    setIsSearching(true);
    setSearchError(null);
    
    try {
        1️⃣ VALIDATE INPUT
        └── origin && destination && travelDate must exist
        
        2️⃣ CALL SEARCH API
        └── searchRoutesApi({
                source: origin.name,
                destination: destination.name,
                date: travelDate,
                budget: selectedBudget,
                journey_type: "single"
            })
        
        3️⃣ PROCESS RESPONSE
        ├── Map backend routes to frontend format
        ├── Apply local filters (transfers, departure time)
        ├── Sort by selected preset (duration/cost)
        └── Update state (optimalRoutes, allRoutes)
        
        4️⃣ RENDER RESULTS
        └── Display RouteCard components
    }
}
```

**Files Involved:**
- `src/pages/Index.tsx` - Main search page
- `src/components/StationSearch.tsx` - Station selection
- `src/services/railwayBackApi.ts` - API communication

---

# 2. API GATEWAY LAYER
## Location: `/backend/api`

### 2.1 API ROUTING & ENDPOINT REGISTRATION
```
📨 File: backend/app.py [215 lines]
   ├── FastAPI Application Initialization
   │   ├── app = FastAPI(
   │   │       title="RouteMaster API",
   │   │       version="1.0.0"
   │   │   )
   │   │
   │   ├── MIDDLEWARE STACK:
   │   │   ├── CORSMiddleware (Allow frontend localhost:5173)
   │   │   ├── Rate Limiter (slowapi) - 5 requests/minute
   │   │   └── Prometheus Instrumentator (/metrics endpoint)
   │   │
   │   ├── DATABASE INITIALIZATION
   │   │   ├── SessionLocal configuration
   │   │   ├── engine_write (Primary write DB)
   │   │   └── engine_read (Read replica, optional)
   │   │
   │   └── ROUTER MOUNTING:
   │       ├── app.include_router(search.router)             → POST /api/search/
   │       ├── app.include_router(routes.router)             → GET /api/routes/
   │       ├── app.include_router(payments.router)           → POST /api/payments/
   │       ├── app.include_router(users.router)              → GET/POST /api/users/
   │       ├── app.include_router(booking_router)            → POST /api/bookings/
   │       ├── app.include_router(integrated_search.router)  → POST /api/v2/search/unified
   │       ├── app.include_router(websockets.router)         → WS /ws/
   │       └── ... (15 more routers)
   │
   ├── STARTUP EVENT
   │   ├── @app.on_event("startup")
   │   ├── async def startup():
   │   │   ├── await init_db()              → Create tables
   │   │   ├── multi_modal_route_engine.load_graph_from_db(db)
   │   │   ├── start_reconciliation_worker() → Background worker
   │   │   └── logger.info("RouteMaster API Started")
   │   │
   │   └── SHUTDOWN EVENT
   │       └── Cleanup resources
   │
   └── CACHE INITIALIZATION
       └── FastAPICache backend with Redis
```

### 2.2 SEARCH ENDPOINT
```
POST /api/search/
├── File: backend/api/search.py [362 lines]
├── Status: ACTIVE - New comprehensive flow
│
├── ROUTE HANDLER: search_routes_endpoint()
│   ├── Decorators:
│   │   ├── @router.post("/")
   │   └── @limiter.limit("5/minute")         → Rate limiting
   │
   ├── PARAMETERS & VALIDATION
   │   ├── request: Request                   (FastAPI Request object)
   │   ├── search_request: SearchRequestSchema (from body - see 2.4)
   │   └── db: Session (Dependency injection - see 2.5)
   │
   └── EXECUTION FLOW (VERY IMPORTANT):
       │
       │ 1️⃣ INPUT VALIDATION
       ├─────────────────────
       │ validator = SearchRequestValidator()
       │ ├─ Validates source/destination non-empty
       │ ├─ Validates date is YYYY-MM-DD format
       │ ├─ Validates date is not in past
       │ ├─ Validates budget in ['all', 'economy', 'standard', 'premium']
       │ ├─ Validates journey_type in ['single', 'connecting', 'circular', 'multi_city']
       │ └─ Returns error if validation fails
       │    └─ raise HTTPException(400, detail=validator.get_error_message())
       │
       │ 2️⃣ LOAD ROUTE ENGINE
       ├─────────────────────
       │ if not multi_modal_route_engine._is_loaded:
       │ └─ multi_modal_route_engine.load_graph_from_db(db)
       │    └─ Load all GTFS data into memory (see 3.1)
       │
       │ 3️⃣ PARSE TRAVEL DATE
       ├─────────────────────
       │ travel_date = validate_date_string(search_request.date, allow_past=False)
       │ └─ Convert string to datetime object
       │    └─ Validate date >= today
       │
       │ 4️⃣ RESOLVE STATIONS
       ├─────────────────────
       │ source_stop, dest_stop = resolve_stations(
       │ │   db,
       │ │   search_request.source,        e.g., "Mumbai Central"
       │ │   search_request.destination    e.g., "New Delhi"
       │ )
       │ │
       │ ├─ Function: src/utils/station_utils.py:resolve_stations()
       │ ├─ Uses fuzzy matching to find closest station names
       │ ├─ Query database:
       │ │  └─ SELECT * FROM stops WHERE name ~* search_term
       │ │     (PostgreSQL trigram search with gin_trgm_ops index)
       │ │
       │ └─ Returns Stop objects with:
       │     ├─ id (internal ID)
       │     ├─ stop_id (public-facing ID)
       │     ├─ name (station name)
       │     ├─ city (city name)
       │     ├─ latitude/longitude (geolocation)
       │     ├─ safety_score (0-100)
       │     └─ facilities_json (wifi, lounge, food, etc.)
       │
       │ 5️⃣ DETERMINE JOURNEY TYPE
       ├─────────────────────
       │ ├─ If journey_type == "single":
       │ │   └─ Single source to single destination
       │ │
       │ ├─ If journey_type == "connecting":
       │ │   ├─ Search multiple intermediate stops
       │ │   └─ Find connecting journeys
       │ │
       │ ├─ If journey_type == "circular":
       │ │   ├─ Return date specified
       │ │   └─ Generate round-trip routes
       │ │
       │ └─ If journey_type == "multi_city":
       │     ├─ Multiple destinations in sequence
       │     └─ Generate multi-city routes
       │
       │ 6️⃣ CALL MULTIMODAL ROUTE ENGINE ⭐ (CORE ALGORITHM)
       ├─────────────────────
       │ routes = multi_modal_route_engine.search_single_journey(
       │ │   source_id=source_stop.id,
       │ │   dest_id=dest_stop.id,
       │ │   start_datetime=travel_date,
       │ │   max_transfers=3,
       │ │   budget_mode=search_request.budget
       │ )
       │ │
       │ ├─ See Section 4: ROUTE CALCULATION ENGINE
       │ └─ Returns: List[JourneyOption] with all possible routes
       │
       │ 7️⃣ APPLY FRONTEND FILTERS
       ├─────────────────────
       │ ├─ Filter by budget (if specified)
       │ ├─ Filter by max transfers
       │ ├─ Filter by departure time window
       │ └─ Sort by duration/cost
       │
       │ 8️⃣ CACHE RESULTS
       ├─────────────────────
       │ cache_route_search(
       │ │   query=RouteQuery(source, dest, date),
       │ │   routes=routes,
       │ │   ttl=3600  # 1 hour cache
       │ )
       │ │
       │ └─ Redis key: f"{source_id}:{dest_id}:{date.date()}:{budget}"
       │
       │ 9️⃣ RETURN RESPONSE
       ├─────────────────────
       │ return {
       │ │   "request_id": request_id,
       │ │   "routes": [
       │ │       {
       │ │           "id": route.journey_id,
       │ │           "segments": [{...}],              # Each train segment
       │ │           "total_duration_minutes": 480,
       │ │           "total_distance_km": 1440,
       │ │           "num_transfers": 2,
       │ │           "cheapest_fare": 1500.0,
       │ │           "premium_fare": 3500.0,
       │ │           "is_direct": false,
       │ │           "availability_status": "available"
       │ │       }
       │ │   ],
       │ │   "total_results": 15,
       │ │   "sorted_by": "duration",
       │ │   "query_time_ms": 245
       │ }
       │
       └─ MEASUREMENTS:
           ├─ SEARCH_LATENCY_SECONDS (Prometheus metric)
           ├─ SEARCH_REQUESTS_TOTAL (counter)
           └─ ROUTE_LATENCY_MS (histogram)
```

### 2.3 INTEGRATED SEARCH ENDPOINT (V2 - NEW UNIFIED)
```
POST /api/v2/search/unified
├── File: backend/api/integrated_search.py [528 lines]
├── Purpose: Complete IRCTC-like offline flow
│
├── REQUEST SCHEMA: SearchRequest
│   ├── source: str                          (Station name, fuzzy matched)
│   ├── destination: str                     (Station name, fuzzy matched)
│   ├── travel_date: str                     (YYYY-MM-DD)
│   ├── return_date: Optional[str]           (For round trips)
│   ├── num_passengers: int                  (1-6)
│   ├── passengers: List[PassengerInfo]
│   │   ├── full_name: str
│   │   ├── age: int
│   │   ├── gender: str (M/F/O)
│   │   ├── concession_type: Optional[str]
│   │   └── phone: Optional[str]
│   ├── coach_preference: str                (AC_THREE_TIER, SLEEPER, etc.)
│   └── is_tatkal: bool                      (Tatkal booking flag)
│
└── RESPONSE SCHEMA: List[JourneyInfoResponse]
    └── [
        {
            "journey_id": "JNY-001",
            "num_segments": 2,
            "distance_km": 1440.0,
            "travel_time": "24:30",
            "num_transfers": 1,
            "is_direct": false,
            "cheapest_fare": 1500.0,
            "premium_fare": 3500.0,
            "has_overnight": true,
            "availability_status": "available"
        }, ...
    ]
```

### 2.4 REQUEST & RESPONSE SCHEMAS
```
📋 File: backend/schemas.py [282 lines]

SEARCH REQUEST SCHEMA:
┌─────────────────────────────────────┐
│ SearchRequestSchema (Pydantic Model)│
├─────────────────────────────────────┤
│ source: str                         │
│ destination: str                    │
│ date: str (YYYY-MM-DD)              │
│ budget: str = "all"                 │
│ multi_modal: bool = True            │
│ journey_type: Optional[str]         │
│ return_date: Optional[str]          │
│ passenger_type: str = "adult"       │
│ concessions: Optional[List[str]]    │
└─────────────────────────────────────┘
   │
   └─ Validation:
      ├── @validator('source')
      │   └── min_length=2, max_length=100
      ├── @validator('date')
      │   └── Pattern: ^\d{4}-\d{2}-\d{2}$
      └── @validator('budget')
          └── Pattern: ^(all|economy|standard|premium)$

RESPONSE SCHEMA (from Route objects):
┌──────────────────────────────────┐
│ RouteSchema (Pydantic Response)  │
├──────────────────────────────────┤
│ id: str                          │
│ segments: List[SegmentSchema]    │
│ total_duration_minutes: int      │
│ total_distance_km: float         │
│ num_transfers: int               │
│ cheapest_fare: float             │
│ premium_fare: float              │
│ availability_status: str         │
└──────────────────────────────────┘
```

### 2.5 DEPENDENCY INJECTION
```
📨 File: backend/api/dependencies.py

async def get_db(request: Request = None) -> Session:
    """
    Dependency that provides database session.
    Routes read-only requests to read replica if available.
    """
    db = SessionLocal()
    
    # Check if GET request → use read replica
    if request and request.method == "GET" and engine_read:
        db._read_only = True  # Routes to read replica
    else:
        db._read_only = False # Routes to primary write DB
    
    try:
        yield db  # Inject into endpoint
    finally:
        db.close()  # Cleanup

        ┌─ Used in search_routes_endpoint():
        └─ async def search_routes_endpoint(
               search_request: SearchRequestSchema,
               db: Session = Depends(get_db)  ← Dependency injection
           ):
```

---

# 3. DATABASE ACCESS LAYER
## Location: `/backend/database`

### 3.1 DATABASE CONNECTION & SESSION MANAGEMENT
```
📦 File: backend/database/session.py [100+ lines]

DATABASE ARCHITECTURE:
┌─────────────────────────────────────────┐
│     RoutingSession (Custom SQLAlchemy)  │
└─────────────────────────────────────────┘
           ↓
    get_bind() method
           ↓
    ┌─────────┴──────────┐
    ↓                    ↓
engine_write          engine_read
(Primary DB)        (Read Replica)
    ↓                    ↓
PostgreSQL ←──────→ PostgreSQL
(Write)            (Read-only)

CONFIGURATION:
├─ PRIMARY ENGINE (engine_write):
│  ├─ Connection Pool: QueuePool
│  ├─ Pool Size: 10 connections
│  ├─ Max Overflow: 20
│  ├─ pool_pre_ping: True (validate connections)
│  └─ URL: DATABASE_URL from config
│
└─ READ REPLICA (engine_read - optional):
   ├─ Connection Pool: QueuePool
   ├─ Pool Size: 10 connections
   └─ URL: READ_DATABASE_URL from config (if set)

ROUTING LOGIC:
if request.method == "GET" and engine_read exists:
    └─ Route to engine_read (Read Replica)
else:
    └─ Route to engine_write (Primary DB)

SESSION FACTORY:
SessionLocal = sessionmaker(
    class_=RoutingSession,
    autocommit=False,
    autoflush=False,
    bind=engine_write
)
```

### 3.2 DATABASE MODELS
```
📋 File: backend/database/models.py [718 lines]

SCHEMA OVERVIEW:

┌──────────────────────────────────────────────────────────────┐
│         GTFS-INSPIRED TRANSIT DATA MODELS                    │
└──────────────────────────────────────────────────────────────┘

1️⃣ AGENCY TABLE
   ├─ id: Integer (Primary Key)
   ├─ agency_id: String (Unique, Index)     e.g., "INDIAN_RAILWAYS"
   ├─ name: String                          e.g., "Indian Railways"
   ├─ url: String
   ├─ timezone: String                      e.g., "Asia/Kolkata"
   └─ language: String (Optional)
   
   Relationships:
   └─ routes (one-to-many to Route)

2️⃣ STOPS TABLE ⭐ (Core)
   ├─ id: Integer (Primary Key, Internal)
   ├─ stop_id: String (Unique, Public-facing ID)
   ├─ code: String (Index)                  e.g., Platform code
   ├─ name: String (Indexed, Trigram)       e.g., "Mumbai Central"
   ├─ city: String (Indexed)                e.g., "Mumbai"
   ├─ state: String
   ├─ latitude: Float
   ├─ longitude: Float
   ├─ location_type: Integer                0=stop, 1=station
   ├─ parent_station_id: FK (self-referential)
   │
   ├─ NEW FIELDS FOR ADVANCED FEATURES:
   ├─ safety_score: Float (0-100)           Default: 50.0
   ├─ is_major_junction: Boolean            For transfer prioritization
   ├─ facilities_json: JSON
   │  ├─ wifi: bool
   │  ├─ lounge: bool
   │  ├─ food: bool
   │  ├─ accessible: bool
   │  └─ ... more facilities
   ├─ wheelchair_accessible: Boolean
   ├─ platform_count: Integer
   └─ distance_to_city_center_km: Float
   
   Indexes:
   ├─ idx_stops_name_trgm (PostgreSQL trigram GIN index)
   ├─ idx_stops_geom (PostgreSQL GIST geo index)
   └─ Regular indexes on: stop_id, city, parent_station_id
   
   Relationships:
   ├─ child_stops (back_populates parent_station)
   └─ stop_times (to StopTime)

3️⃣ ROUTE TABLE (Route = Train Service)
   ├─ id: Integer (Primary Key)
   ├─ route_id: String (Unique, Index)      e.g., "RAJ-001"
   ├─ agency_id: Integer (FK to Agency)
   ├─ short_name: String                    e.g., "RAJ"
   ├─ long_name: String                     e.g., "Rajdhani Express"
   ├─ description: String (Optional)
   ├─ url: String (Optional)
   ├─ route_type: Integer (Index)           0=Tram, 1=Subway, 2=Rail, 3=Bus
   │
   Relationships:
   └─ trips (one-to-many to Trip)

4️⃣ CALENDAR TABLE (Service Patterns)
   ├─ id: Integer (Primary Key)
   ├─ service_id: String (Unique FK)        e.g., "WKD-001"
   ├─ monday: Boolean
   ├─ tuesday: Boolean
   ├─ wednesday: Boolean
   ├─ thursday: Boolean
   ├─ friday: Boolean
   ├─ saturday: Boolean
   ├─ sunday: Boolean
   ├─ start_date: Date                      Service starts
   └─ end_date: Date                        Service ends
   
   Relationships:
   └─ trips (one-to-many via service_id)

5️⃣ CALENDAR_DATES TABLE (Exceptions)
   ├─ id: Integer (Primary Key)
   ├─ service_id: String (Indexed FK)
   ├─ date: Date (Indexed)
   ├─ exception_type: Integer               1=added, 2=removed
   │
   Unique Constraint:
   └─ (service_id, date)

6️⃣ TRIP TABLE (Individual Train Journey)
   ├─ id: Integer (Primary Key)
   ├─ trip_id: String (Unique, Index)       e.g., "RAJ-001-20250219"
   ├─ route_id: Integer (FK to Route)       What route it runs on
   ├─ service_id: String (FK to Calendar)   What service pattern
   ├─ headsign: String                      e.g., "New Delhi"
   ├─ direction_id: Integer                 0=outbound, 1=return
   │
   Relationships:
   ├─ route (FK to Route)
   └─ stop_times (one-to-many to StopTime)

7️⃣ STOPTIME TABLE ⭐ (Train Schedule at Each Station)
   ├─ id: Integer (Primary Key)
   ├─ trip_id: Integer (FK to Trip, Index)
   ├─ stop_id: Integer (FK to Stop, Index)
   ├─ stop_sequence: Integer                Order of stops
   ├─ arrival_time: Time                    HH:MM:SS
   ├─ departure_time: Time                  HH:MM:SS
   ├─ cost: Float (Optional)                Fare at this stop
   │
   Relationships:
   ├─ trip (FK to Trip)
   └─ stop (FK to Stop)
   
   Indexes:
   ├─ (trip_id, stop_sequence)
   └─ (stop_id, arrival_time)

8️⃣ TRANSFER TABLE (Inter-Station Connections)
   ├─ id: Integer (Primary Key)
   ├─ from_stop_id: Integer (FK to Stop, Index)
   ├─ to_stop_id: Integer (FK to Stop)
   ├─ transfer_type: Integer                0=no transfer, 1=timed, 2=min_time
   ├─ min_transfer_time: Integer            Minimum minutes needed
   │
   Index:
   └─ from_stop_id (for fast lookups)

9️⃣ SEAT_INVENTORY TABLE (Per-Trip-Coach Capacity)
   ├─ id: Integer (Primary Key)
   ├─ trip_id: Integer (FK to Trip)
   ├─ coach_type: String                    e.g., "AC_THREE_TIER"
   ├─ total_seats: Integer                  Capacity
   ├─ available_seats: Integer              Available now
   ├─ last_updated: DateTime
   │
   Index:
   └─ (trip_id, coach_type)

🔟 BOOKING TABLE (Customer Bookings)
   ├─ id: String (UUID, Primary Key)
   ├─ booking_date: DateTime
   ├─ user_id: String (FK to User, Index)
   ├─ pnr: String (Unique)                  Passenger Name Record
   ├─ status: String                        "confirmed", "cancelled", etc.
   ├─ total_fare: Float
   ├─ seats_booked: JSON
   │  ├─ trip_id
   │  ├─ coach_number
   │  ├─ seat_number
   │  └─ passenger details
   │
   └─ Relationships:
       ├─ user (FK to User)
       ├─ payment (one-to-one to Payment)
       └─ passengers (one-to-many to PassengerDetails)

1️⃣1️⃣ DISRUPTION TABLE (Real-time Updates)
   ├─ id: String (UUID, Primary Key)
   ├─ trip_id: Integer (FK to Trip)
   ├─ disruption_type: String               "delay", "cancellation", "reroute"
   ├─ severity: String                      "low", "medium", "high"
   ├─ description: String
   ├─ created_at: DateTime
   └─ creator_id: String (FK to User)

DATABASE INDEXES (Performance Optimization):
┌─ Main Indexes:
├─ stops(name) with trigram GIN          → Fast fuzzy search
├─ stops(stop_id)                        → Fast ID lookup
├─ stoptimes(trip_id, stop_sequence)    → Fast schedule lookup
├─ stoptimes(stop_id, arrival_time)     → Fast stop queries
├─ trips(route_id, service_id)          → Fast route queries
├─ transfers(from_stop_id)              → Fast transfer lookup
└─ calendar_dates(service_id, date)     → Fast service exceptions
```

### 3.3 DATABASE QUERIES IN SEARCH FLOW
```
🔍 File: backend/core/multi_modal_route_engine.py [980 lines]

WHEN load_graph_from_db() IS CALLED:

1️⃣ LOAD ALL STOPS INTO MEMORY
   Query:
   ┌──────────────────────────────────────┐
   │ SELECT * FROM stops;                 │
   └──────────────────────────────────────┘
   
   Result → Python Dictionary:
   stops_map = {
       stop_id: {
           'stop_id': '1234',
           'name': 'Mumbai Central',
           'city': 'Mumbai',
           'lat': 18.975,
           'lon': 72.823,
           'safety_score': 85.0,
           ...
       },
       ...
   }

2️⃣ LOAD ALL ROUTES
   Query:
   ┌──────────────────────────────────────┐
   │ SELECT * FROM gtfs_routes;           │
   └──────────────────────────────────────┘
   
   Result → routes_map = {
       route_id: {
           'route_id': 'RAJ-001',
           'short_name': 'RAJ',
           'long_name': 'Rajdhani Express',
           'route_type': 2,
           ...
       },
       ...
   }

3️⃣ LOAD ALL TRIPS
   Query:
   ┌──────────────────────────────────────┐
   │ SELECT * FROM trips;                 │
   └──────────────────────────────────────┘
   
   Result → trips_map = {
       trip_id: {
           'trip_id': 'RAJ-001-20250219',
           'route_id': 'RAJ-001',
           'service_id': 'WKD-001',
           ...
       },
       ...
   }

4️⃣ LOAD ALL STOP TIMES (Schedule)
   Query:
   ┌──────────────────────────────────────┐
   │ SELECT * FROM stop_times             │
   │ ORDER BY trip_id, stop_sequence;     │
   └──────────────────────────────────────┘
   
   Result → stop_times_map = {
       trip_id: [
           {
               'stop_id': stop_id_1,
               'arrival_time': '09:00:00',
               'departure_time': '09:05:00',
               'stop_sequence': 1,
               'cost': 0.0
           },
           {
               'stop_id': stop_id_2,
               'arrival_time': '13:30:00',
               'departure_time': '13:35:00',
               'stop_sequence': 2,
               'cost': 500.0
           },
           ...
       ],
       ...
   }

5️⃣ LOAD ALL TRANSFERS
   Query:
   ┌──────────────────────────────────────┐
   │ SELECT * FROM transfers;             │
   └──────────────────────────────────────┘
   
   Result → transfers_map = {
       from_stop_id: [
           {
               'to_stop_id': destination_stop_id,
               'transfer_type': 0,
               'min_transfer_time': 15
           },
           ...
       ],
       ...
   }

6️⃣ LOAD ALL CALENDAR SERVICES
   Query:
   ┌──────────────────────────────────────┐
   │ SELECT * FROM calendar;              │
   └──────────────────────────────────────┘
   
   Result → calendar_map = {
       service_id: {
           'monday': True,
           'tuesday': True,
           'wednesday': True,
           'thursday': True,
           'friday': True,
           'saturday': False,
           'sunday': False,
           'start_date': 2025-01-01,
           'end_date': 2025-12-31
       },
       ...
   }

7️⃣ LOAD CALENDAR EXCEPTIONS
   Query:
   ┌──────────────────────────────────────┐
   │ SELECT * FROM calendar_dates;        │
   └──────────────────────────────────────┘
   
   Result → calendar_dates_map = {
       service_id: [
           {
               'date': 2025-12-25,          # Christmas
               'exception_type': 2          # Service removed
           },
           ...
       ],
       ...
   }

PERFORMANCE NOTES:
├─ All GTFS data loaded into memory on startup
├─ In-memory search much faster than DB queries
├─ Cache invalidation: Handled by periodic reloads
└─ Total memory usage: ~100-500MB for typical network
```

---

# 4. ROUTE CALCULATION ENGINE - CORE ALGORITHM
## Location: `/backend/core`

### 4.1 MULTIMODAL ROUTE ENGINE (Main Orchestrator)
```
🚂 File: backend/core/multi_modal_route_engine.py [980 lines]

CLASS: MultiModalRouteEngine

INITIALIZATION:
__init__():
    ├─ stops_map: Dict[int, Dict]              (All stops)
    ├─ routes_map: Dict[int, Dict]             (All routes/trains)
    ├─ trips_map: Dict[int, Dict]              (All trip services)
    ├─ stop_times_map: Dict[int, List[Dict]]   (Schedule for each trip)
    ├─ transfers_map: Dict[int, List[Dict]]    (Possible transfers)
    ├─ calendar_map: Dict[int, Dict]           (Service patterns)
    ├─ calendar_dates_map: Dict[int, List[Dict]]  (Exceptions)
    ├─ _is_loaded: Boolean = False             (Data loaded flag)
    └─ _redis_client: Redis = None             (Cache client)

MAIN SEARCH METHOD:
search_single_journey(
    source_id: int,
    dest_id: int,
    start_datetime: datetime,
    max_transfers: int = 3,
    budget_mode: str = "all"
) -> List[JourneyOption]

    ALGORITHM: RAPTOR (Round-Based Public Transit Routing Algorithm)
    
    PURPOSE:
    Find all possible routes from source to destination,
    considering multiple transfers, time windows, and costs.
    
    STEPS:
    
    1️⃣ INITIALIZATION PHASE
    ├─────────────────────────
    │
    │ Initialize data structures:
    │ ├─ arrival_times: Dict[stop_id] = ∞  (Best time to reach each stop)
    │ ├─ arrival_times[source_id] = start_datetime  (Start time known)
    │ ├─ prev: Dict[stop_id] = None  (For path reconstruction)
    │ ├─ rounds: List of transfer rounds
    │ ├─ visited: Set = {source_id}  (Already processed stops)
    │ └─ k_best_routes: List[JourneyOption] = []  (Top K routes found)
    │
    │ Complexity: O(n) where n = number of stops
    
    2️⃣ MAIN RAPTOR LOOP (Per Transfer Round)
    ├─────────────────────────
    │
    │ FOR round IN range(0, max_transfers):
    │
    │ ├─ Get all trips that depart from reachable stops
    │ │  within the current time window
    │ │
    │ │ For each stop in visited:
    │ │    For each trip that departs from this stop:
    │ │        If trip.departure_time >= arrival_time[stop]:
    │ │            Add trip to candidate_trips
    │ │
    │ ├─ Scan all candidate trips
    │ │  (Simulate riding each trip and updating arrival times)
    │ │
    │ │ For each candidate_trip:
    │ │    For each stop_time in trip.stop_times (in order):
    │ │        If arrival_time[stop] < stop_time.arrival_time:
    │ │            Update arrival_time[stop] = stop_time.arrival_time
    │ │            prev[stop] = this trip segment
    │ │
    │ ├─ Apply transfer rules at each stop
    │ │  (Minimum time between arrival and next departure)
    │ │
    │ │ For each improved stop:
    │ │    Check min_transfer_time from transfers table
    │ │    Update reachability for next round
    │ │
    │ └─ If no improvements made in this round → BREAK
    │    (All optimal routes found)
    │
    │ Complexity: O(k * t * s) where:
    │    k = number of rounds (max_transfers)
    │    t = number of trips
    │    s = average stops per trip
    
    3️⃣ ROUTE EXTRACTION
    ├─────────────────────────
    │
    │ Once best arrival_times found:
    │ For each possible arrival at destination:
    │    │
    │    ├─ Backtrack using prev[] pointers
    │    ├─ Reconstruct full path (all segments)
    │    ├─ Calculate total distance, time, transfers
    │    ├─ Calculate fare using FareCalculationEngine
    │    ├─ Calculate comfort/safety scores
    │    ├─ Create JourneyOption object
    │    └─ Add to k_best_routes
    │
    │ Complexity: O(routes_found * avg_segments_per_route)
    
    4️⃣ MULTI-OBJECTIVE SCORING & RANKING
    ├─────────────────────────
    │
    │ For each journeyFound:
    │    │
    │    ├─ SCORE[i] = w1 * time_score(i)
    │    │              + w2 * cost_score(i)
    │    │              + w3 * comfort_score(i)
    │    │              + w4 * safety_score(i)
    │    │
    │    ├─ where:
    │    │   w1, w2, w3, w4 = user-defined weights
    │    │   time_score = 1 / (1 + travel_time_hours)
    │    │   cost_score = max_fare / fare(i)
    │    │   comfort_score = avg_coach_comfort / num_transfers
    │    │   safety_score = avg_station_safety / num_transfers
    │    │
    │    └─ Sort by SCORE descending
    │
    │ Complexity: O(routes_found * log(routes_found))
    
    5️⃣ BUDGET FILTERING
    ├─────────────────────────
    │
    │ If budget_mode == "economy":
    │    └─ Keep only journeys with cheapest_fare <= economy_threshold
    │
    │ If budget_mode == "standard":
    │    └─ Keep journeys with standard_threshold <= fare <= mid_threshold
    │
    │ If budget_mode == "premium":
    │    └─ Keep only journeys with fare >= mid_threshold
    │
    │ Complexity: O(routes_found)
    
    6️⃣ RETURN TOP K RESULTS
    ├─────────────────────────
    │
    │ Return best 15-20 journeys
    │ (Or fewer if fewer valid routes exist)
    │
    └─ OVERALL TIME COMPLEXITY: O(k * t * s + r * log(r))
       where k = transfers, t = trips, s = stops/trip, r = routes_found
```

### 4.2 RAPTOR ALGORITHM - PSEUDOCODE
```
FUNCTION RaptorSearch(source_id, dest_id, start_datetime, max_transfers):
    
    # Data structures
    arrival_times = {stop: ∞ for all stops}
    arrival_times[source_id] = start_datetime
    
    journeys_found = []
    
    # Main RAPTOR rounds
    FOR round = 0 TO max_transfers:
        marked_vertices = {}
        
        # For each improved stop from previous round
        FOR stop IN improved_stops_from_previous_round:
            
            # Get all trips that depart from this stop
            FOR trip IN get_departing_trips(stop, arrival_times[stop]):
                
                # Ride the trip and update all stops along the way
                FOR stop_time IN trip.stop_times (in order):
                    IF stop_time.arrival_time < arrival_times[stop_time.stop_id]:
                        
                        # Better arrival found
                        arrival_times[stop_time.stop_id] = stop_time.arrival_time
                        marked_vertices[stop_time.stop_id] = True
                        
                        # Check if destination reached
                        IF stop_time.stop_id == dest_id:
                            journey = reconstruct_path(source_id, stop_time.stop_id)
                            journeys_found.append(journey)
        
        # If no improvements, all optimal routes found
        IF len(marked_vertices) == 0:
            BREAK
    
    # Score and rank journeys
    FOR journey IN journeys_found:
        journey.score = calculate_multi_objective_score(journey)
    
    journeys_found.sort_by(score, descending=True)
    RETURN journeys_found[0:20]  # Top 20 routes

```

### 4.3 JOURNEY RECONSTRUCTION ENGINE
```
🔄 File: backend/core/journey_reconstruction.py [466 lines]

CLASS: JourneyReconstructionEngine

PURPOSE:
Take raw RAPTOR results and convert to complete journey details
with all necessary information for booking and display.

MAIN METHOD:
reconstruct_journey(
    trip_segments: List[TripSegment],
    start_date: date,
    passenger_profile: Dict
) -> JourneyOption

EXECUTION FLOW:

1️⃣ INPUT VALIDATION
├─────────────────
│ ├─ Validate all trip_segments exist in DB
│ ├─ Validate date is valid
│ ├─ Validate passenger count matches
│ └─ Throw error if invalid

2️⃣ SEGMENT DETAILS EXTRACTION
├─────────────────────────────
│
│ FOR each trip_segment:
│    │
│    ├─ Query database:
│    │  ├─ FROM trips WHERE trip_id = segment.trip_id
│    │  ├─ FROM gtfs_routes WHERE id = trip.route_id
│    │  ├─ FROM stops WHERE id IN (from_stop_id, to_stop_id)
│    │  └─ FROM stop_times WHERE trip_id = segment.trip_id
│    │
│    ├─ Extract segment_detail:
│    │  ├─ segment_id: UUID for this segment
│    │  ├─ train_number: From trip DB
│    │  ├─ train_name: From route DB
│    │  ├─ depart_station: From stops DB
│    │  ├─ depart_time: From stop_times DB
│    │  ├─ depart_platform: Simulated (9-16)
│    │  ├─ arrival_station: From stops DB
│    │  ├─ arrival_time: From stop_times DB
│    │  ├─ arrival_platform: Simulated (1-8)
│    │  ├─ distance_km: Calculated from lat/lon
│    │  ├─ travel_time: arrival_time - depart_time
│    │  ├─ running_days: From calendar DB
│    │  ├─ halt_times: For each intermediate stop
│    │  └─ availability: Query SeatInventory table
│    │
│    └─ Create SegmentDetail dataclass object

3️⃣ TRANSFER TIME CALCULATION
├──────────────────────────
│
│ FOR each pair of consecutive segments:
│    │
│    ├─ Get arrival time of segment[i] at station X
│    ├─ Get departure time of segment[i+1] from station X
│    │
│    ├─ transfer_duration = departure[i+1] - arrival[i]
│    │
│    ├─ Validate transfer feasibility:
│    │  ├─ Query transfers table:
│    │  │  SELECT min_transfer_time
│    │  │  FROM transfers
│    │  │  WHERE from_stop_id = X
│    │  │
│    │  └─ IF transfer_duration < min_transfer_time:
│    │     └─ Mark transfer as TIGHT
│    │
│    └─ Store transfer_duration

4️⃣ FARE CALCULATION (Per Segment)
├─────────────────────────────
│
│ FareCalculationEngine.calculate_fare(
│     segment_detail,
│     coach_type="AC_THREE_TIER",
│     passenger_profiles=passenger_list,
│     is_tatkal=False
│ )
│
│ Returns:
│ ├─ base_fare: INR calculated using:
│ │  │
│ │  ├─ distance_km = segment.distance
│ │  ├─ BASE_FARE_PER_100KM[coach_type] = rate
│ │  ├─ fare = (distance_km / 100) * rate
│ │  │
│ │  ├─ IF distance 50-100km:
│ │  │   └─ fare *= 1.10  (surcharge)
│ │  │
│ │  └─ IF distance > 100km:
│ │      └─ fare *= 1.15  (surcharge)
│ │
│ ├─ tatkal_charge: If is_tatkal=True
│ │   └─ tatkal_charge = fare * 0.10  (10% extra)
│ │
│ ├─ gst: fare * 0.05  (5% GST)
│ │
│ └─ concession_discount: If passenger has concession
│    └─ discount = fare * DISCOUNT_RATE[concession_type]
│
│ total_segment_fare = base_fare + tatkal_charge + gst - discount
│
│ Complexity: O(1) per segment

5️⃣ JOURNEY COMPOSITION
├──────────────────
│
│ Create JourneyOption object:
│
│ journey = JourneyOption(
│     journey_id=generate_uuid(),
│     segments=all_segment_details,
│     start_date=start_date.isoformat(),
│     end_date=start_date.isoformat(),  # Or next day if overnight
│     
│     total_distance_km=sum(seg.distance_km for seg in segments),
│     total_travel_time_mins=sum(seg.travel_time_mins for seg in segments),
│     num_segments=len(segments),
│     num_transfers=len(segments) - 1,
│     
│     cheapest_fare=calculate_fare(coach_type="SLEEPER"),
│     premium_fare=calculate_fare(coach_type="AC_FIRST_CLASS"),
│     
│     is_direct=len(segments) == 1,
│     has_overnight=(end_date > start_date) or (arrival_time < depart_time),
│     
│     availability_status=determine_availability(segments)
│ )
│
│ Complexity: O(n) where n = number of segments

6️⃣ AVAILABILITY DETERMINATION
├──────────────────────────
│
│ availability_status logic:
│
│ available_seats = []
│ FOR segment IN segments:
│     │
│     # Query seat inventory
│     seat_info = db.query(SeatInventory).filter(
│         trip_id = segment.trip_id,
│         coach_type = "AC_THREE_TIER"
│     ).first()
│     │
│     available_seats.append(seat_info.available_seats)
│
│ min_available = min(available_seats)
│
│ IF min_available > 10:
│     └─ status = "available"
│ ELIF min_available > 0:
│     └─ status = "partially_available"
│ ELSE:
│     └─ status = "waitlist_only"
│
└─ return status

```

### 4.4 FARE CALCULATION ENGINE
```
💰 File: backend/core/journey_reconstruction.py (Lines 160-250)

CLASS: FareCalculationEngine

SAMPLE CALCULATION:

INPUTS:
├─ distance_km: 1440.0
├─ coach_type: "AC_THREE_TIER"
├─ passenger_profiles: [
│   {name: "John", age: 30, concession: None},
│   {name: "Jane", age: 28, concession: "student"}
│  ]
├─ is_tatkal: False
└─ is_second_journey: False

ALGORITHM:

1️⃣ BASE FARE CALCULATION
├────────────────────
│
│ base_rate = BASE_FARE_PER_100KM["AC_THREE_TIER"]
│           = 150 INR
│
│ base_fare = (distance_km / 100) * base_rate
│           = (1440 / 100) * 150
│           = 14.4 * 150
│           = 2160 INR

2️⃣ SURCHARGE APPLICATION
├──────────────────────
│
│ IF distance > 100km:
│     surcharge_multiplier = 1.15  # 15% extra
│ ELSE IF distance > 50km:
│     surcharge_multiplier = 1.10  # 10% extra
│ ELSE:
│     surcharge_multiplier = 1.0   # No surcharge
│
│ base_fare_with_surcharge = base_fare * surcharge_multiplier
│                          = 2160 * 1.15
│                          = 2484 INR

3️⃣ TATKAL CHARGE (if applicable)
├─────────────────────────────
│
│ IF is_tatkal:
│     tatkal_charge = base_fare_with_surcharge * 0.10
│                   = 2484 * 0.10
│                   = 248.4 INR
│ ELSE:
│     tatkal_charge = 0

4️⃣ GST CALCULATION (5%)
├──────────────────────
│
│ gst = (base_fare_with_surcharge + tatkal_charge) * 0.05
│     = (2484 + 0) * 0.05
│     = 124.2 INR

5️⃣ PER-PASSENGER FARES (With Concessions)
├─────────────────────────────────────
│
│ Passenger 1 (John, no concession):
│     passenger_fare = base_fare_with_surcharge + tatkal_charge + gst
│                   = 2484 + 0 + 124.2
│                   = 2608.2 INR
│
│ Passenger 2 (Jane, student - 25% discount):
│     concession_discount = (base_fare_with_surcharge * 0.25)
│                        = 2484 * 0.25
│                        = 621 INR
│     passenger_fare = 2484 - 621 + 0 + 62.1  (GST on discounted fare)
│                   = 1925.1 INR

6️⃣ TOTAL JOURNEY FARE
├──────────────────
│
│ total_fare = sum of all passenger fares
│            = 2608.2 + 1925.1
│            = 4533.3 INR
│
│ cheapest_fare = min(all_coach_fares)
│               = min(sleeper=1500, general=300, second=600, ...)
│               = 300 INR (General coach)
│
│ premium_fare = max(all_coach_fares)
│              = max(first_ac=5000, ac_1=4000, ...)
│              = 5000 INR (AC First Class)

7️⃣ FARE BREAKDOWN (Returned to User)
├──────────────────────────────────
│
│ RESPONSE:
│ {
│     "base_fare": 2484.0,
│     "surcharge": 0.0,                    # Included in base_fare
│     "tatkal_charge": 0.0,
│     "gst": 124.2,
│     "concession_discount": 621.0,
│     "total_fare": 4533.3,
│     "currency": "INR",
│     "per_passenger_breakdown": [
│         {
│             "passenger": "John Doe",
│             "age": 30,
│             "concession": None,
│             "fare": 2608.2
│         },
│         {
│             "passenger": "Jane Doe",
│             "age": 28,
│             "concession": "student",
│             "fare": 1925.1
│         }
│     ]
│ }

```

---

# 5. JOURNEY VERIFICATION & REAL-TIME DATA LAYER
## Location: `/backend/services`

### 5.1 VERIFICATION ENGINE
```
✅ File: backend/services/verification_engine.py [442 lines]

CLASS: SimulatedRealTimeDataProvider

PURPOSE:
Simulate real-time data verification checks for offline testing.
In production, this connects to IRCTC live APIs.

METHOD: verify_journey(
    journey_option: JourneyOption,
    travel_date: date,
    coach_preference: str
) -> VerificationDetails

VERIFICATION PROCESS:

1️⃣ SEAT AVAILABILITY CHECK
├──────────────────────
│
│ FOR each segment IN journey.segments:
│     │
│     ├─ Query SeatInventory:
│     │  ├─ trip_id = segment.trip_id
│     │  ├─ coach_type = coach_preference
│     │  └─ Get: total_seats, available_seats, booked_seats
│     │
│     └─ Determine status:
│         ├─ IF available_seats >= num_passengers:
│         │   └─ status = "VERIFIED" (All available)
│         ├─ ELIF available_seats > 0:
│         │   └─ status = "PARTIALLY_AVAILABLE"
│         └─ ELSE:
│             └─ status = "WAITLIST" (None available)
│
│ Result: SeatCheckResult {
│     status,
│     total_seats,
│     available_seats,
│     booked_seats,
│     waiting_list_position,
│     message
│ }

2️⃣ TRAIN SCHEDULE VERIFICATION
├──────────────────────────
│
│ FOR each segment IN journey.segments:
│     │
│     ├─ Get scheduled times from StopTime:
│     │  ├─ departure_time = segment.depart_time (from GTFS)
│     │  └─ arrival_time = segment.arrival_time
│     │
│     ├─ Check for real-time delays:
│     │  ├─ Query Disruption table:
│     │  │  SELECT * FROM disruptions
│     │  │  WHERE trip_id = segment.trip_id
│     │  │  AND disruption_type = 'delay'
│     │  │
│     │  ├─ IF delay found:
│     │  │   ├─ actual_departure = scheduled + delay
│     │  │   ├─ actual_arrival = scheduled + delay
│     │  │   └─ delay_minutes = delay
│     │  │
│     │  └─ ELSE:
│     │      ├─ actual_departure = scheduled
│     │      ├─ actual_arrival = scheduled
│     │      └─ delay_minutes = 0
│     │
│     └─ Check for cancellations:
│         ├─ IF disruption_type = 'cancellation':
│         │   └─ status = "CANCELLED"
│         └─ ELSE:
│             └─ status = "VERIFIED"
│
│ Result: TrainScheduleCheckResult {
│     status,
│     scheduled_departure,
│     scheduled_arrival,
│     actual_departure,
│     actual_arrival,
│     delay_minutes,
│     message
│ }

3️⃣ FARE VERIFICATION
├─────────────────
│
│ ├─ Lock calculated fare (use existing calculation)
│ │
│ ├─ Verify no promotional conflicts:
│ │  ├─ Can't combine tatkal + concession (rules)
│ │  └─ Apply applicable discounts
│ │
│ ├─ Add GST (if applicable)
│ │
│ └─ Result: FareCheckResult {
│     status: "VERIFIED",
│     base_fare,
│     gst,
│     total_fare,
│     applicable_discounts: ["student_concession"],
│     cancellation_charges: 0.0,
│     message: "Fare verified"
│ }

4️⃣ RESTRICTIONS & WARNINGS
├─────────────────────────
│
│ restrictions = []
│ warnings = []
│
│ # Safety checks
│ IF journey.has_overnight:
│     warnings.append("Night journey - ensure safe transit")
│
│ IF journey.num_transfers > 2:
│     warnings.append("Multiple transfers - risk of missing connections")
│
│ # Booking policy checks
│ booking_window = 60  # Days in advance
│ IF (travel_date - today).days > booking_window:
│     restrictions.append("Travel date beyond booking window")
│
│ # Tatkal checks (same-day booking)
│ IF is_tatkal:
│     tatkal_time = 10:00 AM
│     IF current_time < tatkal_time:
│         restrictions.append("Tatkal window not opened yet")
│
│ # PNR conflict check
│ IF check_duplicate_pnr_in_pending_bookings():
│     restrictions.append("PNR conflict - try different journey")

5️⃣ FINAL VERIFICATION RESULT
├──────────────────────────
│
│ is_bookable = (
│     seat_verification.status != "CANCELLED" AND
│     schedule_verification.status != "CANCELLED" AND
│     len(restrictions) == 0
│ )
│
│ verification_details = VerificationDetails(
│     journey_id=journey.journey_id,
│     verification_timestamp=now.isoformat(),
│     overall_status=determine_overall_status(),
│     seat_verification=seat_result,
│     schedule_verification=schedule_result,
│     fare_verification=fare_result,
│     restrictions=restrictions,
│     warnings=warnings,
│     is_bookable=is_bookable
│ )
│
│ return verification_details
```

### 5.2 SEAT ALLOCATION ENGINE
```
💺 File: backend/services/seat_allocation.py [442 lines]

CLASS: SeatAllocationService

PURPOSE:
Manage seat availability, allocation, and confirmation.

COACH TYPES & CAPACITIES:
┌──────────────────────────────────┐
│ AC_FIRST_CLASS ("1A")  - 18 seats │
│ AC_TWO_TIER ("2A")     - 48 seats │
│ AC_THREE_TIER ("3A")   - 64 seats │
│ FIRST_CLASS ("FC")     - 48 seats │
│ SLEEPER ("SL")         - 72 seats │
│ GENERAL ("GN")         - 200 seats│
│ SECOND_CLASS ("2S")    - 120 seats│
└──────────────────────────────────┘

SEAT TYPES:
├─ LOWER (Window)     - Most preferred
├─ MIDDLE             - Medium comfort
├─ UPPER              - Low comfort (upper bunk)
├─ SIDE_LOWER         - Side lower berth
├─ SIDE_UPPER         - Side upper berth
├─ WINDOW             - Window seat
└─ AISLE              - Aisle seat

SEAT STATES:
├─ AVAILABLE          - Can be booked
├─ BOOKED             - Sold to passenger
├─ BLOCKED            - Maintenance/reserved
├─ RESERVED           - For differently-abled
└─ WAITING_LIST       - On wait list

ALLOCATION METHOD:
allocate_seats(
    trip_id: int,
    passenger_list: List[PassengerInfo],
    coach_type: CoachType,
    seat_preference: str = "LOWER"
) -> List[Seat]

ALGORITHM:

1️⃣ INITIALIZE COACH
├──────────────────
│
│ coach_info = Coach(
│     coach_id="A",
│     coach_type=coach_type,
│     total_seats=get_capacity(coach_type)
│ )
│
│ coach_info.initialize_seats()
│ ├─ Creates all seat objects
│ └─ Sets initial status = AVAILABLE

2️⃣ QUERY OCCUPIED SEATS
├─────────────────────
│
│ occupied_seats_query = db.query(Seat).filter(
│     Seat.trip_id == trip_id,
│     Seat.coach_number == coach_id,
│     Seat.status.in_(["BOOKED", "BLOCKED", "RESERVED"])
│ ).all()
│
│ FOR occupied_seat IN occupied_seats_query:
│     coach_info.seats[occupied_seat.seat_id].status = occupied_seat.status

3️⃣ FIND AVAILABLE SEATS
├────────────────────
│
│ available_seats = [
│     seat for seat in coach_info.seats.values()
│     if seat.status == AVAILABLE
│ ]
│
│ # Sort by preference
│ IF seat_preference == "LOWER":
│     available_seats.sort_by(
│         lambda s: (
│             0 if s.seat_type == LOWER else 1,
│             s.seat_number
│         )
│     )

4️⃣ ALLOCATE TO PASSENGERS
├──────────────────────
│
│ allocated_seats = []
│
│ FOR i, passenger IN enumerate(passenger_list):
│     │
│     IF i < len(available_seats):
│         │
│         seat = available_seats[i]
│         seat.status = SeatStatus.BOOKED
│         seat.booked_by_pnr = pnr  # Will be generated after booking
│         seat.passenger_name = passenger.full_name
│         seat.passenger_age = passenger.age
│         seat.concession = passenger.concession_type
│         │
│         allocated_seats.append(seat)
│     ELSE:
│         │
│         # No seats available, add to waiting list
│         waiting_seat = Seat(
│             seat_id=f"{coach_id}_WL_{i+1}",
│             coach_number=coach_id,
│             seat_number=i+1,
│             seat_type=SeatType.WAITING,
│             status=SeatStatus.WAITING_LIST,
│             passenger_name=passenger.full_name
│         )
│         allocated_seats.append(waiting_seat)

5️⃣ PERSIST TO DATABASE
├───────────────────
│
│ FOR seat IN allocated_seats:
│     db.add(seat)
│
│ db.commit()

6️⃣ RETURN ALLOCATION
├─────────────────
│
│ return {
│     "trip_id": trip_id,
│     "coach_type": coach_type.value,
│     "allocated_seats": [s.to_dict() for s in allocated_seats],
│     "total_allocated": len([s for s in allocated_seats if s.status == BOOKED]),
│     "waiting_list": len([s for s in allocated_seats if s.status == WAITING_LIST])
│ }
```

---

# 6. BOOKING ORCHESTRATION & PERSISTENCE
## Location: `/backend/api`, `/backend/services`

### 6.1 BOOKING FLOW
```
📋 File: backend/api/integrated_search.py (booking endpoints)

ENDPOINT: POST /api/bookings/confirm

REQUEST:
┌────────────────────────────────────┐
│ BookingConfirmationRequest         │
├────────────────────────────────────┤
│ journey_id: str                    │
│ selected_coach: str                │
│ passengers: List[PassengerInfo]    │
│ payment_method: str                │
└────────────────────────────────────┘

EXECUTION FLOW:

1️⃣ VERIFY BOOKING PRECONDITIONS
├──────────────────────────────
│
│ ├─ Verify journey_id exists
│ ├─ Verify all passengers valid (age, name, etc.)
│ ├─ Verify coach type still available
│ ├─ Verify user has payment method configured
│ └─ Verify no duplicate PNRs pending

2️⃣ INITIATE PAYMENT
├────────────────
│
│ payment_intent = process_payment(
│     amount=total_fare,
│     currency="INR",
│     method=payment_method,      # "card", "upi", "wallet"
│     user_id=current_user.id
│ )
│
│ Returns: payment_intent_id

3️⃣ ALLOCATE SEATS
├────────────────
│
│ allocated_seats = SeatAllocationService.allocate_seats(
│     trip_id=journey.segments[0].trip_id,
│     passenger_list=passengers,
│     coach_type=CoachType[selected_coach]
│ )

4️⃣ GENERATE PNR
├──────────────
│
│ pnr = generate_pnr()  # e.g., "2025025001234"
│ Returns unique 10-digit PNR

5️⃣ CREATE BOOKING RECORD
├──────────────────────
│
│ booking = Booking(
│     id=str(uuid.uuid4()),
│     booking_date=now,
│     user_id=current_user.id,
│     pnr=pnr,
│     status="confirmed",
│     total_fare=total_fare,
│     seats_booked=json.dumps({
│         "trip_id": journey.segments[0].trip_id,
│         "coach_number": "A",
│         "seats": [s.seat_id for s in allocated_seats],
│         "passengers": [
│             {
│                 "seat_id": seat.seat_id,
│                 "name": passenger.full_name,
│                 "age": passenger.age,
│                 "gender": passenger.gender,
│                 "concession": passenger.concession_type
│             }
│             for seat, passenger in zip(allocated_seats, passengers)
│         ]
│     })
│ )
│
│ db.add(booking)
│ db.commit()

6️⃣ CREATE PASSENGER DETAILS
├────────────────────────
│
│ FOR i, passenger IN enumerate(passengers):
│     passenger_detail = PassengerDetails(
│         booking_id=booking.id,
│         passenger_number=i+1,
│         full_name=passenger.full_name,
│         age=passenger.age,
│         gender=passenger.gender,
│         concession_type=passenger.concession_type,
│         phone=passenger.phone,
│         seat_id=allocated_seats[i].seat_id
│     )
│     db.add(passenger_detail)
│
│ db.commit()

7️⃣ CREATE PAYMENT RECORD
├──────────────────────
│
│ payment = Payment(
│     id=str(uuid.uuid4()),
│     booking_id=booking.id,
│     user_id=current_user.id,
│     amount=total_fare,
│     currency="INR",
│     method=payment_method,
│     status="pending",
│     external_transaction_id=payment_intent_id,
│     created_at=now
│ )
│
│ db.add(payment)
│ db.commit()

8️⃣ ISSUE TICKET
├──────────────
│
│ ticket = Ticket(
│     id=str(uuid.uuid4()),
│     booking_id=booking.id,
│     pnr=pnr,
│     status="issued",
│     created_at=now
│ )
│
│ db.add(ticket)
│ db.commit()

9️⃣ SEND CONFIRMATION
├─────────────────
│
│ ├─ Send PNR via SMS
│ ├─ Send booking details via email
│ ├─ Send ticket PDF to user
│ └─ Update user's booking list UI

🔟 RETURN RESPONSE
├────────────────
│
│ return {
│     "pnr": pnr,
│     "booking_id": booking.id,
│     "status": "confirmed",
│     "total_fare": total_fare,
│     "journey_details": {
│         "departure": "...",
│         "arrival": "...",
│         "train": "...",
│         ...
│     },
│     "passengers": [
│         {"name": "...", "seat": "A-01-LOWER"}
│     ],
│     "ticket_url": "/tickets/...",
│     "confirmation_code": confirmation_code
│ }
```

---

# 7. RESPONSE GENERATION & TRANSMISSION
## Location: `/backend/api` → `/src`

### 7.1 RESPONSE PIPELINE
```
📤 RESPONSE FLOW (After route calculation)

STEP 1: SERIALIZE JOURNEY OPTIONS
├────────────────────────────────
│
│ For each JourneyOption:
│     route_dict = {
│         "id": journey.journey_id,
│         "segments": [
│             {
│                 "segment_id": seg.segment_id,
│                 "train_number": seg.train_number,
│                 "train_name": seg.train_name,
│                 "departure": {
│                     "station": seg.depart_station,
│                     "code": seg.depart_code,
│                     "time": seg.depart_time,
│                     "platform": seg.depart_platform
│                 },
│                 "arrival": {
│                     "station": seg.arrival_station,
│                     "code": seg.arrival_code,
│                     "time": seg.arrival_time,
│                     "platform": seg.arrival_platform
│                 },
│                 "distance_km": seg.distance_km,
│                 "travel_time": f"{hours:02d}:{mins:02d}",
│                 "running_days": seg.running_days,
│                 "availability": {
│                     "ac_first": seg.ac_first_available,
│                     "ac_second": seg.ac_second_available,
│                     "ac_third": seg.ac_third_available,
│                     "sleeper": seg.sleeper_available
│                 },
│                 "fare": {
│                     "base_fare": seg.base_fare,
│                     "tatkal_applicable": seg.tatkal_applicable
│                 }
│             }
│             for seg in journey.segments
│         ],
│         "total_duration_minutes": journey.total_travel_time_mins,
│         "total_distance_km": journey.total_distance_km,
│         "num_transfers": journey.num_transfers,
│         "num_segments": journey.num_segments,
│         "is_direct": journey.is_direct,
│         "has_overnight": journey.has_overnight,
│         "cheapest_fare": journey.cheapest_fare,
│         "premium_fare": journey.premium_fare,
│         "availability_status": journey.availability_status
│     }

STEP 2: ADD METADATA
├─────────────────
│
│ response = {
│     "request_id": request_id,
│     "request_timestamp": now.isoformat(),
│     "search_query": {
│         "source": search_request.source,
│         "destination": search_request.destination,
│         "date": search_request.date,
│         "budget": search_request.budget
│     },
│     "routes": [route_dict for all routes],
│     "total_results": len(routes),
│     "sorted_by": sort_order,
│     "query_time_ms": elapsed_time * 1000,
│     "cache_hit": is_from_cache
│ }

STEP 3: SERIALIZE TO JSON
├──────────────────────
│
│ json_response = json.dumps(response, default=str)
│ ├─ Handle datetime serialization
│ ├─ Handle Decimal/Float serialization
│ └─ Handle UUID serialization

STEP 4: ADD HTTP HEADERS
├──────────────────────
│
│ headers = {
│     "Content-Type": "application/json",
│     "X-Request-ID": request_id,
│     "X-Query-Time-Ms": str(elapsed_ms),
│     "Cache-Control": "public, max-age=3600",
│     "ETag": hashlib.md5(json_response.encode()).hexdigest()
│ }

STEP 5: SEND RESPONSE
├─────────────────
│
│ return JSONResponse(
│     content=response,
│     status_code=200,
│     headers=headers,
│     media_type="application/json"
│ )

STEP 6: FRONTEND RECEIVES & PROCESSES
├──────────────────────────────────
│
│ File: src/services/railwayBackApi.ts
│
│ searchRoutesApi(query): Promise<Route[]> {
│     const response = await fetch("http://localhost:8000/api/search/", {
│         method: "POST",
│         headers: {
│             "Content-Type": "application/json"
│         },
│         body: JSON.stringify(query)
│     })
│     
│     const json = await response.json()
│     
│     // Map backend response to frontend format
│     return mapBackendRoutesToRoutes(json.routes)
│ }

STEP 7: DISPLAY IN UI
├───────────────────
│
│ File: src/pages/Index.tsx
│
│ setOptimalRoutes(routes)  ← Update state
│ ├─ Triggersre-render
│ └─ Renders <RouteCard /> components
│
│ Displayed to user as:
│ ┌─────────────────────────────────────┐
│ │ 🚂 Rajdhani Express                 │
│ │ 09:00 → 09:30 (+1 day)              │
│ │ 1440 km | 24h 30m | 2 transfers     │
│ │ ₹1,500 - ₹3,500                     │
│ │ [BOOK] [DETAILS] [SHARE]            │
│ └─────────────────────────────────────┘
```

---

# 8. KEY FILES SUMMARY & THEIR ROLES

## BACKEND ARCHITECTURE

```
🔴 CRITICAL FILES (Program halts without these)
├─ backend/app.py                          - FastAPI main app initialization
├─ backend/core/multi_modal_route_engine.py - RAPTOR algorithm (route calculation)
├─ backend/database/models.py              - SQLAlchemy ORM models (GTFS schema)
├─ backend/database/session.py             - Database session management
└─ backend/database/config.py              - Database configuration

🟠 IMPORTANT FILES (Core functionality)
├─ backend/api/search.py                   - Main search endpoint
├─ backend/api/integrated_search.py        - Unified v2 API
├─ backend/core/journey_reconstruction.py  - Journey details & fare calculation
├─ backend/services/seat_allocation.py     - Seat allocation logic
├─ backend/services/verification_engine.py - Real-time verification
├─ backend/schemas.py                      - Pydantic request/response models
└─ backend/utils/station_utils.py          - Fuzzy station matching

🟡 SUPPORTING FILES (Infrastructure)
├─ backend/services/cache_service.py       - Redis caching
├─ backend/services/multi_layer_cache.py   - Cache abstraction
├─ backend/utils/limiter.py                - Rate limiting
├─ backend/utils/metrics.py                - Prometheus metrics
├─ backend/utils/validation.py             - Input validation utilities
└─ backend/core/validator/                 - Validation framework

⚪ DATABASE FILES
├─ backend/database/__init__.py            - DB module initialization
├─ backend/models.py                       - Booking/User models (legacy)
└─ backend/database/models.py              - GTFS models (current)
```

## FRONTEND ARCHITECTURE

```
🟢 MAIN PAGES
├─ src/pages/Index.tsx                     - Home/main search page (948 lines)
├─ src/pages/Bookings.tsx                  - User's bookings page
├─ src/pages/Ticket.tsx                    - Ticket display
├─ src/pages/mini-app/Search.tsx           - Mini app search

🔵 KEY COMPONENTS
├─ src/components/StationSearch.tsx        - Station autocomplete
├─ src/components/RouteCard.tsx            - Route display card
├─ src/components/booking/BookingFlowModal.tsx  - Booking flow
├─ src/components/RailAssistantChatbot.tsx - AI chatbot

🟣 SERVICES & APIS
├─ src/services/railwayBackApi.ts          - Backend API calls
├─ src/api/flow.ts                         - Flow API endpoints
├─ src/lib/paymentApi.ts                   - Payment API
└─ src/services/journey_reconstruction.ts  - (Mirror of backend)

🟡 CONTEXT & STATE
├─ src/context/AuthContext.tsx             - Authentication state
├─ src/context/BookingFlowContext.tsx      - Booking state
└─ src/context/ThemeContext.tsx            - Theme management
```

## DATABASE SCHEMA DIAGRAM

```
                          ┌─────────────────┐
                          │    AGENCY       │
                          ├─────────────────┤
                          │ id (PK)         │
                          │ agency_id       │
                          │ name            │
                          └────────┬────────┘
                                   │
                                   │ References
                                   ▼
                          ┌─────────────────┐
                          │    ROUTE        │ (e.g., Rajdhani Express)
                          ├─────────────────┤
                          │ id (PK)         │
                          │ route_id        │
                          │ long_name       │
                          │ route_type      │
                          └────────┬────────┘
                                   │
                                   │
                                   ▼
                    ┌──────────────────────────┐
                    │    CALENDAR              │ (Service Days)
                    ├──────────────────────────┤
                    │ id (PK)                  │
                    │ service_id (Unique)      │
                    │ mon-sun (Boolean array)  │
                    │ start_date/end_date      │
                    └──────┬───────────────────┘
                           │
                    ┌──────┴──────────────────┐
                    │                         │
                    ▼                         ▼
    ┌──────────────────────────┐  ┌────────────────────────────┐
    │    CALENDAR_DATES        │  │    TRIP                    │
    ├──────────────────────────┤  ├────────────────────────────┤
    │ service_id (FK)          │  │ id (PK)                    │
    │ date                     │  │ trip_id (Unique)           │
    │ exception_type           │  │ route_id (FK)              │
    │ (1=add,2=remove)         │  │ service_id (FK)            │
    └──────────────────────────┘  │ headsign                   │
                                  │ direction_id               │
                                  └────────┬────────────────────┘
                                           │
                                           │ References
                                           ▼
                    ┌──────────────────────────────┐
                    │    STOP_TIMES                │ (Schedule)
                    ├──────────────────────────────┤
                    │ id (PK)                      │
                    │ trip_id (FK)                 │
                    │ stop_id (FK)                 │
                    │ stop_sequence                │
                    │ arrival_time                 │
                    │ departure_time               │
                    │ cost (Fare at this stop)     │
                    └──────┬───────────────────────┘
                           │
                           │ References
                           ▼
                    ┌──────────────────────────────┐
                    │    STOPS                     │ (Stations)
                    ├──────────────────────────────┤
                    │ id (PK)                      │
                    │ stop_id (Unique)             │
                    │ name (Indexed, Trigram)      │
                    │ city                         │
                    │ latitude/longitude           │
                    │ safety_score (0-100)         │
                    │ facilities_json              │
                    │ parent_station_id (FK)       │
                    └────────┬─────────────────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
                    ▼                 ▼
        ┌──────────────────┐  ┌──────────────────┐
        │   TRANSFERS      │  │   SEAT_INVENTORY │
        ├──────────────────┤  ├──────────────────┤
        │ from_stop_id(FK) │  │ trip_id (FK)     │
        │ to_stop_id (FK)  │  │ coach_type       │
        │ min_time         │  │ total_seats      │
        └──────────────────┘  │ available_seats  │
                              │ last_updated     │
                              └──────────────────┘

    ┌──────────────────────────────────────────────┐
    │    USER (Authentication User)                │
    ├──────────────────────────────────────────────┤
    │ id (UUID, PK)                                │
    │ email (Unique)                               │
    │ password_hash                                │
    │ phone_number                                 │
    │ role                                         │
    └────────┬─────────────────────────────────────┘
             │
             │ References
             ▼
    ┌──────────────────────────────────────────────┐
    │    BOOKING                                   │
    ├──────────────────────────────────────────────┤
    │ id (UUID, PK)                                │
    │ user_id (FK)                                 │
    │ pnr (Unique)                                 │
    │ booking_date                                 │
    │ status (confirmed/cancelled)                 │
    │ total_fare                                   │
    │ seats_booked (JSON)                          │
    └────────┬─────────────────────────────────────┘
             │
             ├─→ ┌────────────────────────────┐
             │   │  PASSENGER_DETAILS         │
             │   ├────────────────────────────┤
             │   │ id (PK)                    │
             │   │ booking_id (FK)            │
             │   │ full_name                  │
             │   │ age                        │
             │   │ gender                     │
             │   │ concession_type            │
             │   │ seat_id                    │
             │   └────────────────────────────┘
             │
             └─→ ┌────────────────────────────┐
                 │  PAYMENT                   │
                 ├────────────────────────────┤
                 │ id (UUID, PK)              │
                 │ booking_id (FK)            │
                 │ user_id (FK)               │
                 │ amount                     │
                 │ currency (INR)             │
                 │ method (card/upi/wallet)   │
                 │ status (pending/confirmed) │
                 │ external_transaction_id    │
                 └────────────────────────────┘

    ┌──────────────────────────────────────────────┐
    │    DISRUPTION (Real-time Updates)            │
    ├──────────────────────────────────────────────┤
    │ id (UUID, PK)                                │
    │ trip_id (FK to Trip)                         │
    │ disruption_type (delay/cancel/reroute)       │
    │ severity (low/medium/high)                   │
    │ description                                  │
    │ created_at                                   │
    └──────────────────────────────────────────────┘

```

---

# 9. COMPLETE DATA FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER JOURNEY START                           │
└─────────────────────────────────────────────────────────────────────┘
                                ▼
                    ┌───────────────────────┐
                    │  BROWSER / FRONTEND   │
                    │  (React + TypeScript) │
                    └───────────┬───────────┘
                                │
             1️⃣ USER ENTERS:   │
             • From: Mumbai    │
             • To: Delhi       │
             • Date: 2025-02-20│
             • Budget: Economy │
                                │
                                ▼
              ┌─────────────────────────────────┐
              │  src/pages/Index.tsx            │
              │  Collect search parameters      │
              └────────────┬────────────────────┘
                           │
              2️⃣ VALIDATE  │
              • Station not empty
              • Date >= today
              • Budget valid
                           │
                           ▼
              ┌─────────────────────────────────┐
              │  src/services/railwayBackApi.ts │
              │  searchRoutesApi()              │
              │  POST /api/search/              │
              └────────────┬────────────────────┘
                           │
        3️⃣ HTTP REQUEST   │
        POST /api/search/ │
        Content-Type: JSON│
        {                 │
          source: "...",  │
          destination:... │
          date: "...",    │
          budget: "...",  │
          ...             │
        }                 │
                           │
         ════════════════════════════════════════I N T E R N E T═════════════════════════════════════════════════════════
                           │
                           ▼
              ┌─────────────────────────────────────┐
              │     BACKEND - FastAPI              │
              │     app.py                          │
              │     Port: 8000                      │
              └────────────┬────────────────────────┘
                           │
                           ▼
              ┌──────────────────────────────┐
              │   API Route: /api/search/    │
              │   HTTP Status: 200           │
              │ backend/api/search.py:32    │
              │ search_routes_endpoint()     │
              └────────────┬─────────────────┘
                           │
    4️⃣ REQUEST VALIDATION │
       ├─ Check source/dest non-empty
       ├─ Validate date format
       ├─ Validate date >= today
       └─ Check budget category
                           │
                           ▼
              ┌──────────────────────────────┐
              │   Station Resolution         │
              │ resolve_stations() →         │
              │ Query DB for closest match   │
              │ (Fuzzy matching)             │
              └────────────┬─────────────────┘
                           │
    5️⃣ DATABASE QUERY:    │
    SELECT * FROM stops   │
    WHERE name ~* 'Mumbai'│ (Trigram search)
                           │
                           ▼
              ┌──────────────────────────┐
              │  PostgreSQL Database     │
              │  Query returns:          │
              │  ├─ Stop ID: 1234        │
              │  ├─ Name: Mumbai Central │
              │  ├─ Lat: 18.975         │
              │  └─ Lon: 72.823         │
              └────────────┬─────────────┘
                           │
                           ▼
              ┌──────────────────────────────┐
              │   Load Graph (GTFS Data)     │
              │ multi_modal_route_engine.py │
              │ load_graph_from_db()         │
              └────────────┬─────────────────┘
                           │
    6️⃣ BULK DATA LOAD:    │
    ├─ SELECT * FROM stops (10K rows)
    ├─ SELECT * FROM routes (1K rows)
    ├─ SELECT * FROM trips (50K rows)
    ├─ SELECT * FROM stop_times (500K rows)
    ├─ SELECT * FROM transfers (50K rows)
    ├─ SELECT * FROM calendar (1K rows)
    └─ SELECT * FROM calendar_dates (1K rows)
                           │
                           ▼
              ┌─────────────────────────────┐
              │   In-Memory Graph Ready     │
              │ stops_map: Dict[1234] = {...}
              │ routes_map, trips_map,      │
              │ stop_times_map,             │
              │ transfers_map loaded        │
              └────────────┬────────────────┘
                           │
                           ▼
    7️⃣ ROUTE CALCULATION  │
       │ multi_modal_route_engine.
       │ search_single_journey()
       │ (RAPTOR Algorithm)
       │
       ├─→ Initialize data structures
       │   ├─ arrival_times = {stop: ∞}
       │   ├─ arrival_times[source] = start_time
       │   ├─ prev = None
       │   └─ k_best_routes = []
       │
       ├─→ RAPTOR Round 0 (Direct routes)
       │   ├─ Get departing trips from source
       │   ├─ Scan each trip's stops
       │   ├─ Update arrival_times
       │   └─ Found routes: [Route1, Route2]
       │
       ├─→ RAPTOR Round 1 (1 transfer)
       │   ├─ Check transfers at stops
       │   ├─ Get connecting trips
       │   ├─ Update arrival_times
       │   └─ Found routes: [Route3, Route4, Route5]
       │
       ├─→ RAPTOR Round 2 (2 transfers)
       │   ├─ Check transfers at stops
       │   ├─ Get connecting trips
       │   ├─ Update arrival_times
       │   └─ Found routes: [Route6]
       │
       ├─→ Multi-objective Scoring
       │   ├─ Score = w1*time + w2*cost + w3*comfort + w4*safety
       │   └─ Sort routes by score
       │
       σnown_routes: 15 top journeys
                           │
                           ▼
    8️⃣ JOURNEY DETAILS    │
       │ journey_reconstruction.py
       │ FOR each route:
       │   ├─ Extract segment details
       │   ├─ Calculate fares
       │   ├─ Calculate distances
       │   ├─ Get seat availability
       │   └─ Create JourneyOption
       │
              ┌───────────────────────┐
              │  Route Details Built  │
              │  [                    │
              │    {                  │
              │      journey_id,      │
              │      segments: [...], │
              │      fare_breakdown,  │
              │      availability     │
              │    },                 │
              │    ...                │
              │  ]                    │
              └────────────┬──────────┘
                           │
                           ▼
    9️⃣ RESPONSE BUILD       │
       │ Serialize to JSON
       │ Add metadata
       │ Add HTTP headers
       │
              ┌──────────────────────┐
              │   JSON Response      │
              │   {                  │
              │     routes: [...],   │
              │     total_results: 15│
              │     query_time_ms: 245
              │   }                  │
              └────────────┬─────────┘
                           │
                           ▼
    🔟 SEND RESPONSE        │
       HTTP 200 OK          │
                            │
         ═════════════════════════════════════════I N T E R N E T════════════════════════════════════════════════════════
                           │
                           ▼
              ┌────────────────────────────┐
              │  Frontend Receives JSON    │
              │  src/services/api.ts       │
              └────────────┬───────────────┘
                           │
                           ▼
              ┌────────────────────────────┐
              │ Map to Frontend Format     │
              │ mapBackendRoutesToRoutes() │
              └────────────┬───────────────┘
                           │
                           ▼
              ┌────────────────────────────┐
              │  Update React State        │
              │  setOptimalRoutes(routes)  │
              │  setAllRoutes(all_routes)  │
              └────────────┬───────────────┘
                           │
                           ▼
              ┌────────────────────────────┐
              │  Re-render Index.tsx       │
              │  Trigger useEffect/useMemo │
              └────────────┬───────────────┘
                           │
                           ▼
              ┌────────────────────────────┐
              │  Render Route Cards        │
              │  <RouteCard /> x 15        │
              └────────────┬───────────────┘
                           │
                           ▼
        1️⃣1️⃣ USER SEES  │
           RESULTS         │
           ┌──────────────────────────┐
           │ Rajdhani Express         │
           │ 09:00 → 09:30 (+1 day)   │
           │ 1440 km | 24h 30m        │
           │ ₹1,500 - ₹3,500          │
           │ [BOOK] [DETAILS]         │
           │                          │
           │ Shatabdi Express         │
           │ 15:00 → 16:00 (+1 day)   │
           │ 1440 km | 18h 00m        │
           │ ₹2,500 - ₹5,000          │
           │ [BOOK] [DETAILS]         │
           │ ... (13 more)             │
           └──────────────────────────┘
                           │
                           ▼
        1️⃣2️⃣ USER CLICKS  │
           "BOOK"          │
                           ▼
              ┌────────────────────────┐
              │  Route Card onClick    │
              │  openBookingFlow()      │
              └────────────┬───────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  BookingFlowModal      │
              │  Shows:                │
              │  ├─ Passenger details  │
              │  ├─ Seat selection     │
              │  ├─ Coach preference   │
              │  └─ Payment method     │
              └────────────┬───────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  Seat Selection UI     │
              │  (Interactive)         │
              │  Shows available seats │
              │  User selects seats    │
              └────────────┬───────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  Passenger Info Form   │
              │  Enter: Name, Age,     │
              │         Gender,        │
              │         Concession     │
              └────────────┬───────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  Confirm Booking       │
              │  POST /api/bookings/   │
              │  confirm               │
              └────────────┬───────────┘
                           │
        BOOKING REQUEST    │
        {                  │
          journey_id,      │
          passengers: [...],
          coach_type,      │
          payment_method   │
        }                  │
                           │
        ═════════════════════════════════════════I N T E R N E T════════════════════════════════════════════════════════
                           │
                           ▼
        1️⃣3️⃣ BACKEND      │
           BOOKING FLOW    │
           ├─ Allocate Seats
           ├─ Generate PNR
           ├─ Create Booking
           ├─ Process Payment
           ├─ Issue Ticket
           └─ Send Confirmation
                           │
        1️⃣4️⃣ PNR        │
           GENERATED      │
           (PNR: 2025025001234)
                           │
                           ▼
              ┌────────────────────────┐
              │  Booking Confirmed     │
              │  Return PNR + Ticket   │
              └────────────┬───────────┘
                           │
        ═════════════════════════════════════════I N T E R N E T════════════════════════════════════════════════════════
                           │
                           ▼
              ┌────────────────────────┐
              │  Ticket Page           │
              │  /ticket/:bookingId    │
              └────────────┬───────────┘
                           │
                           ▼
        1️⃣5️⃣ USER SEES  │
           TICKET         │
           ┌──────────────────────────┐
           │ PNR: 2025025001234       │
           │ Date: 2025-02-20         │
           │ Rajdhani Express #12002  │
           │ Mumbai Central → New Delhi
           │ 09:00 → 09:30 (+1 day)   │
           │ Coach: A, Seats: 01-02   │
           │ Total Fare: ₹4,533       │
           │ Status: Confirmed        │
           │                          │
           │ [DOWNLOAD PDF]           │
           │ [SHARE] [SCREENSHOT]     │
           └──────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     BOOKING COMPLETE                              │
│              User can now board the train with PNR                 │
└─────────────────────────────────────────────────────────────────────┘

```

---

# 10. EXECUTION TIMELINE & PERFORMANCE

```
QUERY EXECUTION TIMELINE:
┌────────────────────────────────────────────────────────────────┐
│  COMPONENT                              │ TIME (ms)            │
├────────────────────────────────────────────────────────────────┤
│ 1️⃣  Frontend Validation                │ 5-10 ms              │
│ 2️⃣  Network Latency (HTTP)             │ 20-50 ms             │
│ 3️⃣  Input Validation (Backend)         │ 2-5 ms               │
│ 4️⃣  Station Resolution (Fuzzy Match)   │ 10-30 ms             │
│ 5️⃣  Load GTFS Graph (First time)       │ 100-500 ms           │
│      (Cached after: 0ms)                │                      │
│ 6️⃣  RAPTOR Algorithm                   │ 50-200 ms            │
│      - Direct routes (0 transfers)      │ 10-30 ms             │
│      - 1-transfer routes                │ 20-80 ms             │
│      - 2-transfer routes                │ 20-80 ms             │
│      - Scoring & ranking                │ 5-15 ms              │
│ 7️⃣  Seat Availability Query             │ 5-15 ms              │
│ 8️⃣  Fare Calculation                   │ 10-20 ms             │
│ 9️⃣  Response Serialization             │ 5-10 ms              │
│ 🔟  Network Latency (Response)         │ 20-50 ms             │
│ ─────────────────────────────────────   │ ───────────          │
│ TOTAL (Cold start)                      │ 200-400 ms           │
│ TOTAL (Warm start, cached)              │ 150-250 ms           │
│ TOTAL (With Redis cache hit)            │ 50-100 ms            │
└────────────────────────────────────────────────────────────────┘

TARGET PERFORMANCE:
├─ P50 (50th percentile):  < 200ms
├─ P95 (95th percentile):  < 500ms
├─ P99 (99th percentile):  < 1000ms
└─ Throughput: 10K+ req/sec

OPTIMIZATION TECHNIQUES:
├─ In-memory graph caching (GTFS data)
├─ Startup graph preloading
├─ Connection pooling (10 connections)
├─ Redis result caching (1 hour TTL)
├─ Parallel processing (ThreadPoolExecutor)
├─ Database query optimization (Indexes, trigram search)
├─ Pagination (limit results returned)
└─ Progressive loading (stream results to UI)
```

---

# 11. VALIDATION & ERROR HANDLING

```
VALIDATION LAYERS:

┌─ FRONTEND VALIDATION (src/pages/Index.tsx)
│  ├─ Source/destination not empty
│  ├─ Date is valid YYYY-MM-DD
│  ├─ Date >= today
│  ├─ Budget within valid values
│  └─ Display error toast if failed

├─ API LAYER VALIDATION (backend/api/search.py)
│  ├─ SearchRequestValidator class
│  ├─ Check all required fields present
│  ├─ Validate format & constraints
│  ├─ Return HTTP 400 if validation fails
│  └─ Log validation error

├─ DATABASE LAYER VALIDATION
│  ├─ Station exists in DB
│  ├─ Date within calendar range
│  ├─ Foreign key constraints
│  └─ Return empty results if no data

└─ BUSINESS LOGIC VALIDATION
   ├─ Booking date within window (60 days)
   ├─ Seats available in selected coach
   ├─ Transfer times feasible
   ├─ No duplicate PNRs
   └─ Payment processing succeeds

ERROR HANDLING:

❌ Station Not Found
   Error Code: 404
   Message: "Could not find station: 'INVALID'. Please check spelling."
   Fixed by: User enters valid station, autocomplete suggests alternatives

❌ Invalid Date Format
   Error Code: 400
   Message: "Invalid date format. Use YYYY-MM-DD."
   Fixed by: User selects date from calendar picker

❌ Date in Past
   Error Code: 400
   Message: "Travel date must be today or in the future."
   Fixed by: User selects future date

❌ No Routes Found
   Error Code: 200 (Empty results)
   Message: "No routes available for selected criteria."
   Display: Empty state with suggestions to modify filters

❌ Database Connection Error
   Error Code: 500
   Message: "Database connection failed. Try again later."
   Action: Automatic retry with exponential backoff

❌ Seats Unavailable
   Error Code: 400
   Message: "Selected seats no longer available. Please choose others."
   Action: Refresh available seats list

❌ Payment Failed
   Error Code: 402
   Message: "Payment processing failed. Please try again."
   Action: Retry payment or use different payment method

❌ Rate Limited
   Error Code: 429
   Message: "Too many requests. Please slow down (max 5/minute)."
   Action: Wait and retry after timeout
```

---

# CONCLUSION

## COMPLETE FLOW SUMMARY:

```
USER QUERY (Mumbai → Delhi)
         │
         ├─ Frontend validation
         ├─ API transmission (HTTP POST)
         │
         ├─ Backend receives request
         ├─ Input validation
         ├─ Station resolution (fuzzy match)
         │
         ├─ Load GTFS data into memory
         ├─ Run RAPTOR algorithm on graph
         │  ├─ Direct routes
         │  ├─ Transfer routes
         │  └─ Multi-objective scoring
         │
         ├─ Get seat availability
         ├─ Calculate fares
         ├─ Reconstruct journey details
         │
         ├─ Serialize to JSON
         ├─ Return HTTP 200 response
         │
         ├─ Frontend receives & processes
         ├─ Parse JSON response
         ├─ Update React state
         ├─ Re-render UI with RouteCards
         │
         └─ USER SEES RESULTS (< 300ms)
            ┌────────────────────┐
            │ 15 Route Options   │
            │ Sorted by Duration │
            │ With pricing       │
            │ [BOOK] buttons     │
            └────────────────────┘
```

---

This complete workflow shows every file, function, and database interaction from the moment a user types "Mumbai" until they see route results on their screen. Print this document for reference during development, debugging, or system maintenance.

**Total Files Involved: 50+ backend files + 30+ frontend components**
**Total Lines of Code: 50,000+ LOC**
**Key Algorithms: RAPTOR (Route search), Dijkstra (Transfer optimization), Multi-objective scoring**

