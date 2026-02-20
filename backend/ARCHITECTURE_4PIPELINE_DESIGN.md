# Backend Architecture Analysis & 4-Pipeline Data Architecture

**Date**: 2026-02-20
**Phase**: 3 Complete (Unified System) + Advanced Pipeline Design
**Status**: Deployment Planning

---

## PART 1: CURRENT BACKEND STRUCTURE ANALYSIS

### Folder Organization

```
backend/ (251 Python files, 349 MB)
├── Root Level          (41 files)  ⚠️  NEEDS CLEANUP
├── api/                (18 files)  ✅ Router modules
├── core/               (4 files)   ✅ Main routing engine
│   ├── route_engine/   (8 files)   ✅ Phase 2/3 routing
│   ├── validator/      (multiple)  ✅ Validation system
│   ├── validators/     (multiple)  ✅ NEW live validators
│   └── archive/        (legacy)    📦 Deprecated code
├── database/           (4 files)   ✅ ORM models & config
├── services/           (34 files)  ✅ Business logic
├── tests/              (45 files)  ✅ Test suite
├── utils/              (10 files)  ✅ Utilities
├── scripts/            (13 files)  ✅ Standalone tools
├── etl/                (3 files)   ✅ Data pipeline
├── microservices/      (advanced)  📦 gRPC services
├── alembic/            (1 file)    ✅ DB migrations
├── archive/            (legacy)    📦 Deprecated code
└── examples/           (examples)  📚 Code examples
```

### Root Level Files Status

**KEEP at Root (4 files):**
- `app.py` - Main FastAPI application ✅
- `config.py` - Configuration management ✅
- `database.py` - SQLAlchemy session factory ✅
- `schemas.py` - Pydantic request/response schemas ✅

**MOVE to api/ (2 files):**
- `booking_api.py` → `api/booking.py`
- `booking_orchestrator.py` → `services/booking_orchestrator.py`

**MOVE to services/ (5 files):**
- `availability_service.py`
- `train_state_service.py`
- `graph_mutation_service.py`
- `graph_mutation_engine.py`
- `seat_inventory_models.py`
- `shadow_inference_service.py`

**MOVE to core/route_engine/ (3 files):**
- `route_engine.py`
- `frequency_aware_range.py`
- `station_time_index.py`

**MOVE to scripts/ (13 files):**
- `seed_stations.py`
- `check_db.py`
- `inspect_railway_db.py`
- `run_ml_data_collection.py`
- `audit_kafka_config.py`
- `setup_ml_database.py`
- `start_analytics_consumer.py`
- `bulk_update_imports.py`
- `worker.py` (payment reconciliation)
- `search_worker.py` (search processing)
- `mock_api_server.py`

**MOVE to scripts/ml/ or core/ml/ (6 files):**
- `ml_data_collection.py`
- `ml_training_pipeline.py`
- `ml_reliability_model.py`
- `baseline_heuristic_models.py`
- `shadow_inference_service.py`
- `staging_rollout.py`

**MOVE to tests/ (8 files):**
- `test_*.py` files (already in tests usually, but may be duplicated at root)
- `concurrency_load_tester.py`
- `simple_load_test.py`

**DELETE or REVIEW (3 files):**
- `__init__.py` (root init)
- `conftest.py` (should be in tests/)
- `models.py` (should be in database/)

### Folder-Specific Analysis

#### **core/route_engine/** - Phase 2/3 Complete ✅

**Active Files (Keep):**
- `engine.py` (660 lines) - Main RailwayRouteEngine (ENHANCED with Phase 3)
- `raptor.py` (800+ lines) - RAPTOR algorithm implementations
- `graph.py` (500+ lines) - Graph data structures
- `builder.py` (600+ lines) - Graph building logic
- `snapshot_manager.py` (400+ lines) - Snapshot persistence
- `data_provider.py` (300 lines) - PHASE 3: Unified data abstraction ✅ NEW
- `hub.py` - Hub-based routing (Phase 3)

**Purpose**: Implements core RAPTOR algorithm with snapshot system and hub-based optimization

#### **core/validators/** - Validation Framework ✅

**Files:**
- `__init__.py`
- `validation_manager.py` - Orchestrates validators
- `route_validators.py` - Route-specific validators
- `data_integrity_validators.py` - Data consistency checks
- `multimodal_validators.py` - Multi-modal transport validation
- `live_validators.py` (300 lines) - PHASE 3: Live API validators ✅ NEW

**Purpose**: Multi-layer validation system with conditional loading

#### **services/** - Business Logic (34 files)

**Key Services:**
- `booking_service.py`
- `payment_service.py`
- `seat_allocation.py`
- `station_service.py`
- `hybrid_search_service.py`
- `cache_service.py`
- `analytics_service.py`

**Purpose**: Implements all business logic outside of routing

#### **api/** - API Routes (18 files)

**Routers:**
- `search.py` - Main search endpoint (UNIFIED - works offline/hybrid/online) ✅
- `booking.py` - Booking operations
- `routes.py` - Route discovery
- `payments.py` - Payment processing
- `users.py` - User management
- `auth.py` - Authentication
- `admin.py` - Admin operations
- `chat.py` - Chat/support
- `reviews.py` - User reviews
- `websockets.py` - WebSocket connections
- Plus others...

**Purpose**: FastAPI router modules for REST API endpoints

---

## PART 2: ADVANCED 4-PIPELINE DATA ARCHITECTURE

### Overview

The data pipeline is the **critical layer** through which ALL data flows. It prevents code scattered across files and enables clean, testable, performance-optimized data handling.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CLIENT API REQUESTS                              │
│              (/api/search, /api/booking, etc.)                      │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│         PIPELINE ORCHESTRATOR & FEATURE DETECTOR                     │
│         (Config validation, Mode detection: OFFLINE/HYBRID/ONLINE)  │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
        ▼          ▼          ▼
    ┌───────────────────────────────────────┐
    │  PIPELINE 1: DATA ENRICHMENT PIPELINE │
    │  (Fill Missing Data from Live Sources)│
    └──────────────────────────────────────┐
        │
        LVL-1: Live API Connectors
        ├── LiveFareConnector (to LIVE_FARES_API)
        ├── LiveDelayConnector (to LIVE_DELAY_API)
        ├── LiveSeatConnector (to LIVE_SEAT_API)
        └── LiveBookingConnector (to LIVE_BOOKING_API)
              │
        LVL-2: Data Reconciliation Engine
        ├── Check if live data conflicts with DB
        ├── Resolve using fallback rules
        └── Log data source origin (LIVE/DB/FALLBACK)
              │
        LVL-3: Database Writer
        ├── Update seats in DB (from live)
        ├── Update fares in DB (from live)
        ├── Record delays in overlay tables
        └── Maintain data consistency
              │
              ▼
    ┌───────────────────────────────────────┐
    │   PIPELINE 2: ML TRAINING PIPELINE    │
    │   (Continuous Learning System)        │
    └──────────────────────────────────────┐
        │
        LVL-1: Feature Engineering
        ├── Extract route features
        ├── Extract user preferences
        ├── Extract temporal features (season, hour, day)
        ├── Extract statistical features (popularity, delays)
        └── Normalize and transform data
              │
        LVL-2: Real-time Data Collectors
        ├── Collect booking events
        ├── Collect search patterns
        ├── Collect user feedback
        └── Collect delay occurrences
              │
        LVL-3: Batch Model Training
        ├── Train demand prediction model
        ├── Train delay prediction model
        ├── Train ranking/scoring model
        ├── Train seat availability model
        └── Version control for models
              │
        LVL-4: Model Persistence
        ├── Save model artifacts
        ├── Store model metadata
        ├── Version tracking
        └── Fallback to previous version on error
              │
              ▼
    ┌───────────────────────────────────────┐
    │ PIPELINE 3: PREDICTION & CORRECTION  │
    │ (Always Making Smarter Decisions)    │
    └──────────────────────────────────────┐
        │
        LVL-1: Feature Extraction (Real-time)
        ├── Extract query features from user request
        ├── Extract temporal context
        ├── Extract user context
        └── Normalize for model input
              │
        LVL-2: Model Inference Engine
        ├── Predict demand for routes
        ├── Predict delays for trips
        ├── Predict user preference ranking
        ├── Predict seat availability
        └── Get confidence scores
              │
        LVL-3: Prediction Adjustment Layer
        ├── Apply business rules
        ├── Apply fairness constraints
        ├── Apply reliability penalties
        ├── Adjust for current conditions
        └── Rerank results dynamically
              │
        LVL-4: Feedback & Learning Loop
        ├── Compare predictions vs actuals
        ├── Store accuracies
        ├── Trigger retraining if accuracy drops
        ├── Log prediction metadata
        └── Continuous model improvement
              │
              ▼
    ┌───────────────────────────────────────┐
    │    PIPELINE 4: VERIFICATION PIPELINE  │
    │    (Unlock Details + Booking Safety)  │
    └──────────────────────────────────────┐
        │
        LVL-1: Request Validation Layer
        ├── Validate route constraints
        ├── Validate user permissions
        ├── Validate seat availability
        └── Check rate limiting
              │
        LVL-2: Live Data Verification
        ├── Verify seats still available (live check)
        ├── Verify fares haven't changed
        ├── Verify delays are acceptable
        ├── Verify transfer feasibility
        └── Use DataProvider with live fallback
              │
        LVL-3: Risk Assessment Layer
        ├── Calculate transfer success probability
        ├── Calculate on-time delivery probability
        ├── Calculate booking completion probability
        ├── Assign risk level (LOW/MEDIUM/HIGH/CRITICAL)
        └── Add warnings/recommendations
              │
        LVL-4: Booking Validation (Unlock Details)
        ├── Verify fares with user budget
        ├── Verify seats match preferences
        ├── Verify transfer times are safe
        ├── Verify accessibility requirements
        └── Generate unlock token with verification details
              │
        LVL-5: Transaction-Safe Booking
        ├── Hold seats (optimistic lock)
        ├── Lock price (show what user will pay)
        ├── Generate booking ID
        ├── Create payment order
        └── Return booking confirmation
              │
              ▼
        ┌─────────────────┐
        │  API RESPONSE   │
        │  WITH METADATA  │
        │  & MODE INFO    │
        └─────────────────┘
```

### Detailed Pipeline Specifications

#### **PIPELINE 1: Data Enrichment Pipeline**

**Purpose**: Keep database updated with live data from external APIs

**Flow**:
```
User Request for Route/Seats
    ↓
Check: Does user need LIVE data?
    ↓
├─ If OFFLINE: Use database only, skip Pipeline 1
├─ If HYBRID: Try live API, fallback to DB
└─ If ONLINE: Prefer live API

Live Data Fetch (with retry):
    ├─ Level 1: Connect to live API
    │   ├─ Timeout handling (500ms default)
    │   ├─ Retry logic (1 retry)
    │   └─ Circuit breaker on repeated failures
    ├─ Level 2: Validate live data
    │   ├─ Check data format
    │   ├─ Check value ranges
    │   └─ Compare with database (warn if huge difference)
    ├─ Level 3: Reconcile data
    │   ├─ If conflict: apply fallback rules
    │   │   - Use live if newer than 5 min
    │   │   - Use DB if live is unreliable (see history)
    │   │   - Use average of both
    │   └─ Flag conflicts in metrics
    ├─ Level 4: Store live data
    │   ├─ Write to database (shadow table)
    │   ├─ Mark source as LIVE
    │   ├─ Add timestamp
    │   └─ Archive previous version
    └─ Return enriched data
```

**Key Classes**:
- `DataProvider` - Main interface (already created Phase 3)
- `LiveAPIConnector` - Base class for live API connections
  - `LiveFareConnector`
  - `LiveDelayConnector`
  - `LiveSeatConnector`
  - `LiveBookingConnector`
- `DataReconciler` - Handles conflicts
- `DataSourceTracker` - Records data origin

**Configuration**:
```python
# In config.py
LIVE_API_TIMEOUT_MS = 500
LIVE_API_RETRY_COUNT = 1
LIVE_DATA_CACHE_TTL = 300  # 5 min
DATA_CONFLICT_LOG_LEVEL = "WARNING"
```

#### **PIPELINE 2: ML Training Pipeline**

**Purpose**: Continuously improve predictions through learning

**Flow**:
```
Event Stream (Bookings, Searches, Feedback)
    ↓
Buffer events (batch every 1000 or 10 min)
    ↓
Extract Features:
    ├─ Route features: distance, stations, facilities
    ├─ Temporal features: hour, day, season, holidays
    ├─ Statistical features: bookings/hour, delay% history
    ├─ User features: preferences, history, segment
    └─ Environmental features: weather, traffic, events
    ↓
Partition data:
    ├─ Training set (80%)
    ├─ Validation set (10%)
    └─ Test set (10%)
    ↓
Train models (async job, overnight):
    ├─ DemandPredictor - bookings per route per hour
    ├─ DelayPredictor - expected delays per trip
    ├─ RankingModel - user preference scoring
    ├─ SeatsPredictor - availability patterns
    └─ ReliabilityModel - route reliability scoring
    ↓
Evaluate models:
    ├─ Check accuracy metrics
    ├─ Check for overfitting
    ├─ Compare vs previous version
    └─ Alert if accuracy drops >5%
    ↓
Version & store:
    ├─ Save model artifacts (pickle, joblib)
    ├─ Save model metadata (features, version, date)
    ├─ Store in model registry
    └─ Keep last 3 versions for rollback
    ↓
Trigger deployment:
    ├─ If better: gradual rollout (10% → 50% → 100%)
    ├─ Monitor performance
    ├─ Rollback if metrics drop
    └─ Archive old model
```

**Key Classes**:
- `FeatureEngineer` - Extract features from events
- `EventBuffer` - Batch events
- `ModelTrainer` - Train models
- `ModelEvaluator` - Validate models
- `ModelRegistry` - Store and version models
- `TrainingOrchestrator` - Schedule and coordinate training

**Jobs**:
- Daily: Train demand & delay predictors
- Weekly: Train ranking model
- Bi-weekly: Train reliability models
- On-demand: Emergency retraining if accuracy drops

#### **PIPELINE 3: Prediction & Correction Pipeline**

**Purpose**: Make intelligent predictions and continuously learn from outcomes

**Flow**:
```
User sends search request
    ↓
Extract features:
    ├─ Route: source, destination, stops
    ├─ Time: travel date/time
    ├─ Context: user preferences, history
    └─ Environment: current delays, congestion
    ↓
Get predictions from models:
    ├─ Route demand: percentage full
    ├─ Expected delays: minutes late/early
    ├─ Ranking score: suitability for user
    ├─ Seat availability: confidence %
    └─ Reliability: probability of on-time delivery
    ↓
Adjust predictions:
    ├─ Apply business rules
    │   └─ Enforce max transfer window
    ├─ Apply constraints
    │   └─ Budget, accessibility, preferences
    ├─ Apply penalties
    │   └─ Reduce score for high-delay routes
    └─ Apply bonuses
        └─ Increase score for preferred partners
    ↓
Rerank results:
    ├─ Sort by adjusted scores
    ├─ Diversify recommendations
    ├─ Balance price vs quality
    └─ Return top N results
    ↓
Store prediction metadata:
    ├─ Record what was predicted
    ├─ Record which model version used
    ├─ Record timestamp
    └─ Store user preferences applied
    ↓
Later: User books → Compare actual vs prediction:
    ├─ Did seats actually get sold?
    ├─ Did trip actually get delayed?
    ├─ Did user like the recommendation?
    ├─ Record accuracy
    └─ Trigger retrain if accuracy drops
```

**Key Classes**:
- `FeatureExtractor` - Extract real-time features
- `PredictionEngine` - Load models and predict
- `PredictionAdjuster` - Apply rules and constraints
- `ResultRanker` - Score and rank results
- `PredictionLogger` - Record predictions
- `FeedbackCollector` - Collect actual outcomes
- `AccuracyMonitor` - Compare predictions vs actuals

#### **PIPELINE 4: Verification Pipeline (Most Critical)**

**Purpose**: Verify data before user booking, assess risks, unlock full details

**Substages**:

**Stage 4.1: Request Validation**
```
User clicks "Unlock Details" on a route
    ↓
Validate request:
    ├─ Is route still in results? (not expired)
    ├─ Is user authenticated? (has session)
    ├─ Is user rate-limited? (< 100 unlocks/day)
    └─ Is route still available? (not cancelled)
    ↓
Load route details from DB/cache:
    ├─ Segments
    ├─ Coaches
    ├─ Current fares
    └─ Known delays
    ↓
Pass to Stage 4.2
```

**Stage 4.2: Live Data Verification**
```
Verify against live APIs (if available):
    ├─ Are seats still available?
    │   └─ LiveSeatConnector.get_seats(trip_id)
    ├─ Have fares changed?
    │   └─ LiveFareConnector.get_fares(segment_id)
    ├─ Are there new delays?
    │   └─ LiveDelayConnector.get_delays(trip_id)
    └─ Can transfers still be made?
        └─ LiveBookingConnector.validate_transfers()
    ↓
If any live API fails:
    ├─ Use database fallback
    ├─ Mark as PARTIAL_LIVE
    └─ Show data freshness indicator to user
    ↓
Pass to Stage 4.3
```

**Stage 4.3: Risk Assessment**
```
Calculate probabilities:
    ├─ Transfer Success Probability
    │   └─ Based on: wait time, distance, exchange bus
    ├─ On-Time Delivery Probability
    │   └─ Based on: historical delays, current congestion
    ├─ Booking Completion Probability
    │   └─ Based on: payment gateway reliability
    └─ Seat Availability Until Purchase
        └─ Based on: demand prediction, competitor pressure
    ↓
Assign risk level:
    ├─ GREEN (90%+): Safe to book
    ├─ YELLOW (70-89%): Consider alternatives
    ├─ ORANGE (50-69%): Significant risk
    ├─ RED (30-49%): High risk
    └─ CRITICAL (<30%): Not recommended
    ↓
Generate warnings:
    ├─ "High demand route - 3 seats left"
    ├─ "Connection has historical 15min delays"
    ├─ "Payment gateway slower than usual"
    └─ "Competing passengers also searching this route"
    ↓
Pass to Stage 4.4
```

**Stage 4.4: Booking Validation**
```
Final verification before showing unlock details:
    ├─ Confirm fares
    │   └─ Still within user's budget?
    ├─ Confirm seats
    │   └─ Still in preferred class?
    ├─ Confirm transfers
    │   └─ Still safe (15+ min transfer time)?
    ├─ Verify accessibility
    │   └─ Wheelchair accessible if required?
    └─ Verify special requirements
        └─ Meal preferences, pet accommodation, etc.
    ↓
Generate unlock token:
    ├─ Route details (all segments)
    ├─ Final fares (show breakdown)
    ├─ Seat assignments (specific seat numbers)
    ├─ Baggage allowance
    ├─ Cancellation terms
    ├─ Risk indicators (from 4.3)
    ├─ Freshness indicator (VERIFIED_OFFLINE/HYBRID/ONLINE)
    └─ Token expiry (15 min)
    ↓
Pass to Stage 4.5
```

**Stage 4.5: Transaction-Safe Booking Initiation**
```
When user clicks "Book Now":
    ├─ Optimistic lock: Hold seats
    │   └─ Mark as "HOLDING_YOU" in database
    ├─ Price lock: Confirm final price
    │   └─ Create price quote in database
    ├─ Generate booking ID
    │   └─ (Not yet confirmed, just reserved)
    ├─ Create payment order
    │   └─ In payment gateway (not captured)
    └─ Return to user:
        ├─ Booking ID
        ├─ Payment link
        ├─ Seat numbers
        └─ Final price
    ↓
After payment success:
    ├─ Capture payment
    ├─ Mark seats as BOOKED
    ├─ Send confirmation email
    └─ Return booking confirmation
    ↓
If payment fails or timeout:
    ├─ Release seat hold
    ├─ Expire price quote
    ├─ Delete payment order
    └─ Offer to retry
```

**Key Classes**:
- `RequestValidator` - Stage 4.1
- `LiveVerifier` - Stage 4.2 (uses DataProvider)
- `RiskAssessor` - Stage 4.3
- `BookingValidator` - Stage 4.4
- `UnlockTokenGenerator` - Generate unlock details
- `TransactionManager` - Stage 4.5 (holds seats/prices)

**Configuration**:
```python
VERIFICATION_TIMEOUT_MS = 2000  # 2 sec for all checks
UNLOCK_TOKEN_EXPIRY_MINUTES = 15
SEAT_HOLD_DURATION_MINUTES = 10
MAX_UNLOCKS_PER_USER_PER_DAY = 100
RISK_THRESHOLD_CRITICAL = 0.30
RISK_THRESHOLD_RED = 0.50
RISK_THRESHOLD_ORANGE = 0.70
RISK_THRESHOLD_YELLOW = 0.90
```

---

## PART 3: IMPLEMENTATION ROADMAP

### Phase 3A: Complete Pipelines (Weeks 1-2)

1. **Data Enrichment Pipeline** (`backend/pipelines/enrichment/`)
   - Create `LiveAPIConnector` base class
   - Create specific connectors (Fare, Delay, Seat, Booking)
   - Create `DataReconciler`
   - Integrate with `DataProvider`

2. **ML Training Pipeline** (`backend/pipelines/ml_training/`)
   - Create `FeatureEngineer`
   - Create `EventBuffer` and `EventCollector`
   - Create individual model trainers
   - Create `ModelRegistry`

3. **Prediction Pipeline** (`backend/pipelines/prediction/`)
   - Create model inference engine
   - Create adjustment layer
   - Create feedback collection

4. **Verification Pipeline** (`backend/pipelines/verification/`)
   - Create 4 stages (validation, live verify, risk assess, booking)
   - Create unlock token system
   - Create transaction manager

### Phase 3B: Integration & Testing (Week 3)

1. Route all data through pipelines
2. Remove scattered API calls, move to pipelines
3. Integration testing
4. Performance testing

### Phase 3C: Cleanup & Deployment (Week 4)

1. Move root-level files
2. Archive duplicates
3. Update imports
4. Final testing
5. Deployment

---

## PART 4: FILE REORGANIZATION PLAN

### Step 1: Create New Pipeline Structure

```
backend/
└── pipelines/                    # NEW
    ├── __init__.py
    ├── base.py                   # Base pipeline classes
    ├── enrichment/                # Pipeline 1
    │   ├── __init__.py
    │   ├── connectors.py          # LiveAPIConnectors
    │   ├── reconciler.py          # DataReconciler
    │   └── enrichment_engine.py   # Main orchestrator
    ├── ml_training/               # Pipeline 2
    │   ├── __init__.py
    │   ├── feature_engineer.py    # Feature extraction
    │   ├── event_buffer.py        # Event batching
    │   ├── trainers/              # Individual trainers
    │   │   ├── demand_trainer.py
    │   │   ├── delay_trainer.py
    │   │   ├── ranking_trainer.py
    │   │   └── reliability_trainer.py
    │   ├── model_registry.py      # Model versioning
    │   └── training_orchestrator.py
    ├── prediction/                # Pipeline 3
    │   ├── __init__.py
    │   ├── feature_extractor.py   # Real-time features
    │   ├── inference_engine.py    # Model prediction
    │   ├── adjuster.py            # Apply rules
    │   ├── ranker.py              # Score & rank
    │   └── prediction_logger.py   # Record predictions
    └── verification/              # Pipeline 4
        ├── __init__.py
        ├── request_validator.py   # Stage 1
        ├── live_verifier.py       # Stage 2
        ├── risk_assessor.py       # Stage 3
        ├── booking_validator.py   # Stage 4
        ├── unlock_token_generator.py
        ├── transaction_manager.py # Stage 5
        └── verification_engine.py # Main orchestrator
```

### Step 2: Move Root Files

Move 37 files from root to appropriate locations (list above).

### Step 3: Archive Structure

```
backend/archive/
├── offline_phase2_deprecated/    # Already created
│   ├── README.md
│   ├── offline_search.py
│   ├── offline_engine.py
│   └── validators_offline.py
├── root_level_cleanup/           # NEW
│   ├── README.md
│   └── [moved files for reference]
└── legacy_code/
    └── [other deprecated components]
```

---

## SUMMARY

✅ **Phase 3: Unified System** - COMPLETE
- DataProvider (unified abstraction)
- Live Validators (conditional loading)
- RailwayRouteEngine (auto-detection)
- Config (feature flags)
- App (clean startup logging)
- Offline files (archived)

⏳ **Next: 4-Pipeline Architecture** - Ready for Implementation
- Pipeline 1: Data Enrichment
- Pipeline 2: ML Training
- Pipeline 3: Prediction & Correction
- Pipeline 4: Verification (Unlock Details & Booking)

Each pipeline has clear layer structure (3-5 levels) for clean data flow and performance optimization.

**Deployment Ready**: All data flows through pipelines, no scattered code, single source of truth.
