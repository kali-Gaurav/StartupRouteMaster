# ARCHITECTURE V2: Domain-Driven Design + Platform Layer

**Status**: Architecture Design (Before Implementation)
**Pattern**: Domain-Driven Design (DDD) + Platform Infrastructure Layer
**Reference Systems**: IRCTC, Uber, Airline Booking Systems
**Date**: 2026-02-20

---

## 🎯 CORE PRINCIPLE

```
Business Domains + Shared Platform + ML Intelligence + APIs = Production System

Search → Inventory → Booking → Payment → Ticket
(Maps directly to domain boundaries)
```

**Golden Rule**: If code could go in multiple places, it belongs in **platform/** (shared infrastructure), not duplicated in domains.

---

## 📐 ARCHITECTURE LAYERS

```
┌─────────────────────────────────────────────────────┐
│                   API LAYER                         │
│      (Routes, Controllers, FastAPI Routers)         │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────┐
│              DOMAIN LAYER (Business)                │
│  routing/ booking/ inventory/ pricing/              │
│  user/ station/ payment/ verification/              │
│                                                     │
│  ✓ This is where the business logic lives          │
│  ✓ Each domain owns its data and behavior          │
│  ✓ NO DUPLICATES allowed                           │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────┐
│         PLATFORM LAYER (Shared Infrastructure)     │
│  cache/ graph/ events/ monitoring/                  │
│  integrations/ security/                            │
│                                                     │
│  ✓ Used by all domains                             │
│  ✓ Technology layer (Redis, Kafka, gRPC)           │
│  ✓ Cross-cutting concerns                          │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────┐
│        INTELLIGENCE LAYER (ML + Prediction)        │
│  models/ training/ prediction/ registry/            │
│                                                     │
│  ✓ Separate from domains to avoid coupling         │
│  ✓ Uses domains as data sources                    │
│  ✓ No domain code depends on this                  │
└─────────────────────────────────────────────────────┘
```

---

## 📦 DIRECTORY STRUCTURE

```
backend/
│
├── ========== ROOT (4-6 production entry points) ==========
├── app.py                          Main FastAPI app (import all routers)
├── config.py                       Environment configuration
├── database.py                     session_local, engine factory
├── schemas.py                      Shared Pydantic models
├── dependencies.py                 FastAPI dependency injection
│
│
├── ========== API LAYER (Routes/Controllers) ==========
├── api/
│   ├── __init__.py
│   ├── search.py                   GET /api/search
│   ├── booking.py                  POST /api/booking
│   ├── payment.py                  POST /api/payment
│   ├── inventory.py                GET /api/inventory
│   ├── user.py                     GET/POST /api/user
│   ├── station.py                  GET /api/station
│   ├── admin.py                    Admin endpoints
│   ├── health.py                   GET /health (status checks)
│   ├── websockets.py               WebSocket connections
│   └── dependencies.py             Route dependencies
│
│
├── ========== DOMAINS (Business Logic) ==========
│
├── domains/
│   ├── __init__.py
│   │
│   │
│   ├── routing/                    ⭐ SEARCH ROUTING ENGINE
│   │   ├── __init__.py
│   │   ├── interfaces.py            (Abstract RouteFinder protocol)
│   │   ├── engine.py                Main RailwayRouteEngine (only one)
│   │   ├── raptor.py                RAPTOR algorithm implementation
│   │   ├── graph.py                 Graph data structures
│   │   ├── builder.py               Graph building from DB
│   │   ├── snapshot_manager.py       Memory snapshots
│   │   ├── hub.py                   Hub detection & optimization
│   │   ├── transfer_logic.py         Transfer analysis
│   │   ├── constraints.py           Route constraints
│   │   ├── data_structures.py       Domain models (Journey, Segment, etc.)
│   │   ├── frequency_aware_range.py Frequency analysis
│   │   ├── station_time_index.py    Station departure indexing
│   │   └── README.md
│   │
│   │
│   ├── booking/                    ⭐ BOOKING DOMAIN
│   │   ├── __init__.py
│   │   ├── interfaces.py            (Abstract Booker protocol)
│   │   ├── service.py               Main BookingService
│   │   ├── orchestrator.py          Booking workflow coordinator
│   │   ├── models.py                Booking data models
│   │   ├── validators.py            Booking validation rules
│   │   └── README.md
│   │
│   │
│   ├── inventory/                  ⭐ SEAT/CAPACITY MANAGEMENT
│   │   ├── __init__.py
│   │   ├── interfaces.py            (Abstract SeatAllocator protocol)
│   │   ├── seat_allocator.py        ONLY ONE seat allocation impl
│   │   ├── models.py                Seat/Inventory models
│   │   ├── availability_service.py  Real-time availability check
│   │   ├── analytics_consumer.py    Event consumption for updates
│   │   └── README.md
│   │
│   │
│   ├── pricing/                    ⭐ PRICING & YIELD MANAGEMENT
│   │   ├── __init__.py
│   │   ├── interfaces.py            (Abstract PricingEngine protocol)
│   │   ├── engine.py                ONLY ONE pricing impl
│   │   ├── models.py                Pricing data models
│   │   ├── yield_management.py      Dynamic pricing logic
│   │   ├── calculators.py           Fare calculation helpers
│   │   └── README.md
│   │
│   │
│   ├── user/                       ⭐ USER MANAGEMENT
│   │   ├── __init__.py
│   │   ├── service.py               User operations
│   │   ├── models.py                User data models
│   │   ├── validators.py            User validation
│   │   └── README.md
│   │
│   │
│   ├── station/                    ⭐ STATION DATA
│   │   ├── __init__.py
│   │   ├── service.py               Station operations
│   │   ├── models.py                Station data models
│   │   ├── departure_service.py     Station departure lookup
│   │   └── README.md
│   │
│   │
│   ├── payment/                    ⭐ PAYMENT PROCESSING
│   │   ├── __init__.py
│   │   ├── interfaces.py            (Abstract PaymentProcessor protocol)
│   │   ├── service.py               Payment operations
│   │   ├── gateway.py               Payment gateway integration
│   │   ├── models.py                Payment data models
│   │   └── README.md
│   │
│   │
│   └── verification/               ⭐ BOOKING VERIFICATION
│       ├── __init__.py
│       ├── service.py               Verification operations
│       ├── validators.py            Verification rules
│       ├── unlock_system.py         Unlock token generation
│       ├── models.py                Verification data models
│       └── README.md
│
│
├── ========== PLATFORM (Shared Infrastructure) ==========
│
├── platform/
│   ├── __init__.py
│   │
│   │
│   ├── cache/                      ⭐ CACHING LAYER
│   │   ├── __init__.py
│   │   ├── manager.py               Main CacheManager (single source)
│   │   ├── memory.py                In-memory cache (L1)
│   │   ├── redis.py                 Redis adapter (L2)
│   │   ├── warming.py               Cache warming strategies
│   │   ├── invalidation.py          Cache invalidation logic
│   │   └── README.md
│   │
│   │
│   ├── graph/                      ⭐ GRAPH INFRASTRUCTURE
│   │   ├── __init__.py
│   │   ├── mutation_engine.py       Real-time graph updates
│   │   ├── mutation_service.py      Mutation orchestration
│   │   ├── train_state_service.py   Train state tracking
│   │   └── README.md
│   │
│   │
│   ├── events/                     ⭐ EVENT STREAMING
│   │   ├── __init__.py
│   │   ├── producer.py              Publish events to Kafka
│   │   ├── consumer.py              Consume events (analytics)
│   │   ├── schemas.py               Event data models
│   │   └── README.md
│   │
│   │
│   ├── monitoring/                 ⭐ OBSERVABILITY
│   │   ├── __init__.py
│   │   ├── metrics.py               Prometheus metrics
│   │   ├── logger.py                Structured logging
│   │   ├── tracer.py                Distributed tracing
│   │   ├── performance_monitor.py   Performance tracking
│   │   └── README.md
│   │
│   │
│   ├── integrations/               ⭐ EXTERNAL SYSTEMS
│   │   ├── __init__.py
│   │   ├── routemaster_client.py    RouteMaster API integration
│   │   ├── live_api_connector.py    Live fares/delays/seats APIs
│   │   └── README.md
│   │
│   │
│   └── security/                   ⭐ AUTHENTICATION & AUTHORIZATION
│       ├── __init__.py
│       ├── jwt_handler.py           JWT token management
│       ├── validators.py            Schema & API security
│       ├── limiter.py               Rate limiting
│       └── README.md
│
│
├── ========== INTELLIGENCE (ML + Prediction) ==========
│
├── intelligence/
│   ├── __init__.py
│   │
│   │
│   ├── models/                     ⭐ ML MODELS
│   │   ├── __init__.py
│   │   ├── demand_predictor.py      Demand forecasting
│   │   ├── delay_predictor.py       Delay prediction
│   │   ├── ranking_model.py         Route ranking
│   │   ├── reliability_model.py     Reliability scoring
│   │   ├── baseline_models.py       Baseline heuristics
│   │   └── README.md
│   │
│   │
│   ├── training/                   ⭐ MODEL TRAINING
│   │   ├── __init__.py
│   │   ├── pipeline.py              Training orchestration
│   │   ├── data_collector.py        Training data collection
│   │   ├── evaluator.py             Model evaluation
│   │   └── README.md
│   │
│   │
│   ├── prediction/                 ⭐ INFERENCE
│   │   ├── __init__.py
│   │   ├── service.py               Prediction service
│   │   ├── feature_extractor.py     Feature engineering
│   │   ├── result_ranker.py         Result ranking
│   │   └── README.md
│   │
│   │
│   └── registry/                   ⭐ MODEL LIFECYCLE
│       ├── __init__.py
│       ├── manager.py               Model registry
│       ├── versioning.py            Version management
│       └── README.md
│
│
├── ========== WORKERS (Background Jobs) ==========
├── workers/
│   ├── __init__.py
│   ├── README.md
│   ├── seat_expiry_worker.py       Expire old seat locks
│   ├── delay_update_worker.py      Update delays from live APIs
│   ├── pricing_worker.py           Dynamic pricing updates
│   ├── analytics_worker.py         Process analytics events
│   └── health_check_worker.py      System health checks
│
│
├── ========== CORE INFRASTRUCTURE ==========
├── core/                           [EXISTING - KEEP]
│   ├── route_engine/ [Full routing system - validate against domains/routing/]
│   ├── validators/ [Validators by concern]
│   └── archive/
│
├── database/                       [EXISTING - ENHANCE]
│   ├── models.py                  [Consolidate models.py + seat_inventory_models.py]
│   ├── session.py
│   └── config.py
│
├── utils/                          [EXISTING - KEEP]
│   ├── validators.py
│   ├── time_utils.py
│   ├── graph_utils.py
│   ├── security.py
│   ├── limiter.py
│   ├── metrics.py
│   └── logger.py
│
│
├── ========== DATA PIPELINES & ETL ==========
├── pipelines/                      [EXISTING - KEEP]
├── etl/                            [EXISTING - KEEP]
│
│
├── ========== MICROSERVICES (FUTURE) ==========
├── microservices/                  [EXISTING - KEEP]
│
│
├── ========== TESTING ==========
├── tests/
│   ├── conftest.py
│   ├── unit/                       Unit tests by domain
│   ├── integration/                Multi-domain integration
│   ├── load/                       Load testing
│   └── fixtures/
│
│
├── ========== SCRIPTS & UTILITIES ==========
├── scripts/
│   ├── __init__.py
│   ├── README.md
│   ├── seed_stations.py           Data seeding
│   ├── inspect_railway_db.py      DB inspection
│   ├── audit_kafka_config.py      Kafka audit
│   ├── check_db.py                DB health check
│   │
│   ├── workers/
│   │   ├── search_worker.py
│   │   ├── payment_worker.py
│   │   └── start_analytics_consumer.py
│   │
│   └── ml/
│       ├── ml_data_collection.py
│       ├── ml_training_pipeline.py
│       ├── setup_ml_database.py
│       └── ml_staging_rollout.py
│
│
├── ========== ARCHIVED CODE ==========
├── archive/
│   ├── README.md
│   ├── offline_phase2_deprecated/
│   ├── route_engines_v1/           [Old route engines]
│   ├── seat_allocators_v1/         [Old seat allocators]
│   ├── pricing_engines_v1/         [Old pricing engines]
│   └── cache_managers_v1/          [Old cache managers]
│
│
├── ========== DOCUMENTATION ==========
├── docs/
├── examples/
│
│
└── ========== CONFIGURATION ==========
    ├── .env
    ├── requirements.txt
    ├── Dockerfile
    ├── alembic/
    ├── pytest.ini
    └── README.md
```

---

## 🎯 DOMAIN BOUNDARIES & OWNERSHIP

### 📍 **routing/** - Route Finding & Optimization
**Purpose**: Find optimal routes between two stations
**Owns**: Journey data, transfer logic, RAPTOR algorithm, graph structures
**Consumes**: Station data from stations/, user preferences from user/
**Provides**: Route search results
**Key Classes**:
- `RailwayRouteEngine` - Main entry point
- `Journey` - Route result data model
- `OptimizedRAPTOR` - Algorithm implementation

```python
# routing/interfaces.py
class RouteFinder(Protocol):
    async def find_routes(
        self,
        source_station_id: int,
        destination_station_id: int,
        departure_time: datetime,
        max_transfers: int = 3
    ) -> List[Journey]:
        """Find routes between stations."""
        ...
```

---

### 📍 **booking/** - Booking Management
**Purpose**: Create, manage, update, and cancel bookings
**Owns**: Booking workflow, orchestration, booking state
**Consumes**: Routes from routing/, inventory from inventory/, pricing from pricing/
**Provides**: Booking records, booking status
**Key Classes**:
- `BookingService` - Core booking operations
- `BookingOrchestrator` - Workflow coordination
- `Booking` - Data model

```python
# booking/interfaces.py
class Booker(Protocol):
    async def create_booking(
        self,
        journey: Journey,
        user_id: int,
        seats: List[str]
    ) -> Booking:
        """Create a booking."""
        ...
```

---

### 📍 **inventory/** - Seat & Capacity Management
**Purpose**: Track seat availability and allocate seats
**Owns**: Seat inventory, availability logic, capacity constraints
**Consumes**: Booking events from booking/
**Provides**: Available seats, seat locks
**Key Classes**:
- `SeatAllocator` - Allocate seats (ONLY ONE)
- `AvailabilityService` - Check real-time availability
- `Seat` - Data model

```python
# inventory/interfaces.py
class SeatAllocator(Protocol):
    async def allocate_seats(
        self,
        trip_id: int,
        requested_seats: int,
        user_id: int
    ) -> List[str]:
        """Allocate seats for a booking."""
        ...
```

---

### 📍 **pricing/** - Fares & Revenue Management
**Purpose**: Calculate fares and manage dynamic pricing
**Owns**: Pricing logic, yield management, fare rules
**Consumes**: Route segments from routing/, demand from intelligence/
**Provides**: Fare calculations, price points
**Key Classes**:
- `PricingEngine` - Calculate fares (ONLY ONE)
- `YieldManager` - Dynamic pricing logic
- `Fare` - Price data model

```python
# pricing/interfaces.py
class PricingEngine(Protocol):
    async def calculate_fare(
        self,
        segment: Segment,
        seat_class: str,
        demand_level: float
    ) -> float:
        """Calculate dynamic fare."""
        ...
```

---

### 📍 **user/** - User Management
**Purpose**: Store and manage user data
**Owns**: User profiles, preferences, authentication
**Consumes**: Nothing domain-specific
**Provides**: User data for other domains
**Key Classes**:
- `UserService` - User operations
- `User` - Data model

---

### 📍 **station/** - Station Data
**Purpose**: Maintain station information and schedules
**Owns**: Station data, departure schedules, routes/lines
**Consumes**: Nothing
**Provides**: Station info for routing/
**Key Classes**:
- `StationService` - Station operations
- `Station` - Data model

---

### 📍 **payment/** - Payment Processing
**Purpose**: Handle payment transactions
**Owns**: Payment workflow, gateway integration, transaction state
**Consumes**: Booking from booking/
**Provides**: Payment status, transaction records
**Key Classes**:
- `PaymentService` - Payment operations
- `PaymentGateway` - Gateway abstraction
- `Transaction` - Data model

```python
# payment/interfaces.py
class PaymentProcessor(Protocol):
    async def process_payment(
        self,
        booking_id: int,
        amount: float,
        method: str
    ) -> PaymentResult:
        """Process payment for booking."""
        ...
```

---

### 📍 **verification/** - Booking Verification
**Purpose**: Verify bookings before finalization
**Owns**: Verification rules, unlock tokens, confirmation workflow
**Consumes**: Bookings from booking/, routes from routing/
**Provides**: Verification status, unlock details
**Key Classes**:
- `VerificationService` - Verification operations
- `UnlockSystem` - Token generation

---

## 🏗️ PLATFORM LAYER - SHARED INFRASTRUCTURE

### 💾 **platform/cache/** - Caching
**Purpose**: Multi-layer caching for performance
**Responsible For**: Memory cache (L1) + Redis (L2)
**Used By**: All domains (especially routing for graphs)
**Single Source**: `CacheManager` - ONLY ONE implementation

```python
# platform/cache/manager.py
class CacheManager:
    async def get(self, key: str) -> Optional[Any]:
        """Try L1 first, then L2 Redis."""

    async def set(self, key: str, value: Any, ttl: int):
        """Write to both L1 and L2."""
```

---

### 📊 **platform/graph/** - Real-Time Graph Updates
**Purpose**: Handle live train delays and cancellations
**Responsible For**: Graph mutations, Copy-on-Write overlays
**Used By**: routing/
**Classes**:
- `MutationEngine` - Apply real-time changes
- `RealtimeOverlay` - COW snapshot for delays

---

### 📨 **platform/events/** - Event Streaming
**Purpose**: Publish/consume events for async processing
**Responsible For**: Kafka producers & consumers
**Used By**: All domains for audit & analytics
**Classes**:
- `EventProducer` - Publish events
- `EventConsumer` - Consume events

---

### 📈 **platform/monitoring/** - Observability
**Purpose**: Metrics, logging, tracing
**Responsible For**: Prometheus, structured logs, distributed traces
**Used By**: All domains
**Classes**:
- `MetricsCollector` - Prometheus metrics
- `StructuredLogger` - JSON logging
- `DistributedTracer` - Request tracing

---

### 🔗 **platform/integrations/** - External APIs
**Purpose**: Connect to RouteMaster, live data APIs
**Responsible For**: API clients, retry logic, circuit breakers
**Used By**: domains/ that need external data
**Classes**:
- `RouteMasterClient` - RouteMaster integration
- `LiveAPIConnector` - Fares/delays/seats APIs

---

### 🔐 **platform/security/** - Security
**Purpose**: Auth, validation, rate limiting
**Responsible For**: JWT, schema validation, rate limits
**Used By**: api/ layer
**Classes**:
- `JWTHandler` - Token management
- `SchemaValidator` - Input validation
- `RateLimiter` - Request throttling

---

## 🤖 INTELLIGENCE LAYER - ML & PREDICTION

### 🧠 **intelligence/models/** - ML Models
**Purpose**: Store all ML model implementations
**Contains**: Demand, delay, ranking, reliability models
**Used By**: Domains via intelligence/prediction/
**Classes**:
- `DemandPredictor` - Predict demand
- `DelayPredictor` - Predict delays
- `RankingModel` - Rank routes
- `ReliabilityModel` - Reliability scoring

---

### 🎓 **intelligence/training/** - Model Training
**Purpose**: Continuous model training
**Responsible For**: Data collection, training orchestration, evaluation
**Classes**:
- `TrainingPipeline` - Training workflow
- `DataCollector` - Gather training data
- `ModelEvaluator` - Test models

---

### 🔮 **intelligence/prediction/** - Inference
**Purpose**: Make predictions at runtime
**Responsible For**: Inference service, feature extraction, result ranking
**Used By**: Domains via dependency injection
**Classes**:
- `PredictionService` - Make predictions
- `FeatureExtractor` - Prepare features
- `ResultRanker` - Rank results

---

### 📚 **intelligence/registry/** - Model Lifecycle
**Purpose**: Version, register, and manage models
**Responsible For**: Model versioning, A/B testing setup
**Used By**: intelligence/prediction/, intelligence/training/
**Classes**:
- `ModelRegistry` - Track models
- `VersionManager` - Handle versions

---

## 🔄 DATA FLOW EXAMPLE: Search → Booking → Payment

```
1. API Layer (api/search.py)
   └─> receives GET /api/search?from=A&to=B&date=X

2. Controller calls domains/routing/
   └─> RouteFinder.find_routes()
       ├─> Uses domains/station/ for station data
       ├─> Uses platform/cache/ for graph snapshots
       ├─> Uses platform/graph/ for real-time overlays
       ├─> Uses intelligence/prediction/ for demand
       └─> Returns List[Journey]

3. Controller returns Routes to User
   └─> JSON with fares from domains/pricing/

4. User Selects Route + Books (POST /api/booking)

5. API Controller calls domains/booking/
   └─> BookingService.create_booking()
       ├─> Calls domains/inventory/ to allocate seats
       ├─> Calls domains/pricing/ to confirm fare
       ├─> Locks seats (seat_expiry_worker monitors this)
       └─> Returns Booking

6. API Controller calls domains/payment/
   └─> PaymentService.process_payment()
       ├─> Calls platform/integrations/ for payment gateway
       ├─> Publishes event via platform/events/
       └─> Returns PaymentResult

7. Background Workers (workers/)
   └─> Consume events from platform/events/
       ├─> Unlock seats after expiry
       ├─> Update pricing
       ├─> Send notifications
       └─> Collect analytics

8. Intelligence Layer (workers can trigger training)
   └─> intelligence/training/ collects data
       └─> intelligence/prediction/ improves models
```

---

## 🚫 DEPENDENCY RULES (CRITICAL)

### ✅ ALLOWED:
```
api/ → domains/
domains/ → platform/
domains/ → other domains/ (carefully - single direction)
platform/ → platform/ (intentionally shared)
intelligence/ → platform/
workers/ → domains/, platform/, intelligence/
```

### ❌ FORBIDDEN:
```
NO: domains/ → api/ (backward call)
NO: platform/ → domains/ (platforms don't know about business)
NO: intelligence/ → domains/ (except via dependency injection)
NO: database/ → intelligence/ (no direct ML deps)
NO: Circular imports between domains (A→B→A)
```

---

## 📋 CONSOLIDATION PRIORITY ORDER

### Phase 1 - Core Engines (These affect everything)

**Priority 1: Route Finding**
- Current: 4 implementations
  - `route_engine.py` (at root) - legacy
  - `hybrid_search_service.py` (services/) - primary
  - `advanced_route_engine.py` (services/) - duplicate
  - `multi_modal_route_engine.py` (services/) - duplicate

**Action**:
- Keep: `hybrid_search_service.py` (best implementation)
- Archive: 3 others
- Move to: `domains/routing/engine.py`
- Create: `domains/routing/interfaces.py` with RouteFinder protocol

**Priority 2: Seat Allocation**
- Current: 3 implementations
  - `seat_allocation.py` (services/)
  - `advanced_seat_allocation_engine.py` (services/)
  - `smart_seat_allocation.py` (services/)

**Action**:
- Review all 3, keep best
- Archive: 2 others
- Move to: `domains/inventory/seat_allocator.py`
- Create: `domains/inventory/interfaces.py` with SeatAllocator protocol

**Priority 3: Pricing Engine**
- Current: 3 implementations
  - `price_calculation_service.py` (services/)
  - `enhanced_pricing_service.py` (services/)
  - `yield_management_engine.py` (services/)

**Action**:
- Keep: best implementation (likely enhanced_pricing_service.py)
- Archive: 2 others
- Move to: `domains/pricing/engine.py`
- Create: `domains/pricing/interfaces.py` with PricingEngine protocol

**Priority 4: Cache Manager**
- Current: 3 implementations
  - `cache_service.py` (services/)
  - `cache_warming_service.py` (services/)
  - `multi_layer_cache.py` (services/)

**Action**:
- Keep: `cache_service.py` as main
- Keep: `cache_warming_service.py` as warming strategy
- Archive: `multi_layer_cache.py`
- Move to: `platform/cache/`

### Phase 2 - Remaining Services

Move by domain ownership:
- `booking_service.py` → `domains/booking/`
- `availability_service.py` → `domains/inventory/`
- `station_service.py` → `domains/station/`
- `payment_service.py` → `domains/payment/`
- `verification_engine.py` → `domains/verification/`
- `user_service.py` → `domains/user/`
- `unlock_service.py` → `domains/verification/unlock_system.py`

### Phase 3 - Graph & Mutations

Move to platform:
- `graph_mutation_engine.py` → `platform/graph/`
- `graph_mutation_service.py` → `platform/graph/`
- `train_state_service.py` → `platform/graph/`

### Phase 4 - Intelligence & ML

Move to intelligence:
- All ML files from root and services/ → `intelligence/models/`
- Training files → `intelligence/training/`
- Predictors → `intelligence/models/` with registry

### Phase 5 - Workers & Scripts

Move background jobs:
- `search_worker.py` → `workers/`
- `payment_worker.py` → `workers/`
- `seat_expiry_worker.py` → create in `workers/`
- `delay_update_worker.py` → create in `workers/`

Move scripts:
- All setup/seed/audit files → `scripts/`

---

## 🔍 INTERFACE PROTOCOL EXAMPLES

Before moving files, define interfaces to prevent tight coupling:

### Example 1: Routing Interface
```python
# domains/routing/interfaces.py
from typing import Protocol, List
from datetime import datetime

class RouteFinder(Protocol):
    async def find_routes(
        self,
        source_station_id: int,
        destination_station_id: int,
        departure_time: datetime,
        max_transfers: int = 3
    ) -> List[Journey]:
        """Find optimal routes between stations."""
        ...
```

### Example 2: Seat Allocator Interface
```python
# domains/inventory/interfaces.py
from typing import Protocol, List

class SeatAllocator(Protocol):
    async def allocate_seats(
        self,
        trip_id: int,
        requested_seats: int,
        seat_class: str = "GENERAL"
    ) -> List[str]:
        """Allocate specific seats."""
        ...

    async def release_seats(
        self,
        trip_id: int,
        seat_codes: List[str]
    ):
        """Release allocated seats."""
        ...
```

### Example 3: Pricing Interface
```python
# domains/pricing/interfaces.py
from typing import Protocol

class PricingEngine(Protocol):
    async def calculate_fare(
        self,
        segment_id: str,
        seat_class: str,
        demand_level: float
    ) -> float:
        """Calculate dynamic fare."""
        ...
```

---

## ✅ VERIFICATION CHECKLIST

After moving all files:

- [ ] **No file at root except**: app.py, config.py, schemas.py, database.py, dependencies.py
- [ ] **No duplicates**: Only 1 route finder, 1 seat allocator, 1 pricing engine, 1 cache manager
- [ ] **Domain isolation**: Each domain has clear boundaries in code
- [ ] **Platform usage**: All domains use platform/ layer, not each other
- [ ] **Imports work**: Run `python app.py` without import errors
- [ ] **Tests pass**: All unit/integration tests pass
- [ ] **Performance same**: Search response time unchanged
- [ ] **No circular deps**: Imports form a DAG (directed acyclic graph)

---

## 🚀 NEXT EXECUTION STEPS

1. **Review this architecture** - Confirm boundaries correct
2. **Create interface protocols** - domains/X/interfaces.py files
3. **Phase 1 consolidation** - Route finder, seat allocator, pricing, cache
4. **Phase 2-5 moves** - Execute in order
5. **Import updates** - Update app.py and api/ files
6. **Testing** - Verify everything works
7. **Delete archived files** - Only after success

---

**Status**: Architecture V2 Complete - Ready for Implementation
**Next**: User Review → Interface Protocols → Phase 1 Moves
