# Backend Implementation Roadmap
## IRCTC-Inspired Advanced System - Production Deployment Plan

**Document Date:** February 17, 2026  
**Timeline:** 10 Weeks to Full Production  
**Target:** Production-grade multi-modal routing system with 99.9% uptime

---

## PHASE 0: FOUNDATION (Week 1-2)

### Objectives
- Set up infrastructure
- Prepare databases
- Deploy basic services

### Tasks

#### 0.1 Infrastructure Setup (3 days)
- [ ] Set up Kubernetes cluster (or Docker Compose for dev)
- [ ] Configure PostgreSQL 14+ with PostGIS
- [ ] Set up Redis cluster (3+ nodes)
- [ ] Configure Kafka brokers (3+ nodes)
- [ ] Set up Prometheus + Grafana
- [ ] Configure Elasticsearch + Kibana for logging

**Commands:**
```bash
# Initialize PostgreSQL with PostGIS
docker run -d \
  -e POSTGRES_PASSWORD=secure_pass \
  -e POSTGRES_DB=routedb \
  -p 5432:5432 \
  postgis/postgis:14-3.3

# Verify PostGIS
psql -U postgres -d routedb -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# Initialize Redis
docker run -d -p 6379:6379 redis:7-alpine

# Kafka setup
docker-compose -f docker-compose.kafka.yml up -d
```

#### 0.2 Database Schema (3 days)
- [ ] Run GTFS-based migrations
- [ ] Create all tables (stations, stops, trips, transfers, bookings)
- [ ] Create indexes for performance
- [ ] Set up table partitioning for scalability
- [ ] Create stored procedures for complex queries

**Code:**
```sql
-- Run migrations in order:
-- 1. GTFS tables
-- 2. Booking tables
-- 3. Real-time tables
-- 4. ML/RL tables
-- 5. Indexes and partitioning

alembic upgrade head

-- Verify schema
\dt  -- List all tables
```

#### 0.3 Backend Skeleton (2 days)
- [ ] Set up FastAPI project structure
- [ ] Configure environment variables
- [ ] Set up logging and monitoring
- [ ] Create base service classes
- [ ] Write health check endpoints

**Structure:**
```
backend/
├── app.py
├── config.py
├── database.py
├── models.py
├── schemas.py
├── api/
│   ├── __init__.py
│   ├── health.py
│   ├── routes.py
│   ├── bookings.py
│   ├── admin.py
│   └── ml.py
├── services/
│   ├── route_engine.py
│   ├── advanced_route_engine.py
│   ├── booking_service.py
│   ├── inventory_service.py
│   ├── pricing_service.py
│   ├── ml_service.py
│   └── realtime_processor.py
├── utils/
│   ├── cache.py
│   ├── metrics.py
│   └── helpers.py
└── tests/
    ├── test_route_engine.py
    ├── test_booking.py
    └── conftest.py
```

### Deliverables
- ✅ Running Kubernetes cluster
- ✅ PostgreSQL with GTFS schema
- ✅ Redis cache layer
- ✅ Monitoring stack (Prometheus/Grafana)
- ✅ Basic FastAPI service

### Success Criteria
- [ ] `GET /health` returns 200
- [ ] Database has all 15+ tables
- [ ] Grafana accessible at localhost:3000

---

## PHASE 1: CORE ROUTE ENGINE (Week 3-4)

### Objectives
- Implement RAPTOR algorithm
- Deploy station & network service
- Set up real-time graph

### Tasks

#### 1.1 RAPTOR Implementation (5 days)
- [ ] Implement RAPTOR router class
- [ ] Integrate with GTFS data
- [ ] Add transfer logic (Set A & B intersection)
- [ ] Optimize for performance
- [ ] Add comprehensive logging

**Code Location:** `backend/services/advanced_route_engine.py` (Already provided!)

**Test:**
```python
# test_route_engine.py
def test_raptor_basic_route():
    raptor = RaptorRouter(network_service, db_session, transfer_validator)
    
    source = network_service.get_stop_by_code('NDLS')
    dest = network_service.get_stop_by_code('CSTM')
    
    route = raptor.find_shortest_path(
        source,
        dest,
        departure_time=datetime(2026, 2, 20, 10, 0),
        max_transfers=3
    )
    
    assert route is not None
    assert route.num_transfers <= 3
    assert route.departure_time >= datetime(2026, 2, 20, 10, 0)
```

#### 1.2 Station & Network Service (3 days)
- [ ] Create NetworkService class
- [ ] Implement stop/station queries
- [ ] Add trip lookup methods
- [ ] Implement transfer validation
- [ ] Add caching layer

```python
# backend/services/network_service.py
class NetworkService:
    def __init__(self, db: Session, cache: Redis):
        self.db = db
        self.cache = cache
    
    def get_stop(self, stop_id: int) -> Stop:
        """Get stop by ID with caching."""
        cache_key = f"stop:{stop_id}"
        cached = self.cache.get(cache_key)
        if cached:
            return Stop(**json.loads(cached))
        
        stop = self.db.query(models.Stop).filter(models.Stop.id == stop_id).first()
        if stop:
            self.cache.setex(cache_key, 3600, json.dumps(stop.to_dict()))
        return stop
    
    def get_trips_from_stop(
        self,
        stop_id: int,
        travel_date: datetime,
        mode_filters: Optional[List[TransportMode]] = None
    ) -> List[Trip]:
        """Get all trips departing from stop on given date."""
        # Query database
        stop_times = self.db.query(models.StopTime).filter(
            models.StopTime.stop_id == stop_id,
            models.StopTime.departure_time >= travel_date
        ).all()
        
        # Build Trip objects
        trip_ids = set(st.trip_id for st in stop_times)
        trips = []
        for trip_id in trip_ids:
            trip = self.db.query(models.Trip).filter(
                models.Trip.id == trip_id
            ).first()
            
            if mode_filters and trip.mode not in mode_filters:
                continue
            
            trips.append(self._trip_to_domain_model(trip))
        
        return trips
    
    def get_all_stops(self) -> Dict[int, Stop]:
        """Cache all stops for graph construction."""
        cache_key = "all_stops"
        cached = self.cache.get(cache_key)
        if cached:
            return json.loads(cached)
        
        stops_data = {}
        for stop in self.db.query(models.Stop).all():
            stops_data[stop.id] = stop.to_dict()
        
        self.cache.setex(cache_key, 3600, json.dumps(stops_data))
        return stops_data
```

#### 1.3 Route Search API (3 days)
- [ ] Create `/api/v1/routes/search` endpoint
- [ ] Implement query validation
- [ ] Add caching logic
- [ ] Set up response serialization
- [ ] Add performance logging

```python
# backend/api/routes.py
@router.post("/api/v1/routes/search", response_model=RouteSearchResponse)
async def search_routes(
    request: RouteSearchRequest,
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_cache)
):
    """
    Search routes from source to destination.
    """
    start_time = time.time()
    
    try:
        # Create engine
        engine = AdvancedRouteEngine(db, cache, network_service)
        
        # Search
        result = engine.search_routes(
            source=request.source,
            destination=request.destination,
            travel_date=request.travel_date,
            num_passengers=request.num_passengers,
            max_transfers=request.max_transfers,
            num_alternatives=request.num_alternatives
        )
        
        # Add metrics
        elapsed_ms = (time.time() - start_time) * 1000
        result['search_time_ms'] = elapsed_ms
        
        # Log metrics
        prometheus.route_search_latency.observe(elapsed_ms)
        
        return result
    
    except Exception as e:
        logger.error(f"Route search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

#### 1.4 Performance Benchmarking (2 days)
- [ ] Load test route search (target: <500ms)
- [ ] Test with 100K+ stops
- [ ] Profile RAPTOR algorithm
- [ ] Optimize hot paths
- [ ] Document bottlenecks

**Benchmark Script:**
```python
import time
import asyncio

async def benchmark_route_search():
    routes_searched = 0
    total_time = 0
    
    for _ in range(100):
        start = time.time()
        
        result = await search_routes(
            source='NDLS',
            destination='CSTM',
            travel_date=datetime(2026, 2, 20)
        )
        
        elapsed = time.time() - start
        total_time += elapsed
        routes_searched += len(result['routes'])
    
    avg_time_ms = (total_time / 100) * 1000
    print(f"Average search time: {avg_time_ms:.2f}ms")
    print(f"Average routes per search: {routes_searched / 100:.0f}")
    
    assert avg_time_ms < 500, "Target: <500ms"
```

### Deliverables
- ✅ RAPTOR router working
- ✅ Network service with caching
- ✅ Route search API
- ✅ Performance benchmarks

### Success Criteria
- [ ] Route search latency < 500ms
- [ ] Returns 5+ alternative routes
- [ ] Handles transfers correctly
- [ ] Cache hit rate > 70%

---

## PHASE 2: BOOKING & INVENTORY (Week 5-6)

### Objectives
- Implement seat allocation
- Build booking management
- Set up payment integration

### Tasks

#### 2.1 Inventory Management (4 days)
- [ ] Create SeatInventoryManager class
- [ ] Implement fair seat allocation
- [ ] Add overbooking logic
- [ ] Set up waitlist management
- [ ] Create inventory reconciliation job

```python
# backend/services/inventory_service.py
class InventoryManager:
    def __init__(self, db: Session, cache: Redis):
        self.db = db
        self.cache = cache
    
    def allocate_seats(self, booking_request, num_passengers):
        """Allocate seats fairly."""
        # Validate availability
        available = self.get_available_seats(booking_request.trip_id)
        
        if len(available) < num_passengers:
            # Add to waitlist
            return self._add_to_waitlist(booking_request, num_passengers)
        
        # Fair allocation (distributed across coaches)
        allocated = self._fair_allocation(available, num_passengers)
        
        # Reserve seats
        for seat in allocated:
            self.db.execute(
                "UPDATE seat_inventory SET seats_available = seats_available - 1 WHERE trip_id = %s",
                (booking_request.trip_id,)
            )
        
        return allocated
    
    def process_waitlist_confirmation(self):
        """Confirm waitlisted passengers periodically."""
        waitlist = self.db.query(Booking).filter(
            Booking.status == 'WAITLIST'
        ).order_by(Booking.created_at).limit(100).all()
        
        for booking in waitlist:
            available = self.get_available_seats(booking.trip_id)
            
            if len(available) >= booking.num_passengers:
                booking.status = 'CONFIRMED'
                # Send confirmation notification
                notify_user(booking.user_id, booking.id)
        
        self.db.commit()
```

#### 2.2 Booking Service (3 days)
- [ ] Create BookingService class
- [ ] Implement PNR generation
- [ ] Add booking validation
- [ ] Set up cancellation logic
- [ ] Create booking search endpoint

```python
# backend/services/booking_service.py
class BookingService:
    def __init__(self, db: Session, inventory_mgr, payment_svc):
        self.db = db
        self.inventory = inventory_mgr
        self.payment = payment_svc
    
    async def create_booking(self, request: BookingRequest) -> BookingResponse:
        """Create new booking."""
        try:
            # 1. Allocate seats
            seats = self.inventory.allocate_seats(request, len(request.passengers))
            
            # 2. Create booking
            booking = models.Booking(
                user_id=request.user_id,
                trip_id=request.trip_id,
                travel_date=request.travel_date,
                booking_details={'seats': seats},
                status='PENDING'
            )
            
            # 3. Process payment
            payment = await self.payment.process_payment(
                user_id=request.user_id,
                amount=request.total_fare,
                payment_method=request.payment_method
            )
            
            if payment['status'] != 'SUCCESS':
                # Release seats
                self.inventory.release_seats(seats)
                return BookingResponse(status='PAYMENT_FAILED')
            
            # 4. Confirm booking
            booking.status = 'CONFIRMED'
            booking.pnr_number = self._generate_pnr(booking)
            
            self.db.add(booking)
            self.db.commit()
            
            # 5. Send confirmation
            await send_booking_confirmation(booking)
            
            return BookingResponse(
                booking_id=booking.id,
                pnr=booking.pnr_number,
                status='CONFIRMED'
            )
        
        except Exception as e:
            self.db.rollback()
            logger.error(f"Booking failed: {e}")
            raise
    
    def _generate_pnr(self, booking) -> str:
        """Generate 10-char PNR: 6 alphanumeric + 4 numeric."""
        timestamp = int(booking.created_at.timestamp())
        base = hashlib.md5(
            f"{booking.user_id}{booking.id}{timestamp}".encode()
        ).hexdigest()[:6].upper()
        
        checksum = str(timestamp % 10000).zfill(4)
        return base + checksum
```

#### 2.3 Payment Integration (3 days)
- [ ] Set up Razorpay/Stripe
- [ ] Create PaymentService
- [ ] Implement payment verification
- [ ] Add refund logic
- [ ] Set up webhook handlers

```python
# backend/services/payment_service.py
class PaymentService:
    def __init__(self, razorpay_key_id, razorpay_key_secret):
        self.client = razorpay.Client(
            auth=(razorpay_key_id, razorpay_key_secret)
        )
    
    async def process_payment(self, user_id: str, amount: float, payment_method: str):
        """Process payment and return confirmation."""
        try:
            # Create order
            order = self.client.order.create(data={
                'amount': int(amount * 100),  # Convert to paise
                'currency': 'INR',
                'receipt': f'booking_{user_id}_{time.time()}'
            })
            
            return {
                'status': 'PENDING',
                'order_id': order['id'],
                'amount': amount,
                'currency': 'INR'
            }
        
        except Exception as e:
            logger.error(f"Payment failed: {e}")
            return {
                'status': 'FAILED',
                'error': str(e)
            }
    
    async def verify_payment(self, razorpay_payment_id, razorpay_signature, order_id):
        """Verify payment signature and confirm."""
        try:
            self.client.utility.verify_payment_signature({
                'razorpay_order_id': order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            })
            
            return {
                'status': 'SUCCESS',
                'payment_id': razorpay_payment_id
            }
        except Exception as e:
            logger.error(f"Payment verification failed: {e}")
            return {
                'status': 'FAILED',
                'error': 'Invalid signature'
            }
```

#### 2.4 API Endpoints (2 days)
- [ ] POST /api/v1/bookings (create)
- [ ] GET /api/v1/bookings/{id} (retrieve)
- [ ] POST /api/v1/bookings/{id}/cancel (cancel)
- [ ] GET /api/v1/bookings (list user bookings)

### Deliverables
- ✅ Seat allocation working
- ✅ Booking creation working
- ✅ Payment integration complete
- ✅ PNR generation working

### Success Criteria
- [ ] Booking creation < 2 seconds
- [ ] Seat availability updates in real-time
- [ ] Waitlist auto-confirmation working
- [ ] Payment success rate > 99%

---

## PHASE 3: REAL-TIME UPDATES (Week 7)

### Objectives
- Implement real-time train updates
- Build graph mutation engine
- Set up event streaming

### Tasks

#### 3.1 Real-Time Data Processing (3 days)
- [ ] Implement Kafka consumers
- [ ] Create event processors
- [ ] Add delay handling logic
- [ ] Implement cancellation logic
- [ ] Set up alerts

```python
# backend/services/realtime_processor.py
class RealtimeProcessor:
    async def process_train_delay_event(self, event):
        """Handle train delay event."""
        train_id = event['train_id']
        delay_minutes = event['delay_minutes']
        
        # 1. Update train state
        train_state = models.TrainState(
            train_number=train_id,
            delay_minutes=delay_minutes,
            status='delayed' if delay_minutes > 5 else 'on_time'
        )
        self.db.add(train_state)
        
        # 2. Trigger graph mutation
        if delay_minutes > 15:
            graph_mutation_engine.handle_train_delay(
                train_id, delay_minutes
            )
        
        # 3. Notify affected users
        bookings = self.db.query(models.Booking).filter(
            models.Booking.trip_id == train_id
        ).all()
        
        for booking in bookings:
            await notify_user(
                booking.user_id,
                f'Train {train_id} delayed by {delay_minutes} minutes'
            )
        
        # 4. Publish update to WebSocket
        await broadcast_train_update(train_id, train_state)
```

#### 3.2 Graph Mutation Engine (4 days)
Already provided in architecture! Implement:
- [ ] Train delay handling
- [ ] Cancellation handling
- [ ] Diversion routes
- [ ] Cache invalidation
- [ ] Version tracking

```python
# backend/services/graph_mutation_engine.py (from architecture)
# Copy implementation from IRCTC_INSPIRED_BACKEND_ARCHITECTURE.md
```

### Deliverables
- ✅ Real-time event processing
- ✅ Graph mutation working
- ✅ WebSocket updates
- ✅ User notifications

### Success Criteria
- [ ] Event processing < 100ms
- [ ] Graph updates within 5 seconds
- [ ] Users notified within 10 seconds
- [ ] Cache invalidation correct

---

## PHASE 4: ML/RL INTEGRATION (Week 8)

### Objectives
- Implement ML ranking
- Set up demand prediction
- Build dynamic pricing

### Tasks

#### 4.1 ML Service Setup (3 days)
- [ ] Create MLService class
- [ ] Implement feature extraction
- [ ] Load pre-trained models
- [ ] Set up inference pipeline
- [ ] Add model versioning

```python
# backend/services/ml_service.py
class MLService:
    def __init__(self, model_registry_path):
        self.models = self._load_models(model_registry_path)
    
    def rank_routes(self, routes, user_profile, context):
        """Rank routes using ML model."""
        # Extract features
        features = []
        for route in routes:
            f = self._extract_features(route, user_profile, context)
            features.append(f)
        
        # Predict scores
        scores = self.models['route_ranker'].predict(np.array(features))
        
        # Rank
        ranked = sorted(
            zip(routes, scores),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [r for r, _ in ranked]
    
    def predict_demand(self, route, travel_date):
        """Predict demand for route."""
        features = self._extract_demand_features(route, travel_date)
        demand_score = self.models['demand_predictor'].predict(
            np.array([features])
        )[0]
        
        return demand_score  # 0 to 1
```

#### 4.2 Dynamic Pricing (3 days)
- [ ] Create PricingEngine
- [ ] Implement demand-based pricing
- [ ] Add occupancy-based surge
- [ ] Set up ML optimization
- [ ] Create pricing API

```python
# backend/services/pricing_service.py
class PricingService:
    def __init__(self, ml_service):
        self.ml = ml_service
    
    def calculate_dynamic_price(self, route, booking_date):
        """Calculate dynamic price based on multiple factors."""
        base_price = self._get_base_price(route)
        
        # Factors
        demand = self.ml.predict_demand(route, booking_date)
        occupancy = self._get_occupancy_rate(route)
        
        # Multipliers
        demand_mult = 1.0 + (demand - 0.5) * 0.4  # -20% to +20%
        occupancy_mult = 1.0 + (occupancy ** 1.5) * 0.3  # 0-30%
        
        # Combined
        dynamic_price = base_price * demand_mult * occupancy_mult
        
        # Bounds
        dynamic_price = max(base_price * 0.8, dynamic_price)
        dynamic_price = min(base_price * 1.5, dynamic_price)
        
        return dynamic_price
```

#### 4.3 Feedback Loop (2 days)
- [ ] Create feedback logging
- [ ] Set up async model training
- [ ] Implement online learning
- [ ] Add A/B testing framework

### Deliverables
- ✅ ML ranking working
- ✅ Demand prediction working
- ✅ Dynamic pricing working
- ✅ Feedback collection

### Success Criteria
- [ ] Ranking inference < 200ms
- [ ] Prediction accuracy > 75%
- [ ] Revenue increase > 5%

---

## PHASE 5: MULTI-MODAL SUPPORT (Week 9)

### Objectives
- Add bus support
- Add flight support
- Integrate multi-modal routing

### Tasks

#### 5.1 Bus Integration (2 days)
- [ ] Create Bus adapter
- [ ] Implement bus route parsing
- [ ] Add bus-specific seat types
- [ ] Integrate with routing

#### 5.2 Flight Integration (2 days)
- [ ] Create Flight adapter
- [ ] Implement flight schedule parsing
- [ ] Add flight seat classes
- [ ] Integrate with routing

#### 5.3 Multi-Modal Routing (3 days)
- [ ] Update transfer logic for modes
- [ ] Implement mode-specific costs
- [ ] Add mode filtering
- [ ] Test multi-mode routes

```python
# backend/services/multi_modal_route_engine.py
class MultiModalRouteEngine(AdvancedRouteEngine):
    """Extended route engine supporting multiple modes."""
    
    def __init__(self, db, redis, network_service):
        super().__init__(db, redis, network_service)
        self.mode_handlers = {
            TransportMode.TRAIN: TrainHandler(),
            TransportMode.BUS: BusHandler(),
            TransportMode.FLIGHT: FlightHandler(),
        }
    
    def search_routes_multi_modal(
        self,
        source: str,
        destination: str,
        travel_date: datetime,
        allowed_modes: List[TransportMode] = None
    ):
        """Search allowing multiple modes and transfers between them."""
        # Search with mode filters
        if allowed_modes is None:
            allowed_modes = [
                TransportMode.TRAIN,
                TransportMode.BUS,
                TransportMode.FLIGHT
            ]
        
        return self.search_routes(
            source=source,
            destination=destination,
            travel_date=travel_date,
            mode_filters=allowed_modes
        )
```

### Deliverables
- ✅ Bus routing working
- ✅ Flight routing working
- ✅ Multi-modal search working
- ✅ Transfer logic updated

---

## PHASE 6: PRODUCTION HARDENING (Week 10)

### Objectives
- Load testing
- Security audit
- Performance optimization
- Documentation

### Tasks

#### 6.1 Load Testing (2 days)
- [ ] Create load test suite
- [ ] Test 1000 concurrent searches
- [ ] Test booking surge
- [ ] Identify bottlenecks
- [ ] Optimize hot paths

```bash
# Load test with locust
locust -f tests/load_test.py --host=http://localhost:8000
```

#### 6.2 Security (2 days)
- [ ] SQL injection prevention ✅ (SQLAlchemy ORM)
- [ ] CSRF protection
- [ ] Rate limiting
- [ ] API authentication
- [ ] Data encryption

#### 6.3 Monitoring (2 days)
- [ ] Set up alerts
- [ ] Create dashboards
- [ ] Add health checks
- [ ] Set up SLO tracking

#### 6.4 Documentation (1 day)
- [ ] API documentation (FastAPI docs)
- [ ] Deployment guide
- [ ] Operation manual
- [ ] Troubleshooting guide

### Deliverables
- ✅ Load tests passing
- ✅ Security audit passed
- ✅ Monitoring working
- ✅ Documentation complete

---

## TIMELINE SUMMARY

```
Week 1-2:  Foundation Setup ████████░░░░░░░░░░░░ 40%
Week 3-4:  Route Engine    ████████████████░░░░░ 80%
Week 5-6:  Booking System  ████████████████████░ 100%
Week 7:    Real-time       ████████████░░░░░░░░░ 60%
Week 8:    ML/RL          ████████████░░░░░░░░░ 60%
Week 9:    Multi-Modal     ████████░░░░░░░░░░░░░ 40%
Week 10:   Production      ████████████████░░░░░ 80%

Total: 10 weeks → Production Ready ✅
```

---

## SUCCESS METRICS

### Performance Targets
- Route search latency: < 500ms (p99)
- Booking creation: < 2 seconds
- Payment success: > 99%
- Seat availability: Real-time (< 1 second)
- Graph mutation: < 5 seconds

### Reliability Targets
- Uptime: 99.9%
- Error rate: < 0.1%
- Data consistency: 100%
- Recovery time (RTO): < 1 hour

### Business Targets
- Revenue increase: > 5% from dynamic pricing
- Customer satisfaction: > 4.5/5
- Operational efficiency: > 20% improvement

---

## NEXT STEPS

1. **Review this roadmap** with your team
2. **Assign owners** for each phase
3. **Set up infrastructure** (Week 1)
4. **Start Phase 1** (Route Engine)
5. **Integrate RouteMaster Agent** (Week 5+)
6. **Deploy to production** (Week 11+)

**Questions?** Refer to:
- `IRCTC_INSPIRED_BACKEND_ARCHITECTURE.md` - Design details
- `ROUTEMASTER_BACKEND_INTEGRATION_GUIDE.md` - Agent integration
- `backend/services/advanced_route_engine.py` - Core implementation

---

**Ready to build the future of railway and multi-modal transportation?**

Let's go! 🚀
