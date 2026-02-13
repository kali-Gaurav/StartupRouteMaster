# Database Architecture Diagram

## System Overview (Mermaid Diagram)

```mermaid
graph TB
    subgraph External["📦 External Data (SQLite)"]
        SQLite["<b>railway_manager01.db</b><br/>SQLite Database"]
        StationM["stations_master<br/>~1000 stations"]
        TrainM["trains_master<br/>All registered trains"]
        TrainR["train_routes<br/>Train path definitions"]
        TrainS["train_schedule<br/>Departure/arrival times"]
        TrainF["train_fares<br/>Cost information"]
        TrainRD["train_running_days<br/>Operating schedule"]
        
        SQLite --> StationM
        SQLite --> TrainM
        SQLite --> TrainR
        SQLite --> TrainS
        SQLite --> TrainF
        SQLite --> TrainRD
    end

    subgraph LocalBackup["🖥️ Workspace Backup (SQLite)"]
        LocalDB["<b>railway_manager.db</b><br/>Local copy"]
        CopyScript["copy_tables.py<br/>(Copies data locally)"]
    end

    subgraph App["☁️ Application Database (PostgreSQL/Supabase)"]
        Supabase["<b>Supabase PostgreSQL</b>"]
        
        Stations["stations<br/>🔴 STATUS: may be empty"]
        Segments["segments<br/>🟡 STATUS: test data only?"]
        Routes["routes<br/>✅ populated via API"]
        Bookings["bookings<br/>✅ user transactions"]
        Payments["payments<br/>✅ razorpay data"]
        
        Supabase --> Stations
        Supabase --> Segments
        Supabase --> Routes
        Supabase --> Bookings
        Supabase --> Payments
    end

    subgraph API["🔧 Application Layer (FastAPI)"]
        RouteEngine["RouteEngine<br/>(route_engine.py)"]
        BookingService["BookingService<br/>(booking_service.py)"]
        SearchAPI["/api/search endpoint<br/>(search.py)"]
    end

    subgraph Frontend["🎨 Frontend (React)"]
        SearchUI["Search Form"]
        ResultsUI["Results Display"]
        BookingUI["Booking Flow"]
    end

    %% Data Flow
    External -->|copy_tables.py| LocalBackup
    LocalBackup -->|❌ NO ETL| App
    
    App -->|Queries segments| RouteEngine
    App -->|Queries stations| RouteEngine
    
    RouteEngine -->|Results + segments JSON| BookingService
    BookingService -->|Insert into routes| Routes
    BookingService -->|Insert into bookings| Bookings
    
    Frontend -->|POST /api/search| SearchAPI
    SearchAPI -->|Uses| RouteEngine
    SearchAPI -->|Caches in| Routes
    SearchAPI -->|Returns| Frontend
    
    Frontend -->|POST /api/payments| Payments
    Payments -->|References| Routes
    Bookings -->|References| Routes

    style External fill:#ffeeee
    style LocalBackup fill:#fff0ee
    style App fill:#e8f4f8
    style API fill:#f0f8ff
    style Frontend fill:#f0fff0
    style RouteEngine fill:#fffacd
    style Segments fill:#ffcccc
    style Stations fill:#ffcccc
```

---

## Current Data Flow (What Happens Now) 

```mermaid
sequenceDiagram
    participant User as Frontend User
    participant API as FastAPI
    participant RE as RouteEngine
    participant DB as Supabase DB
    participant Cache as CacheService

    User->>API: POST /api/search<br/>source, dest, date, budget
    
    API->>Cache: Check cache key
    alt Cache Hit
        Cache-->>API: Return cached routes
        API-->>User: Return results
    else Cache Miss
        API->>RE: search_routes(...)
        
        RE->>DB: Query stations by name
        DB-->>RE: station objects
        
        RE->>DB: Query segments (filtered)
        DB-->>RE: segment list
        
        Note over RE: Build graph + run Dijkstra
        RE->>RE: _construct_route() x N paths
        
        Note over RE: Create route dicts with<br/>segments array as JSONB
        RE-->>API: List[route_dict]
        
        API->>DB: save_route() for each result
        DB-->>API: route IDs
        
        API->>Cache: Store routes with key
        API-->>User: Return results
    end

    Note over User,DB: Later: User selects a route
    User->>API: POST /api/payments/create-order<br/>route_id, user details
    
    API->>DB: Query route (with segments JSON)
    DB-->>API: route object
    
    API->>DB: Create payment record
    API->>DB: Create booking record
    API-->>User: Payment URL
```

---

## Missing ETL Pipeline (What Should Exist)

```mermaid
graph LR
    subgraph ETL["❌ MISSING: ETL Pipeline"]
        Read["Read SQLite<br/>train_schedule<br/>train_routes<br/>train_fares"]
        
        Transform["Transform<br/>Join tables<br/>Build Segment objects<br/>Parse times/costs"]
        
        Load["Load into PostgreSQL<br/>INSERT/UPDATE segments<br/>Update stations"]
        
        Schedule["Schedule Daily/Hourly<br/>via Cloud Function<br/>or Cron Job"]
        
        Read --> Transform
        Transform --> Load
        Load --> Schedule
    end
    
    SQLiteSrc["railway_manager.db<br/>(SQLite)"]
    SupabaseDest["Supabase<br/>(PostgreSQL)"]
    
    SQLiteSrc -->|Should call ETL| ETL
    ETL -->|Should populate| SupabaseDest
    
    style ETL fill:#ffcccc
    style Read fill:#ffe6e6
    style Transform fill:#ffe6e6
    style Load fill:#ffe6e6
    style Schedule fill:#ffb3b3
```

---

## Data Model: Segments Table (PostgreSQL)

```mermaid
erDiagram
    STATIONS ||--o{ SEGMENTS : "source_station_id"
    STATIONS ||--o{ SEGMENTS : "dest_station_id"
    SEGMENTS ||--o{ ROUTES : "contained_in_segments_array"
    ROUTES ||--o{ BOOKINGS : "has"
    BOOKINGS ||--o{ PAYMENTS : "has"

    STATIONS {
        uuid id PK
        string name
        string city
        float latitude
        float longitude
        timestamp created_at
    }

    SEGMENTS {
        uuid id PK
        uuid source_station_id FK
        uuid dest_station_id FK
        string transport_mode
        string departure_time "HH:MM"
        string arrival_time "HH:MM"
        int duration_minutes
        float cost
        string operator
        string operating_days "1111111"
        timestamp created_at
    }

    ROUTES {
        uuid id PK
        string source
        string destination
        jsonb segments "Array of segment objects"
        string total_duration
        float total_cost
        string budget_category
        int num_transfers
        timestamp created_at
    }

    BOOKINGS {
        uuid id PK
        string user_name
        string user_email
        string user_phone
        uuid route_id FK
        string travel_date
        string payment_status
        float amount_paid
        timestamp created_at
    }

    PAYMENTS {
        uuid id PK
        uuid booking_id FK
        string razorpay_order_id
        string razorpay_payment_id
        string status
        float amount
        timestamp created_at
    }
```

---

## Segments Formation: SQLite → PostgreSQL Transformation

```mermaid
graph TB
    subgraph SQLite["SQLite: railway_manager.db"]
        TR["train_routes<br/>(source, dest, distance)"]
        TS["train_schedule<br/>(train_id, dep_time, arr_time)"]
        TF["train_fares<br/>(train_id, cost, class)"]
        TM["trains_master<br/>(train_id, operator)"]
        RD["train_running_days<br/>(mon, tue, ... sun)"]
    end

    subgraph Transform["🔄 TRANSFORM"]
        Join["1. JOIN train_routes<br/>+ train_schedule<br/>+ train_fares<br/>+ trains_master"]
        Parse["2. PARSE times<br/>Calculate duration<br/>Build bitmask"]
        Build["3. BUILD Segment<br/>object"]
    end

    subgraph PG["PostgreSQL: segments"]
        Seg["id, source_id, dest_id<br/>transport_mode, departure_time<br/>arrival_time, duration_minutes<br/>cost, operator, operating_days"]
    end

    TR --> Join
    TS --> Join
    TF --> Join
    TM --> Join
    RD --> Join
    
    Join --> Parse
    Parse --> Build
    Build --> Seg

    style Join fill:#fffacd
    style Parse fill:#fffacd
    style Build fill:#fffacd
```

---

## High-Level System Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                      USER (Frontend)                           │
│         React App (TypeScript + Vite)                          │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 │ HTTP Requests
                 │
┌────────────────▼─────────────────────────────────────────────┐
│              FASTAPI APPLICATION LAYER                        │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ /api/search     ← Search routes                      │    │
│  │ /api/route/{id} ← Get route details                 │    │
│  │ /api/payments   ← Create orders & verify payments    │    │
│  │ /api/bookings   ← Manage user bookings               │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  Services:                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ RouteEngine  │  │BookingService│  │PaymentService│       │
│  │ (search)     │  │(persistence) │  │(razorpay)    │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 │ SQL Queries (ORM: SQLAlchemy)
                 │
┌────────────────▼─────────────────────────────────────────────┐
│         SUPABASE POSTGRESQL (Production DB)                  │
│                                                               │
│  ┌─────────────┐ ┌──────────┐ ┌────────┐ ┌──────────┐       │
│  │  stations   │ │ segments │ │ routes │ │ bookings │       │
│  └─────────────┘ └──────────┘ └────────┘ └──────────┘       │
│                                                               │
│  ❌ STATUS: segments may be empty!                           │
│  ❌ STATUS: Need ETL to populate from SQLite!               │
└────────────────────────────────────────────────────────────────┘
                 ▲
                 │ Should populate via ETL
                 │ (CURRENTLY MISSING)
                 │
┌────────────────┴─────────────────────────────────────────────┐
│    RAILWAY_MANAGER.DB (SQLite - Master Data)                 │
│                                                               │
│  ┌────────────────┐ ┌──────────────┐ ┌──────────┐           │
│  │stations_master │ │ trains_master│ │train_*   │           │
│  │(~1000 records) │ │ train_routes │ │ tables   │           │
│  │                │ │train_schedule│ │          │           │
│  │                │ │ train_fares  │ │          │           │
│  └────────────────┘ └──────────────┘ └──────────┘           │
│                                                               │
│  ✅ Contains all railway data                               │
│  ✅ Cannot be modified by users                             │
│  ❌ Not synced to Supabase!                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## Example: How a Route is Created & Retrieved

```mermaid
sequenceDiagram
    actor User
    participant Frontend
    participant API as /api/search
    participant Engine as RouteEngine
    participant DB as Supabase<br/>segments table
    participant DB2 as Supabase<br/>routes table
    participant Booking as BookingService

    User->>Frontend: "Search Delhi → Mumbai, 15 Feb"
    Frontend->>API: POST /api/search
    
    API->>Engine: search_routes(source, dest, date)
    
    Engine->>DB: SELECT * FROM segments WHERE<br/>source_station_id IN (...)<br/>AND operating_days matches date<br/>AND duration <= 720
    DB-->>Engine: 200 segments
    
    Note over Engine: Build TimeExpandedGraph<br/>from segments
    
    Engine->>Engine: dijkstra_search() finds paths<br/>Path 1: A → B (8h, ₹1200)<br/>Path 2: A → C → B (14h, ₹900)
    
    Engine->>Engine: _construct_route(path1)<br/>segments=[{mode, from, to, cost, ...}]
    
    Note over Engine: Return routes with<br/>JSONB segments array
    Engine-->>API: [{<br/>id: UUID,<br/>segments: [obj, obj],<br/>total_cost: 1200,<br/>...<br/>}]
    
    API->>Booking: save_route(segments=..., cost=..., ...)
    Booking->>DB2: INSERT INTO routes<br/>(segments, total_cost, ...)
    DB2-->>Booking: route_id
    
    Booking-->>API: route_id
    API-->>Frontend: [{route_id, cost, duration, ...}]
    
    Frontend-->>User: Display results
    
    Note over User,Frontend: User clicks "Book This Route"
    
    User->>Frontend: Select route, enter details
    Frontend->>API: POST /api/payments/create-order<br/>route_id, user_email, ...
    
    API->>DB2: SELECT * FROM routes WHERE id=?
    DB2-->>API: route object with segments JSON
    
    API->>API: Create Razorpay order
    API->>Booking: create_booking(route_id, user_*)
    Booking->>DB2: INSERT INTO bookings(...route_id...)
    
    API-->>Frontend: payment_url
    Frontend-->>User: Redirect to payment
```

---

## The Critical Problem ⚠️

The **Segments Table is Likely Empty or Incomplete** because:

❌ No ETL process reads from `railway_manager.db`
❌ Tests create mock segments, but production DB doesn't have them
❌ Routes can't be found → API returns empty results

**Current Code Flow:**
```
1. RouteEngine queries segments table
2. Segments table is empty
3. Graph has no edges
4. Dijkstra finds no paths
5. Routes = []
6. User sees "No routes found"
```

**What Should Happen:**
```
1. Daily ETL: Read train_schedule from SQLite
2. Transform to Segment objects
3. INSERT into Supabase segments
4. RouteEngine queries populated segments
5. Finds exact trains matching search
6. Returns real routes with actual costs
```

---

## Solution: Create the ETL Bridge

**File to create:** `backend/etl/populate_segments_from_sqlite.py`

```python
"""
ETL: SQLite railway_manager.db → Supabase segments table

Flow:
  1. Read train_schedule + train_routes + train_fares from SQLite
  2. For each combination:
     - Parse departure/arrival times
     - Calculate duration
     - Get cost
     - Determine operating days bitmask
  3. Create Segment object
  4. Upsert into Supabase (INSERT OR UPDATE)
  5. Log results

Usage:
  python -m backend.etl.populate_segments_from_sqlite
"""
```

This one script fixes the entire architecture!

