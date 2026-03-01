# DETAILED EXECUTION PLAN - READY FOR IMPLEMENTATION

**Status:** IMPLEMENTATION READY
**Date:** 2026-02-20
**Total Actions:** 147 items across 12 categories

---

## PHASE 1: ROUTE ENGINES - COMPLETION & CLEANUP

### Verify Core Route Engine (backend/core/route_engine.py)
- [ ] READ full `backend/core/route_engine.py` (2,447 lines)
- [ ] VERIFY OptimizedRAPTOR implementation complete
- [ ] VERIFY HybridRAPTOR hub acceleration present
- [ ] VERIFY real-time overlay (Copy-on-Write) implementation
- [ ] VERIFY StaticGraphSnapshot and HubManager classes
- [ ] VERIFY ValidationManager integration
- [ ] VERIFY ML reliability scoring
- [ ] TEST import all required modules
- [ ] RUN unit tests for route_engine.py
- [ ] DOCUMENT any gaps found

### Expand Domain Routing Engine (backend/domains/routing/engine.py)
- [ ] READ current `backend/domains/routing/engine.py`
- [ ] VERIFY imports from core components
- [ ] ADD missing imports (if any)
- [ ] ADD async interface wrapper
- [ ] ADD ML ranking integration
- [ ] ADD real-time event processor integration
- [ ] ADD live validators integration
- [ ] ADD test imports resolve correctly
- [ ] CREATE unit tests for domain adapter
- [ ] TEST end-to-end routing flow

### Delete Archive Route Engine Versions
- [ ] BACKUP `backend/archive/route_engines_v1/` (git history)
- [ ] DELETE `backend/archive/route_engines_v1/advanced_route_engine.py`
- [ ] DELETE `backend/archive/route_engines_v1/multi_modal_route_engine.py`
- [ ] DELETE `backend/archive/route_engines_v1/route_engine.py`
- [ ] DELETE `backend/archive/route_engines_consolidated/` (entire folder)
- [ ] DELETE `backend/core/archive/` (old versions)
- [ ] GIT COMMIT: "Delete archival route engine versions"

### Update All Route Engine Imports
- [ ] FIND all imports from `backend.archive.route_engines_*`
- [ ] FIND all imports from `backend.core.archive`
- [ ] REPLACE with `backend.core.route_engine`
- [ ] UPDATE API endpoints to use new imports
- [ ] UPDATE domain routing imports
- [ ] RUN full test suite
- [ ] GIT COMMIT: "Update route engine imports"

### Route Engine Final Actions
- [ ] CREATE integration test (E2E route search)
- [ ] PERFORMANCE TEST (target: <5ms, P95: <50ms)
- [ ] LOAD TEST (10K+ req/sec)
- [ ] VERIFY all validators working
- [ ] VERIFY ML reliability scoring
- [ ] VERIFY real-time overlays functional
- [ ] Update architecture documentation
- [ ] GIT COMMIT: "Complete route engine consolidation"

---

## PHASE 2: SEAT ALLOCATION - VERIFICATION & ENHANCEMENT

### Verify Seat Allocator (backend/domains/inventory/seat_allocator.py)
- [ ] READ `backend/domains/inventory/seat_allocator.py` (482 lines)
- [ ] VERIFY fair multi-coach distribution algorithm
- [ ] VERIFY berth preference optimization
- [ ] VERIFY family grouping logic
- [ ] VERIFY accessibility handling
- [ ] VERIFY overbooking management
- [ ] VERIFY waitlist management
- [ ] VERIFY OccupancyMetricsCollector integration
- [ ] VERIFY shared infrastructure imports correct
- [ ] TEST import all dependencies
- [ ] RUN unit tests

### Compare with Archive Version
- [ ] READ `backend/archive/seat_allocators_v1/advanced_seat_allocation_engine.py`
- [ ] COMPARE algorithms (archive vs. current)
- [ ] IDENTIFY unique features in archive (if any)
- [ ] IDENTIFY missing features in current (if any)
- [ ] MERGE any unique archive features
- [ ] DOCUMENT algorithm differences

### Delete Archive Seat Allocator Versions
- [ ] BACKUP `backend/archive/seat_allocators_v1/` (git history)
- [ ] DELETE `backend/archive/seat_allocators_v1/advanced_seat_allocation_engine.py`
- [ ] DELETE `backend/archive/seat_allocators_v1/seat_allocation.py`
- [ ] DELETE `backend/archive/seat_allocators_v1/smart_seat_allocation.py`
- [ ] DELETE `backend/archive/seat_allocators_consolidated/` (entire folder)
- [ ] GIT COMMIT: "Delete archival seat allocator versions"

### Add Revenue Optimization Feature
- [ ] DESIGN revenue optimization algorithm
- [ ] IMPLEMENT yield management logic
- [ ] INTEGRATE with pricing engine
- [ ] ADD occupancy-based pricing feedback
- [ ] TEST revenue optimization
- [ ] GIT COMMIT: "Add revenue optimization to seat allocator"

### Update Seat Allocator Imports
- [ ] FIND all imports from `backend.archive.seat_allocators_*`
- [ ] REPLACE with `backend.domains.inventory.seat_allocator`
- [ ] UPDATE API endpoints
- [ ] TEST all seat allocation flows

### Seat Allocation Final Actions
- [ ] CREATE integration test (booking + allocation)
- [ ] PERFORMANCE TEST (allocate 1000+ seats in <100ms)
- [ ] TEST family grouping logic
- [ ] TEST accessibility handling
- [ ] TEST overbooking scenarios
- [ ] TEST waitlist promotion
- [ ] VERIFY metrics collection
- [ ] Update architecture documentation
- [ ] GIT COMMIT: "Complete seat allocation consolidation"

---

## PHASE 3: PRICING - VERIFICATION & ENHANCEMENT

### Verify Pricing Engine (backend/domains/pricing/engine.py)
- [ ] READ `backend/domains/pricing/engine.py` (462 lines)
- [ ] VERIFY DynamicPricingEngine class complete
- [ ] VERIFY 5 pricing factors implemented:
  - [ ] Demand Multiplier (0.9 - 1.6x)
  - [ ] Time Multiplier (0.85 - 1.40x)
  - [ ] Route Popularity Multiplier (0.9 - 1.15x)
  - [ ] Seasonality Multiplier (0.9 - 1.35x)
  - [ ] Competitor-Aware Multiplier (0.92 - 1.08x)
- [ ] VERIFY Tatkal surge (1.5x)
- [ ] VERIFY geometric mean factor combination
- [ ] VERIFY ML model integration (TatkalDemandPredictor, RouteRankingPredictor)
- [ ] VERIFY fallback to heuristics
- [ ] TEST import all dependencies
- [ ] RUN unit tests

### Compare with Archive Versions
- [ ] READ `backend/archive/pricing_engines_v1/price_calculation_service.py`
- [ ] READ `backend/archive/pricing_engines_v1/yield_management_engine.py`
- [ ] IDENTIFY unique features in archive
- [ ] MERGE any needed features
- [ ] DOCUMENT pricing algorithm evolution

### Delete Archive Pricing Versions
- [ ] BACKUP `backend/archive/pricing_engines_v1/` (git history)
- [ ] DELETE `backend/archive/pricing_engines_v1/price_calculation_service.py`
- [ ] DELETE `backend/archive/pricing_engines_v1/yield_management_engine.py`
- [ ] DELETE `backend/archive/pricing_engines_consolidated/` (entire folder)
- [ ] GIT COMMIT: "Delete archival pricing versions"

### Add Advanced Features
- [ ] ADD real-time competitor price integration (API)
- [ ] ADD revenue management optimization (yield management)
- [ ] IMPLEMENT group discount logic (5+ passengers = 5% discount)
- [ ] IMPLEMENT loyalty tier pricing adjustments
- [ ] IMPLEMENT corporate partnership rates
- [ ] IMPLEMENT seasonal package pricing
- [ ] TEST all new features
- [ ] GIT COMMIT: "Add advanced pricing features"

### Update Pricing Imports
- [ ] FIND all imports from `backend.archive.pricing_engines_*`
- [ ] REPLACE with `backend.domains.pricing.engine`
- [ ] UPDATE API endpoints
- [ ] UPDATE booking flow to use pricing engine
- [ ] TEST pricing calculations

### Pricing Final Actions
- [ ] CREATE comprehensive pricing test suite
- [ ] PERFORMANCE TEST (calculate 10K+ prices/sec)
- [ ] TEST all pricing factors independently
- [ ] TEST combined factor interactions
- [ ] TEST edge cases (holiday surges, last-minute)
- [ ] TEST group discount logic
- [ ] TEST competitor parity
- [ ] VERIFY ML fallback works
- [ ] Update architecture documentation
- [ ] GIT COMMIT: "Complete pricing consolidation"

---

## PHASE 4: CACHING - VERIFICATION & CLEANUP

### Verify Platform Cache Manager (backend/platform/cache/manager.py)
- [ ] READ `backend/platform/cache/manager.py`
- [ ] VERIFY MultiLayerCache class structure
- [ ] VERIFY 4-layer architecture:
  - [ ] Layer 1: Query Cache (2-10min TTL)
  - [ ] Layer 2: Partial Route Cache
  - [ ] Layer 3: Seat Availability Cache (30s-2min TTL)
  - [ ] Layer 4: ML Feature Cache
- [ ] VERIFY intelligent TTL management
- [ ] VERIFY cache warming strategies
- [ ] VERIFY automatic invalidation
- [ ] VERIFY Redis integration
- [ ] VERIFY metrics collection
- [ ] TEST import all dependencies
- [ ] RUN unit tests

### Verify Cache Warming (backend/platform/cache/warming.py)
- [ ] READ `backend/platform/cache/warming.py`
- [ ] VERIFY warming strategies implemented
- [ ] VERIFY popular routes pre-warming
- [ ] VERIFY off-peak warming
- [ ] VERIFY TTL configuration
- [ ] TEST warming performance
- [ ] RUN unit tests

### Delete Archive Cache Versions
- [ ] BACKUP `backend/archive/cache_managers_v1/` (git history)
- [ ] DELETE `backend/archive/cache_managers_v1/multi_layer_cache.py`
- [ ] DELETE `backend/archive/cache_managers_consolidated/` (entire folder)
- [ ] GIT COMMIT: "Delete archival cache versions"

### Verify Cache Integration with Route Engine
- [ ] VERIFY route_engine.py uses platform/cache/manager
- [ ] VERIFY cache hit rates > 60% for common routes
- [ ] VERIFY cache invalidation on data changes
- [ ] VERIFY multi-instance Redis coordination
- [ ] TEST cache failover scenarios
- [ ] GIT COMMIT: "Verify cache integration"

### Caching Final Actions
- [ ] CREATE cache performance test
- [ ] LOAD TEST (cache hit rates, memory usage)
- [ ] TEST TTL management (expiration)
- [ ] TEST warming strategies (off-peak behavior)
- [ ] TEST multi-instance coordination
- [ ] VERIFY metrics collection (hit rate, misses, memory)
- [ ] Update architecture documentation
- [ ] GIT COMMIT: "Complete cache consolidation"

---

## PHASE 5: BOOKING - VERIFICATION & COMPLETION

### Verify Booking Service (backend/domains/booking/service.py)
- [ ] READ `backend/domains/booking/service.py`
- [ ] VERIFY BookingService class complete
- [ ] VERIFY PNR generation with uniqueness
- [ ] VERIFY passenger details handling
- [ ] VERIFY serializable transaction isolation
- [ ] VERIFY retry logic (MAX_RETRIES = 3)
- [ ] VERIFY travel date validation
- [ ] VERIFY event publishing (BookingCreatedEvent)
- [ ] VERIFY booking status management
- [ ] TEST import all dependencies
- [ ] RUN unit tests

### Compare with Archive Version
- [ ] READ `backend/archive/booking_consolidated/v1/booking_service.py`
- [ ] COMPARE features with current version
- [ ] IDENTIFY any missing features
- [ ] MERGE missing features if needed
- [ ] DOCUMENT any differences

### Verify Booking API (backend/api/payments.py or payments endpoint)
- [ ] VERIFY API calls domain BookingService
- [ ] VERIFY request validation
- [ ] VERIFY error handling
- [ ] VERIFY response formatting
- [ ] TEST API integration

### Delete Archive Booking Versions
- [ ] BACKUP `backend/archive/booking_consolidated/v1/` (git history)
- [ ] DELETE `backend/archive/booking_consolidated/v1/booking_service.py`
- [ ] DELETE `backend/archive/booking_consolidated/v1/booking_orchestrator.py`
- [ ] DELETE `backend/archive/booking_consolidated/v1/booking_api.py`
- [ ] DELETE `backend/archive/booking_consolidated/` (entire folder)
- [ ] GIT COMMIT: "Delete archival booking versions"

### Update Booking Imports
- [ ] FIND all imports from `backend.archive.booking_consolidated*`
- [ ] REPLACE with `backend.domains.booking.service`
- [ ] UPDATE API endpoints
- [ ] TEST booking endpoints

### Booking Final Actions
- [ ] CREATE E2E booking test (search → book → confirm)
- [ ] TEST race condition prevention (serializable isolation)
- [ ] TEST PNR uniqueness (1000+ concurrent bookings)
- [ ] TEST passenger details storage
- [ ] TEST event publishing
- [ ] TEST retry logic
- [ ] VERIFY booking status transitions
- [ ] Update architecture documentation
- [ ] GIT COMMIT: "Complete booking consolidation"

---

## PHASE 6: PAYMENT - VERIFICATION & COMPLETION

### Verify Payment Service (backend/domains/payment/service.py)
- [ ] READ `backend/domains/payment/service.py`
- [ ] VERIFY PaymentService class structure
- [ ] VERIFY Razorpay API integration
- [ ] VERIFY async/await with httpx
- [ ] VERIFY order creation with idempotency
- [ ] VERIFY payment verification (signature)
- [ ] VERIFY webhook signature verification (HMAC-SHA256)
- [ ] VERIFY configuration validation
- [ ] VERIFY error handling
- [ ] TEST import all dependencies
- [ ] RUN unit tests

### Compare with Archive Version
- [ ] READ `backend/archive/payment_consolidated/v1/payment_service.py`
- [ ] COMPARE features with current
- [ ] IDENTIFY any missing features
- [ ] MERGE missing features if needed

### Verify Payment API (backend/api/payments.py)
- [ ] VERIFY API calls domain PaymentService
- [ ] VERIFY create_order endpoint
- [ ] VERIFY verify_payment endpoint
- [ ] VERIFY webhook handling
- [ ] TEST API integration

### Delete Archive Payment Versions
- [ ] BACKUP `backend/archive/payment_consolidated/v1/` (git history)
- [ ] DELETE `backend/archive/payment_consolidated/v1/payment_service.py`
- [ ] DELETE `backend/archive/payment_consolidated/` (entire folder)
- [ ] GIT COMMIT: "Delete archival payment versions"

### Update Payment Imports
- [ ] FIND all imports from `backend.archive.payment_consolidated*`
- [ ] REPLACE with `backend.domains.payment.service`
- [ ] UPDATE API endpoints
- [ ] TEST payment flow

### Payment Final Actions
- [ ] CREATE payment test suite (orders, verification, webhooks)
- [ ] TEST Razorpay order creation
- [ ] TEST payment verification
- [ ] TEST webhook signature verification
- [ ] TEST idempotency (duplicate order prevention)
- [ ] TEST error scenarios (API failure, timeout, invalid signature)
- [ ] VERIFY configuration handling
- [ ] Update architecture documentation
- [ ] GIT COMMIT: "Complete payment consolidation"

---

## PHASE 7: STATION SERVICES - VERIFICATION & COMPLETION

### Verify Station Services (backend/domains/station/)
- [ ] READ `backend/domains/station/service.py`
- [ ] READ `backend/domains/station/departure_service.py`
- [ ] VERIFY all CRUD operations
- [ ] VERIFY departure scheduling
- [ ] VERIFY station data consistency
- [ ] VERIFY foreign key constraints
- [ ] TEST import all dependencies
- [ ] RUN unit tests

### Compare with Archive Versions
- [ ] READ `backend/archive/station_consolidated/v1/station_service.py`
- [ ] READ `backend/archive/station_consolidated/v1/station_departure_service.py`
- [ ] COMPARE features with current
- [ ] IDENTIFY any missing features
- [ ] MERGE missing features if needed

### Verify Seed Scripts
- [ ] READ `backend/seed_stations.py` (root)
- [ ] READ `backend/scripts/seed_stations.py`
- [ ] CONSOLIDATE: Keep in scripts/, reference from root if needed
- [ ] TEST seed script functionality

### Delete Archive Station Versions
- [ ] BACKUP `backend/archive/station_consolidated/v1/` (git history)
- [ ] DELETE `backend/archive/station_consolidated/v1/station_service.py`
- [ ] DELETE `backend/archive/station_consolidated/v1/station_departure_service.py`
- [ ] DELETE `backend/archive/station_consolidated/` (entire folder)
- [ ] DELETE `backend/seed_stations.py` (if redundant with scripts version)
- [ ] GIT COMMIT: "Delete archival station versions"

### Station Final Actions
- [ ] CREATE E2E station test suite
- [ ] TEST station CRUD
- [ ] TEST departure scheduling
- [ ] TEST data consistency
- [ ] TEST seed script
- [ ] VERIFY database integrity
- [ ] Update architecture documentation
- [ ] GIT COMMIT: "Complete station consolidation"

---

## PHASE 8: USER MANAGEMENT - EXPANSION & COMPLETION

### Expand User Service (backend/domains/user/service.py)
- [ ] READ current `backend/domains/user/service.py`
- [ ] READ `backend/archive/user_consolidated/v1/user_service.py`
- [ ] DESIGN UserService class
- [ ] IMPLEMENT user creation
- [ ] IMPLEMENT user retrieval (by ID, email, phone)
- [ ] IMPLEMENT user profile update
- [ ] IMPLEMENT user preferences
- [ ] IMPLEMENT authentication integration
- [ ] IMPLEMENT activity tracking
- [ ] IMPLEMENT shared infrastructure integration
- [ ] CREATE unit tests
- [ ] TEST all operations

### Create User Interfaces (backend/domains/user/interfaces.py)
- [ ] CREATE UserContext data class
- [ ] CREATE UserPreferences data class
- [ ] CREATE user validation schemas
- [ ] CREATE user response schemas

### Verify User API (backend/api/users.py)
- [ ] VERIFY API calls domain UserService
- [ ] VERIFY endpoints: GET, POST, PUT, DELETE
- [ ] VERIFY error handling
- [ ] TEST API integration

### Delete Archive User Versions
- [ ] BACKUP `backend/archive/user_consolidated/v1/` (git history)
- [ ] DELETE `backend/archive/user_consolidated/v1/user_service.py`
- [ ] DELETE `backend/archive/user_consolidated/` (entire folder)
- [ ] GIT COMMIT: "Delete archival user versions"

### User Final Actions
- [ ] CREATE E2E user test suite
- [ ] TEST user CRUD
- [ ] TEST profile updates
- [ ] TEST preferences
- [ ] TEST authentication
- [ ] VERIFY data security
- [ ] Update architecture documentation
- [ ] GIT COMMIT: "Complete user consolidation"

---

## PHASE 9: VERIFICATION & SECURITY - VERIFICATION & CLEANUP

### Verify Unlock Service (backend/domains/verification/unlock_service.py)
- [ ] READ `backend/domains/verification/unlock_service.py`
- [ ] VERIFY unlock recording logic
- [ ] VERIFY duplicate prevention
- [ ] VERIFY live availability check
- [ ] VERIFY unlocked routes retrieval
- [ ] VERIFY payment ID linking
- [ ] TEST import all dependencies
- [ ] RUN unit tests

### Compare with Archive Versions
- [ ] READ `backend/archive/verification_consolidated/v1/unlock_service.py`
- [ ] READ `backend/archive/verification_consolidated/v1/verification_engine.py`
- [ ] COMPARE features with current
- [ ] IDENTIFY any missing features
- [ ] MERGE missing features if needed

### Delete Archive Verification Versions
- [ ] BACKUP `backend/archive/verification_consolidated/v1/` (git history)
- [ ] DELETE `backend/archive/verification_consolidated/v1/unlock_service.py`
- [ ] DELETE `backend/archive/verification_consolidated/v1/verification_engine.py`
- [ ] DELETE `backend/archive/verification_consolidated/` (entire folder)
- [ ] GIT COMMIT: "Delete archival verification versions"

### Verification Final Actions
- [ ] CREATE E2E verification test
- [ ] TEST unlock recording
- [ ] TEST duplicate prevention
- [ ] TEST live availability check
- [ ] VERIFY payment linkage
- [ ] Update architecture documentation
- [ ] GIT COMMIT: "Complete verification consolidation"

---

## PHASE 10: EVENT PROCESSING - VERIFICATION & CLEANUP

### Verify Event Producer (backend/platform/events/producer.py)
- [ ] READ `backend/platform/events/producer.py`
- [ ] VERIFY event types (RouteSearched, BookingCreated, PaymentProcessed)
- [ ] VERIFY event schema
- [ ] VERIFY Kafka publishing
- [ ] VERIFY circuit breaker pattern
- [ ] VERIFY metrics collection
- [ ] VERIFY fire-and-forget semantics
- [ ] TEST import all dependencies
- [ ] RUN unit tests

### Verify Event Consumer (backend/platform/events/consumer.py)
- [ ] READ `backend/platform/events/consumer.py`
- [ ] VERIFY event consumption
- [ ] VERIFY handler routing
- [ ] VERIFY error handling
- [ ] VERIFY metrics collection
- [ ] TEST import all dependencies
- [ ] RUN unit tests

### Compare with Archive Versions
- [ ] READ `backend/archive/platform_consolidated/v1/event_producer.py`
- [ ] READ `backend/archive/platform_consolidated/v1/analytics_consumer.py`
- [ ] COMPARE event types with current
- [ ] IDENTIFY any missing features
- [ ] MERGE missing features if needed

### Delete Archive Event Versions
- [ ] BACKUP `backend/archive/platform_consolidated/v1/` (git history)
- [ ] DELETE `backend/archive/platform_consolidated/v1/event_producer.py`
- [ ] DELETE `backend/archive/platform_consolidated/v1/analytics_consumer.py`
- [ ] DELETE `backend/archive/platform_consolidated/v1/performance_monitor.py`
- [ ] DELETE `backend/archive/platform_consolidated/` (entire folder)
- [ ] GIT COMMIT: "Delete archival event versions"

### Event Processing Final Actions
- [ ] CREATE E2E event test (produce → consume)
- [ ] TEST event publishing
- [ ] TEST circuit breaker activation
- [ ] TEST event consumption
- [ ] TEST handler routing
- [ ] VERIFY metrics collection
- [ ] Load test (1000+ events/sec)
- [ ] Update architecture documentation
- [ ] GIT COMMIT: "Complete event consolidation"

---

## PHASE 11: GRAPH & NETWORK - VERIFICATION

### Verify Graph Components (backend/core/route_engine/graph.py)
- [ ] READ `backend/core/route_engine/graph.py`
- [ ] VERIFY graph data structures
- [ ] VERIFY Space-Time node implementation
- [ ] VERIFY graph building algorithms
- [ ] VERIFY indexing structures
- [ ] TEST import all dependencies
- [ ] RUN unit tests

### Verify Graph Mutation (backend/graph_mutation_service.py)
- [ ] READ `backend/graph_mutation_service.py`
- [ ] VERIFY real-time mutation handling
- [ ] VERIFY Copy-on-Write overlays
- [ ] VERIFY delay injection
- [ ] VERIFY trip cancellation
- [ ] VERIFY platform changes
- [ ] VERIFY occupancy tracking
- [ ] TEST import all dependencies
- [ ] RUN unit tests

### Verify Separation of Concerns
- [ ] ENSURE graph.py has graph structures only
- [ ] ENSURE graph_mutation_service.py handles updates only
- [ ] REFACTOR if overlap found
- [ ] TEST interaction between modules

### Graph & Network Final Actions
- [ ] CREATE graph mutation test suite
- [ ] TEST real-time updates
- [ ] TEST overlay application
- [ ] TEST delay injection
- [ ] TEST occupancy tracking
- [ ] Verify path finding with mutations
- [ ] Update architecture documentation
- [ ] GIT COMMIT: "Complete graph consolidation"

---

## PHASE 12: ML/INTELLIGENCE - MAJOR REORGANIZATION

### Step 1: Create Intelligence Training Structure
- [ ] CREATE `backend/intelligence/training/` directory
- [ ] CREATE `backend/intelligence/training/__init__.py`
- [ ] CREATE `backend/intelligence/models/base_model.py` (abstract base)
- [ ] GIT COMMIT: "Create intelligence training structure"

### Step 2: Move ML Training Files
- [ ] MOVE `backend/ml_data_collection.py` → `intelligence/training/data_collection.py`
- [ ] MOVE `backend/ml_training_pipeline.py` → `intelligence/training/pipeline.py`
- [ ] MOVE `backend/setup_ml_database.py` → `intelligence/training/setup_db.py`
- [ ] UPDATE imports in moved files
- [ ] UPDATE wrapper scripts in `backend/scripts/`
- [ ] TEST scripts in new location
- [ ] GIT COMMIT: "Move ML training files to intelligence/"

### Step 3: Verify Live Predictor Services (backend/services/)
- [ ] READ `backend/services/delay_predictor.py` (CANONICAL)
  - [ ] VERIFY DelayPredictor class complete
  - [ ] VERIFY model loading/training
  - [ ] VERIFY real-time delay updates
  - [ ] VERIFY TTL management
  - [ ] RUN unit tests

- [ ] READ `backend/services/route_ranking_predictor.py`
  - [ ] VERIFY RouteRankingPredictor functionality
  - [ ] RUN unit tests

- [ ] READ `backend/services/cancellation_predictor.py`
  - [ ] VERIFY CancellationPredictor functionality
  - [ ] RUN unit tests

- [ ] READ `backend/services/tatkal_demand_predictor.py`
  - [ ] VERIFY TatkalDemandPredictor functionality
  - [ ] RUN unit tests

- [ ] CREATE `backend/services/__init__.py` (service registry)
  - [ ] REGISTER all predictors
  - [ ] PROVIDE factory methods

### Step 4: Delete Duplicate Predictors from Intelligence/Models
- [ ] BACKUP `backend/intelligence/models/` (git history)
- [ ] DELETE `backend/intelligence/models/delay_predictor.py` (DUPLICATE)
- [ ] DELETE `backend/intelligence/models/route_ranker.py` (DUPLICATE)
- [ ] DELETE `backend/intelligence/models/cancellation.py` (DUPLICATE)
- [ ] DELETE `backend/intelligence/models/demand.py` (DUPLICATE)
- [ ] DELETE `backend/core/ml_ranking_model.py` (consolidate to services)
- [ ] GIT COMMIT: "Delete duplicate ML models from intelligence/"

### Step 5: Verify ML Integration (backend/core/ml_integration.py)
- [ ] READ `backend/core/ml_integration.py`
- [ ] VERIFY MLModelRegistry class
- [ ] VERIFY FeatureEngineer class
- [ ] VERIFY model loading mechanism
- [ ] VERIFY fallback handling
- [ ] ADD registration for all predictors
- [ ] ADD registration for reliability model
- [ ] TEST registry functionality
- [ ] RUN unit tests
- [ ] GIT COMMIT: "Enhance ML integration registry"

### Step 6: Verify ML Reliability Model (backend/ml_reliability_model.py)
- [ ] READ `backend/ml_reliability_model.py`
- [ ] VERIFY ReliabilityModel functionality
- [ ] VERIFY integration with route engine
- [ ] VERIFY ML fallback mechanism
- [ ] RUN unit tests
- [ ] REGISTER in ML registry
- [ ] GIT COMMIT: "Verify ML reliability model"

### Step 7: Verify ML Feature Store Schema (backend/ml_feature_store_schema.sql)
- [ ] READ schema file
- [ ] VERIFY tables and columns
- [ ] VERIFY indexes
- [ ] TEST database creation
- [ ] DOCUMENT schema

### Step 8: Update All ML Imports
- [ ] FIND all imports from `backend.intelligence.models.*` (DUPLICATE)
- [ ] REPLACE with `backend.services.*` (CANONICAL)
- [ ] FIND all imports from `backend.ml_data_collection`
- [ ] REPLACE with `backend.intelligence.training.data_collection`
- [ ] FIND all imports from `backend.ml_training_pipeline`
- [ ] REPLACE with `backend.intelligence.training.pipeline`
- [ ] FIND all imports from `backend.core.ml_ranking_model`
- [ ] REPLACE with `backend.services.route_ranking_predictor`
- [ ] RUN full test suite
- [ ] GIT COMMIT: "Update all ML imports"

### Step 9: Delete Remaining Root ML Files
- [ ] DELETE `backend/ml_data_collection.py` (already moved)
- [ ] DELETE `backend/ml_training_pipeline.py` (already moved)
- [ ] DELETE `backend/setup_ml_database.py` (already moved)
- [ ] VERIFY wrapper scripts in `backend/scripts/` still work
- [ ] GIT COMMIT: "Delete root ML files (moved to intelligence/)"

### Step 10: Verify All ML Services Integrated
- [ ] VERIFY all predictors in services/
- [ ] VERIFY all predictors registered in ml_integration
- [ ] VERIFY all training code in intelligence/training/
- [ ] VERIFY all scripts in backend/scripts/
- [ ] TEST end-to-end ML pipeline
- [ ] GIT COMMIT: "Complete ML integration"

### ML Final Actions
- [ ] CREATE comprehensive ML test suite
- [ ] TEST all predictors end-to-end
- [ ] TEST ML pipeline (collect → train → predict)
- [ ] TEST model loading and fallback
- [ ] TEST registry functionality
- [ ] PERFORMANCE TEST (inference latency < 50ms)
- [ ] VERIFY no import cycles
- [ ] Update architecture documentation
- [ ] GIT COMMIT: "Complete ML/Intelligence consolidation"

---

## PHASE 13: FINAL CLEANUP & VALIDATION

### Final Archive Cleanup
- [ ] DELETE all remaining `backend/archive/` folders
  - [ ] VERIFY all consolidation complete before deleting
  - [ ] ENSURE git history preserved
  - [ ] GIT COMMIT: "Clean up archive folder"

### Final Import Audit
- [ ] GREP for any remaining imports from deleted files
- [ ] GREP for any circular imports
- [ ] GREP for any relative imports to deleted modules
- [ ] FIX any issues found
- [ ] GIT COMMIT: "Fix remaining imports"

### Final Directory Structure Verification
- [ ] VERIFY `backend/core/` structure correct
- [ ] VERIFY `backend/domains/` structure correct
- [ ] VERIFY `backend/platform/` structure correct
- [ ] VERIFY `backend/services/` structure correct
- [ ] VERIFY `backend/intelligence/` structure correct
- [ ] VERIFY `backend/scripts/` structure correct
- [ ] VERIFY `backend/archive/` contains only v1 (reference)

### Final Test Suite
- [ ] RUN complete unit test suite
- [ ] RUN complete integration test suite
- [ ] RUN end-to-end test suite
- [ ] PERFORMANCE TEST all services (latency, throughput)
- [ ] LOAD TEST all services (concurrent users, data volume)
- [ ] STRESS TEST (peak load scenarios)
- [ ] FIX any failures
- [ ] GIT COMMIT: "All tests passing"

### Final Documentation
- [ ] UPDATE backend/core/README.md
- [ ] UPDATE backend/domains/README.md
- [ ] UPDATE backend/platform/README.md
- [ ] UPDATE backend/services/README.md
- [ ] UPDATE backend/intelligence/README.md
- [ ] UPDATE main architecture documentation
- [ ] CREATE consolidation summary document
- [ ] DOCUMENT canonical file locations
- [ ] DOCUMENT import patterns
- [ ] GIT COMMIT: "Update architecture documentation"

### Final Code Quality
- [ ] RUN linter (flake8/pylint)
- [ ] RUN type checker (mypy)
- [ ] RUN security scanner
- [ ] FIX any issues
- [ ] GIT COMMIT: "Code quality fixes"

### Final Verification
- [ ] VERIFY no broken imports
- [ ] VERIFY no circular dependencies
- [ ] VERIFY all tests passing
- [ ] VERIFY performance targets met
- [ ] VERIFY database integrity
- [ ] VERIFY config consistency
- [ ] CREATE final status report
- [ ] GIT COMMIT: "Consolidation complete - All systems go"

---

## SUMMARY OF EXECUTION

### Total Action Items: 147
### Phases: 13

**Time Estimates:**
- Phase 1 (Route Engines): 2-3 days
- Phase 2 (Seat Allocation): 2-3 days
- Phase 3 (Pricing): 2-3 days
- Phase 4 (Caching): 1-2 days
- Phase 5 (Booking): 1-2 days
- Phase 6 (Payment): 1-2 days
- Phase 7 (Station): 1 day
- Phase 8 (User Management): 2-3 days
- Phase 9 (Verification): 1 day
- Phase 10 (Events): 1 day
- Phase 11 (Graph): 1 day
- Phase 12 (ML/Intelligence): 3-4 days
- Phase 13 (Cleanup & Validation): 2-3 days

**Total Estimated Time: 2-3 weeks**

### Key Success Criteria
1. ✓ All 47+ duplicate files consolidatedinto canonical versions
2. ✓ All tests passing (unit, integration, E2E)
3. ✓ All performance targets met
4. ✓ No broken imports or circular dependencies
5. ✓ Complete feature parity with archived versions
6. ✓ 40-50% code duplication eliminated
7. ✓ Architecture documentation updated
8. ✓ Git history preserved for audit trail

---

**Status: READY FOR EXECUTION**
**Next Step: BEGIN PHASE 1 - Route Engines**
**Execution Start Date: 2026-02-20**

