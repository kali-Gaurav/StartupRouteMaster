# RouteMaster Agent ↔ Backend Integration Guide

**Version:** 2.0  
**Date:** February 17, 2026  
**Purpose:** Connect RouteMaster Agent's autonomous intelligence with the IRCTC-inspired backend system

---

## OVERVIEW

The RouteMaster Agent acts as the **intelligent autonomous collector and optimizer** while the backend provides the **high-performance computation engine**.

```
┌─────────────────────────────────────┐
│   RouteMaster Agent                 │
│   (Autonomous Intelligence)         │
│ - Scrape IRCTC real-time data      │
│ - Process web pages with Vision AI  │
│ - Extract schedules/prices          │
│ - Predict demand patterns           │
│ - Make intelligent decisions        │
└────────────┬────────────────────────┘
             │ (APIs)
             ▼
┌─────────────────────────────────────┐
│   Backend System                    │
│   (Computation & Storage)           │
│ - RAPTOR route search               │
│ - Real-time graph mutation          │
│ - Booking management                │
│ - ML/RL ranking                     │
│ - Dynamic pricing                   │
└─────────────────────────────────────┘
```

---

## 1. DATA COLLECTION PIPELINE

### 1.1 Autonomous Schedule Collection

**RouteMaster Agent does:**
```python
# In routemaster_agent/tasks/train_scheduler.py
class TrainScheduleCollectorTask:
    async def execute(self):
        # 1. Visit IRCTC/partner sites
        schedules = await self.vision_ai.extract_train_schedules()
        
        # 2. Parse with extraction AI
        parsed = await self.extraction_ai.extract_structured_data(
            html=schedules,
            schema=TrainScheduleSchema
        )
        
        # 3. Validate data
        validated = self.decision_engine.validate_data(parsed)
        
        # 4. Push to backend
        response = await self.backend_client.bulk_insert_trips(validated)
        
        # 5. Log feedback for learning
        self.ml_feedback.log_data_collection({
            'source': 'irctc_scraper',
            'records': len(validated),
            'success_rate': response['success_rate']
        })
```

**Backend receives:**
```python
# In backend/api/routes.py
@router.post("/api/v1/admin/bulk-insert-trips")
async def bulk_insert_trips(request: BulkInsertRequest, db: Session = Depends(get_db)):
    """
    Bulk insert trips scraped by RouteMaster Agent.
    Called by agent after extracting from IRCTC.
    """
    inserted_count = 0
    errors = []
    
    try:
        for trip_data in request.trips:
            # 1. Validate GTFS format
            if not validate_gtfs_trip(trip_data):
                errors.append(f"Invalid GTFS: {trip_data['trip_id']}")
                continue
            
            # 2. Upsert trip
            trip = Trip(
                trip_id=trip_data['trip_id'],
                route_id=trip_data['route_id'],
                service_id=trip_data['service_id'],
                mode=trip_data['mode'],
                train_number=trip_data.get('train_number')
            )
            
            # 3. Insert stop times
            for stop_data in trip_data['stop_times']:
                stop_time = StopTime(
                    trip_id=trip.id,
                    stop_id=stop_data['stop_id'],
                    arrival_time=stop_data['arrival_time'],
                    departure_time=stop_data['departure_time'],
                    stop_sequence=stop_data['sequence']
                )
                db.add(stop_time)
            
            db.add(trip)
            inserted_count += 1
            
            # 4. Every N inserts, commit
            if inserted_count % 100 == 0:
                db.commit()
                logger.info(f"Committed {inserted_count} trips")
        
        db.commit()
        
        # 5. Invalidate route search cache
        redis_client.delete('routes:*')
        
        return {
            'success': True,
            'inserted': inserted_count,
            'errors': errors,
            'message': f'Inserted {inserted_count} trips successfully'
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"Bulk insert failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### 1.2 Real-Time Updates (Train Position, Delays)

**RouteMaster Agent:**
```python
# In routemaster_agent/tasks/realtime_monitor.py
class RealtimeTrainMonitor:
    async def update_train_positions(self):
        """
        Continuously monitor train positions and update backend.
        """
        while True:
            try:
                # 1. Scrape current positions
                positions = await self.vision_ai.extract_train_positions()
                
                # 2. Update backend with real-time data
                for train_id, location_data in positions.items():
                    await self.backend_client.update_train_state(
                        train_id=train_id,
                        location=location_data['location'],
                        delay_minutes=location_data['delay'],
                        occupancy_rate=location_data['occupancy'],
                        timestamp=datetime.utcnow()
                    )
                
                # 3. Process feedback
                self.ml_feedback.log_realtime_update({
                    'trains_updated': len(positions),
                    'timestamp': datetime.utcnow()
                })
                
                # Wait before next update
                await asyncio.sleep(60)  # Every minute
                
            except Exception as e:
                logger.error(f"Realtime update failed: {e}")
                await asyncio.sleep(300)  # Retry after 5 min
```

**Backend receives:**
```python
# In backend/api/routes.py
@router.post("/api/v1/admin/update-train-state")
async def update_train_state(request: TrainStateUpdate, db: Session = Depends(get_db)):
    """
    Real-time train state update from RouteMaster Agent.
    """
    try:
        # 1. Get or create train state
        train_state = db.query(TrainState).filter(
            TrainState.train_number == request.train_id
        ).first()
        
        if not train_state:
            train_state = TrainState(train_number=request.train_id)
        
        # 2. Update state
        train_state.delay_minutes = request.delay_minutes
        train_state.occupancy_rate = request.occupancy_rate
        train_state.last_updated = request.timestamp
        train_state.status = 'delayed' if request.delay_minutes > 5 else 'on_time'
        
        # 3. If delay significant, trigger graph mutation
        if request.delay_minutes > 15:
            affected_stops = db.query(StopTime).filter(
                StopTime.trip_id == train_state.trip_id
            ).all()
            
            graph_mutation_engine.handle_train_delay(
                train_id=request.train_id,
                delay_minutes=request.delay_minutes,
                affected_stations=[st.stop_id for st in affected_stops]
            )
        
        db.add(train_state)
        db.commit()
        
        return {
            'success': True,
            'train_id': request.train_id,
            'message': f'Updated train state with {request.delay_minutes} min delay'
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"Train state update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 2. PRICING & DEMAND OPTIMIZATION

### 2.1 Data-Driven Pricing

**RouteMaster Agent:**
```python
# In routemaster_agent/intelligence/pricing_optimizer.py
class PricingOptimizer:
    async def optimize_prices_for_routes(self):
        """
        Periodically optimize prices based on predicted demand.
        """
        # 1. Get upcoming routes (next 7 days)
        upcoming = await self.backend_client.get_upcoming_routes()
        
        # 2. For each route, predict demand
        for route in upcoming:
            # Collect features
            historical_demand = await self.data_store.get_demand_history(
                origin=route['source'],
                destination=route['destination'],
                days_back=90
            )
            
            # Predict demand using RL models
            demand_score = self.rl_agent.predict_demand(
                route=route,
                historical_data=historical_demand
            )
            
            # Calculate optimal price
            optimal_price = self._calculate_optimal_price(
                base_price=route['base_price'],
                demand_score=demand_score,
                occupancy=route['current_occupancy'],
                days_until_travel=route['days_until_travel']
            )
            
            # Push optimization to backend
            await self.backend_client.update_pricing_rule(
                route_id=route['id'],
                optimal_price=optimal_price,
                rationale={
                    'demand_score': demand_score,
                    'algorithm': 'rl_optimization',
                    'timestamp': datetime.utcnow()
                }
            )
    
    def _calculate_optimal_price(
        self,
        base_price: float,
        demand_score: float,  # 0 to 1
        occupancy: float,      # 0 to 1
        days_until_travel: int
    ) -> float:
        """
        Revenue management: optimize price based on multiple factors.
        """
        # Dynamic pricing factors
        demand_multiplier = 1.0 + (demand_score - 0.5) * 0.4  # -20% to +20%
        occupancy_multiplier = 1.0 + (occupancy ** 1.5) * 0.3  # 0-30% surge
        
        # Closer to travel date = higher price
        days_multiplier = 1.0 + (10 - min(days_until_travel, 10)) * 0.05
        
        # Combined
        optimal_price = base_price * demand_multiplier * occupancy_multiplier * days_multiplier
        
        # Bounds
        optimal_price = max(base_price * 0.8, optimal_price)  # Don't go below 80%
        optimal_price = min(base_price * 1.5, optimal_price)  # Don't exceed 150%
        
        return optimal_price
```

**Backend receives:**
```python
# In backend/api/routes.py
@router.post("/api/v1/admin/update-pricing-rule")
async def update_pricing_rule(request: PricingRuleUpdate, db: Session = Depends(get_db)):
    """
    Update dynamic pricing rule from RouteMaster optimization.
    """
    try:
        # 1. Find or create pricing rule
        rule = db.query(DynamicPricingRule).filter(
            DynamicPricingRule.route_id == request.route_id
        ).first()
        
        if not rule:
            rule = DynamicPricingRule(route_id=request.route_id)
        
        # 2. Update pricing
        rule.base_multiplier = request.optimal_price / request.base_price
        rule.algorithm = request.rationale.get('algorithm')
        rule.updated_at = request.rationale.get('timestamp')
        rule.confidence = request.rationale.get('confidence', 0.9)
        
        # 3. Log for monitoring
        logger.info(
            f"Updated pricing for route {request.route_id}: "
            f"{request.optimal_price} (demand={request.rationale['demand_score']})"
        )
        
        # 4. Apply to future bookings
        db.add(rule)
        db.commit()
        
        return {
            'success': True,
            'route_id': request.route_id,
            'new_price': request.optimal_price
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"Pricing update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### 2.2 Demand Prediction

**RouteMaster Agent:**
```python
# Uses ML models to predict demand
class DemandPredictor:
    async def predict_for_route(self, route_data):
        """
        Predict demand using time-series + external factors.
        """
        # Get historical data
        history = await self.data_store.get_route_history(
            origin=route_data['origin'],
            destination=route_data['destination'],
            days_back=90
        )
        
        # Extract features
        features = {
            'day_of_week': route_data['travel_date'].weekday(),
            'is_weekend': route_data['travel_date'].weekday() >= 5,
            'is_holiday': self._is_holiday(route_data['travel_date']),
            'days_until_travel': (route_data['travel_date'] - datetime.now()).days,
            'historical_avg_occupancy': np.mean([h['occupancy'] for h in history]),
            'recent_trend': self._calculate_trend(history),
            'weather_forecast': await self._get_weather(route_data['destination']),
            'competitor_pricing': await self._get_competitor_prices(route_data)
        }
        
        # Predict using ensemble
        demand_score = self.ensemble_model.predict([features])
        
        return {
            'demand_score': demand_score[0],  # 0 to 1
            'confidence': 0.85,
            'features': features
        }
```

---

## 3. BOOKING & SEAT MANAGEMENT

### 3.1 Direct Booking Integration

**RouteMaster Agent can make bookings:**
```python
# In routemaster_agent/tasks/booking_agent.py
class BookingAgent:
    async def complete_booking(self, booking_request):
        """
        Make booking through backend for users.
        """
        # 1. Search routes using backend
        search_response = await self.backend_client.search_routes(
            source=booking_request['source'],
            destination=booking_request['destination'],
            travel_date=booking_request['travel_date'],
            num_passengers=booking_request['num_passengers']
        )
        
        # 2. Select best route using RL
        best_route = self.rl_agent.select_best_route(
            routes=search_response['routes'],
            user_profile=booking_request['user_profile']
        )
        
        # 3. Book through backend
        booking_response = await self.backend_client.create_booking(
            route_id=best_route['route_id'],
            passengers=booking_request['passengers'],
            user_id=booking_request['user_id'],
            preferences=booking_request['preferences']
        )
        
        # 4. Log feedback for model improvement
        self.ml_feedback.log_booking_outcome({
            'route_id': best_route['route_id'],
            'booking_id': booking_response['booking_id'],
            'success': booking_response['status'] == 'CONFIRMED',
            'num_passengers': booking_request['num_passengers']
        })
        
        return booking_response
```

**Backend:**
```python
# In backend/services/booking_service.py
@router.post("/api/v1/bookings")
async def create_booking(request: BookingRequest, db: Session = Depends(get_db)):
    """
    Create booking (from frontend or RouteMaster Agent).
    """
    try:
        # 1. Allocate seats
        seat_allocation = booking_service.allocate_seats(
            booking_request=request,
            num_passengers=len(request.passengers)
        )
        
        if not seat_allocation:
            return {
                'status': 'WAITLIST',
                'message': 'No seats available, added to waitlist'
            }
        
        # 2. Create booking record
        booking = Booking(
            user_id=request.user_id,
            trip_id=request.route_id,
            travel_date=request.travel_date,
            booking_details=seat_allocation,
            status='CONFIRMED',
            amount_paid=request.total_fare
        )
        
        # 3. Generate PNR
        booking.pnr_number = generate_pnr(booking)
        
        # 4. Process payment
        payment_result = await payment_service.process_payment(
            amount=request.total_fare,
            payment_method=request.payment_method,
            user_id=request.user_id
        )
        
        if not payment_result['success']:
            return {'status': 'PAYMENT_FAILED', 'error': payment_result['error']}
        
        # 5. Confirm booking
        booking.payment_status = 'PAID'
        db.add(booking)
        db.commit()
        
        # 6. Send confirmation
        await notification_service.send_booking_confirmation(
            user_id=request.user_id,
            booking_id=booking.id,
            pnr=booking.pnr_number
        )
        
        return {
            'status': 'CONFIRMED',
            'booking_id': booking.id,
            'pnr': booking.pnr_number,
            'total_fare': request.total_fare,
            'seats': seat_allocation
        }
    
    except Exception as e:
        logger.error(f"Booking failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 4. FEEDBACK LOOP FOR ML MODEL TRAINING

### 4.1 Data Collection for RL

**RouteMaster Agent logs:**
```python
# In routemaster_agent/intelligence/feedback_collector.py
class FeedbackCollector:
    async def log_route_selection(self, event):
        """
        Log when user selects a route for RL training.
        """
        feedback = {
            'user_id': event['user_id'],
            'search_query': {
                'origin': event['origin'],
                'destination': event['destination'],
                'travel_date': event['travel_date'],
                'num_passengers': event['num_passengers']
            },
            'candidate_routes': event['routes_shown'],
            'selected_route': event['selected_route'],
            'selected_index': event['selected_index'],
            'booking_completed': event['booking_completed'],
            'timestamp': datetime.utcnow()
        }
        
        # Send to backend for RL training
        await self.backend_client.log_rl_feedback(feedback)
    
    async def log_booking_outcome(self, event):
        """
        Log booking outcomes for reward calculation.
        """
        # Calculate reward
        reward = 1.0 if event['success'] else 0.0
        reward += 0.2 if event['payment_success'] else 0.0
        reward += 0.1 if event['seats_confirmed'] > 0 else 0.0
        
        feedback = {
            'booking_id': event['booking_id'],
            'route_id': event['route_id'],
            'reward': reward,
            'context': event,
            'timestamp': datetime.utcnow()
        }
        
        await self.backend_client.log_rl_feedback(feedback)
```

**Backend stores for model training:**
```python
# In backend/services/ml_service.py
@router.post("/api/v1/ml/log-feedback")
async def log_rl_feedback(request: RLFeedbackLog, db: Session = Depends(get_db)):
    """
    Store RL feedback for async model retraining.
    """
    # 1. Store feedback
    feedback_record = RLFeedbackLog(
        user_id=request.user_id,
        session_id=request.session_id,
        action=request.action,
        context=request.context,
        reward=request.reward,
        timestamp=request.timestamp
    )
    
    db.add(feedback_record)
    db.commit()
    
    # 2. Publish to Kafka for async processing
    await kafka_producer.send_and_wait(
        'rl.feedback',
        value=feedback_record.to_dict()
    )
    
    return {'success': True, 'message': 'Feedback logged'}
```

---

## 5. API REFERENCE

### 5.1 Backend APIs for RouteMaster Agent

```python
# Route Search
POST /api/v1/routes/search
{
    "source": "NDLS",
    "destination": "CSTM",
    "travel_date": "2026-02-20",
    "num_passengers": 2,
    "num_alternatives": 5
}
→ Returns list of routes with costs, durations, transfers

# Bulk Insert Trips (after scraping)
POST /api/v1/admin/bulk-insert-trips
{
    "trips": [
        {
            "trip_id": "12345_2026-02-20",
            "route_id": 1,
            "mode": "train",
            "train_number": "12345",
            "stop_times": [...]
        }
    ]
}
→ Returns inserted count and errors

# Update Train State (real-time)
POST /api/v1/admin/update-train-state
{
    "train_id": "12345",
    "location": {"lat": 28.5, "lon": 77.2},
    "delay_minutes": 15,
    "occupancy_rate": 0.75,
    "timestamp": "2026-02-20T10:30:00Z"
}
→ Updates real-time state and triggers graph mutation

# Create Booking
POST /api/v1/bookings
{
    "source": "NDLS",
    "destination": "CSTM",
    "travel_date": "2026-02-20",
    "passengers": [...],
    "preferences": {...}
}
→ Returns booking confirmation with PNR

# Update Pricing Rule
POST /api/v1/admin/update-pricing-rule
{
    "route_id": "NDLS-CSTM",
    "optimal_price": 2500,
    "rationale": {"demand_score": 0.75}
}
→ Updates dynamic pricing for route

# Log RL Feedback
POST /api/v1/ml/log-feedback
{
    "user_id": "user_123",
    "action": "route_selected",
    "context": {...},
    "reward": 0.8,
    "timestamp": "2026-02-20T10:30:00Z"
}
→ Stores for model training
```

### 5.2 RouteMaster Agent Initialization

```python
# In routemaster_agent/backend_integration.py

class BackendClient:
    def __init__(self, backend_url: str, api_key: str):
        self.backend_url = backend_url
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=backend_url,
            headers={'Authorization': f'Bearer {api_key}'}
        )
    
    async def search_routes(self, **kwargs):
        response = await self.client.post('/api/v1/routes/search', json=kwargs)
        return response.json()
    
    async def bulk_insert_trips(self, trips):
        response = await self.client.post(
            '/api/v1/admin/bulk-insert-trips',
            json={'trips': trips}
        )
        return response.json()
    
    async def update_train_state(self, **kwargs):
        response = await self.client.post(
            '/api/v1/admin/update-train-state',
            json=kwargs
        )
        return response.json()
    
    async def create_booking(self, **kwargs):
        response = await self.client.post('/api/v1/bookings', json=kwargs)
        return response.json()
    
    async def log_rl_feedback(self, feedback):
        response = await self.client.post(
            '/api/v1/ml/log-feedback',
            json=feedback
        )
        return response.json()


# Initialize in main.py
async def initialize_backend_integration():
    global backend_client
    backend_client = BackendClient(
        backend_url=os.getenv('BACKEND_URL', 'http://localhost:8000'),
        api_key=os.getenv('BACKEND_API_KEY')
    )
```

---

## 6. DEPLOYMENT CHECKLIST

- [ ] Set up backend service (PostgreSQL, Redis, Kafka)
- [ ] Deploy route search service
- [ ] Deploy booking service
- [ ] Set up ML/RL models
- [ ] Configure RouteMaster Agent API credentials
- [ ] Test data collection pipeline
- [ ] Test real-time updates
- [ ] Test booking flow end-to-end
- [ ] Monitor performance metrics
- [ ] Set up alerting for failures

---

## 7. MONITORING & OBSERVABILITY

**Key Metrics to Monitor:**

```python
# In backend and agent code
METRICS = {
    'route_search_latency_ms': histogram,
    'routes_per_query': histogram,
    'booking_success_rate': gauge,
    'real_time_updates_per_minute': counter,
    'ml_prediction_accuracy': gauge,
    'pricing_optimization_revenue_impact': gauge,
}

# Grafana dashboards
- Route Search Performance
- Booking Funnel
- Seat Inventory Status
- Real-time Train Updates
- ML Model Performance
- Pricing Optimization Impact
```

---

## CONCLUSION

The integration between RouteMaster Agent and the Backend System creates a powerful, autonomous transportation intelligence platform:

- **Agent:** Collects data, makes intelligent decisions, predicts demand
- **Backend:** Computes routes, manages bookings, optimizes pricing
- **Feedback:** ML/RL models continuously improve both

This symbiotic relationship creates a system that learns and adapts to user preferences and market dynamics, delivering superior user experience and maximizing operational efficiency.

---

**Ready to integrate?** Follow the API reference and deployment checklist above. Start with Phase 1 (data collection) and gradually expand to optimize pricing and demand prediction.
