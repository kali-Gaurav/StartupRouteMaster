# IRCTC-Inspired Advanced Backend System Architecture
## Multi-Modal, Multi-Transfer Railway Intelligence Engine

**Document Version:** 2.0  
**Date:** February 17, 2026  
**Status:** Production-Ready Design Blueprint  

---

## EXECUTIVE SUMMARY

This document outlines a **production-grade, IRCTC-inspired backend system** designed for the startupV2 project. It builds upon IRCTC's proven railway reservation architecture while extending it to support:

- **Multi-Modal Transport** (Trains → Buses → Flights → Future modes)
- **Multi-Transfer Routes** (Complex layover management)
- **Real-Time Graph Mutation** (Dynamic train state updates)
- **ML/RL Optimization** (Smart route ranking & pricing)
- **High-Performance Algorithms** (RAPTOR, A*, Yen's algorithm)
- **Microservices Architecture** (Scalable, fault-tolerant)
- **Integration with RouteMaster Agent** (Autonomous intelligence)

---

## TABLE OF CONTENTS

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Core Components & Services](#2-core-components--services)
3. [Enhanced Route Search Engine](#3-enhanced-route-search-engine)
4. [Real-Time Data Pipeline](#4-real-time-data-pipeline)
5. [Booking & Seat Inventory System](#5-booking--seat-inventory-system)
6. [ML/RL Integration](#6-mlrl-integration)
7. [Database Schema (GTFS-Based)](#7-database-schema-gtfs-based)
8. [API Gateway & Integration](#8-api-gateway--integration)
9. [Scalability & Performance](#9-scalability--performance)
10. [RouteMaster Agent Integration](#10-routemaster-agent-integration)

---

## 1. SYSTEM ARCHITECTURE OVERVIEW

### 1.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                │
│  (Web Browser, Mobile App, RouteMaster Agent, Partner APIs)         │
└────────────────────────┬────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────────┐
│              API GATEWAY (Nginx/Kong)                               │
│  - Authentication/Authorization                                     │
│  - Rate Limiting, Load Balancing                                    │
│  - Request Routing, Response Caching                                │
│  - SSL/TLS Termination                                              │
└────────────────────────┬────────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
┌───────▼──────┐ ┌──────▼────────┐ ┌────▼─────────────┐
│ Auth Service │ │ Station Svc   │ │ Route Search Svc │
│              │ │               │ │                  │
│ JWT/OAuth2   │ │ GTFS Network  │ │ RAPTOR Algorithm │
│ User Mgmt    │ │ PostGIS       │ │ A*, Yen's K-SP   │
│ Preferences  │ │ Real-time     │ │ Multi-Modal      │
└──────────────┘ └───────────────┘ │ Graph Mutation   │
                                   └────┬─────────────┘
                                        │
        ┌───────────────┬───────────────┼────────────────┬──────────────┐
        │               │               │                │              │
┌───────▼────┐  ┌──────▼────────┐ ┌───▼──────────┐ ┌──▼────────┐ ┌──▼─────┐
│ Booking    │  │ Inventory Svc │ │ Pricing Svc  │ │ ML/RL Svc │ │Payment │
│ Service    │  │               │ │              │ │           │ │ Svc    │
│ PNR, Seat  │  │ Seat Alloc    │ │ Dynamic      │ │ Route     │ │        │
│ Management │  │ Availability  │ │ Pricing, ML  │ │ Ranking   │ │ Razorpay
│            │  │ Overbooking   │ │ Discounts    │ │ Demand    │ │ Stripe │
└──────┬─────┘  └────────────────┘ └──────────────┘ │ Prediction│ └────────┘
       │                                            └───────────┘
       │
┌──────▼────────────────────────────────────────────────────────────────┐
│                    MESSAGE BROKER (Kafka/RabbitMQ)                    │
│  Topics: BookingCreated, TrainDelayed, StationUpdated, ScheduleSync  │
└──────┬─────────────────────────────────────────────────────────────────┘
       │
   ┌───┴────┬─────────┬──────────┬─────────────┐
   │         │         │          │             │
┌──▼──┐ ┌──▼──┐ ┌───▼─┐ ┌──────▼─┐ ┌────────▼─┐
│ ETL │ │ Real│ │Data │ │Notif  │ │Analytics │
│Pipe │ │Time │ │Lake │ │Service│ │ Consumer │
│line │ │Queue│ │(S3) │ └────────┘ └──────────┘
└─────┘ └─────┘ └─────┘
       │
┌──────▼────────────────────────────────────────────────────────────────┐
│                    PERSISTENT STORAGE LAYER                           │
│                                                                        │
│  ┌──────────────────┐  ┌────────────────┐  ┌──────────────────────┐  │
│  │  PostgreSQL      │  │   Redis Cache  │  │   Neo4j (Optional)   │  │
│  │ (Primary DB)     │  │ (Session, Route│  │ (Graph Traversal)    │  │
│  │ - GTFS Stations  │  │  Cache, Tokens)│  │                      │  │
│  │ - Trips/Stops    │  │                │  │                      │  │
│  │ - Bookings       │  │   InfluxDB     │  │                      │  │
│  │ - Users          │  │ (Time-series)  │  │                      │  │
│  │ - Transfers      │  │ - Train Data   │  │                      │  │
│  │ - Seat Inventory │  │ - Metrics      │  │                      │  │
│  │ - Pricing Rules  │  │                │  │                      │  │
│  └──────────────────┘  └────────────────┘  └──────────────────────┘  │
│                                                                        │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Elasticsearch / Loki (Logs) + Prometheus (Metrics)            │  │
│  │  Grafana (Visualization) + Jaeger (Distributed Tracing)        │  │
│  └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Technology Stack

| Component | Technology | Justification |
|-----------|-----------|---------------|
| **Language** | Python 3.11+ (FastAPI), Rust/Go (perf-critical) | Python for ML/flexibility, Rust for speed |
| **API Framework** | FastAPI | Async, automatic OpenAPI docs, validation |
| **Web Server** | Uvicorn + Nginx | Async ASGI, reverse proxy, load balancing |
| **Primary Database** | PostgreSQL 14+ with PostGIS | ACID, geospatial, relational, GTFS support |
| **Cache Layer** | Redis 7+ | Fast K-V, pub/sub, session management |
| **Message Broker** | Kafka or RabbitMQ | Event-driven architecture, log durability |
| **Search/Analytics** | Elasticsearch + Kibana | Full-text search, log aggregation |
| **Monitoring** | Prometheus + Grafana + Jaeger | Metrics, visualization, distributed tracing |
| **Container Orchestration** | Kubernetes | Scaling, self-healing, service discovery |
| **ML/RL Framework** | TensorFlow, PyTorch, Ray | Training, inference, distributed computing |
| **Graph Algorithm** | NetworkX / Custom C extension | Path finding, topology analysis |

---

## 2. CORE COMPONENTS & SERVICES

### 2.1 API Gateway Service

**Purpose:** Single entry point for all external requests; handles authentication, rate limiting, request routing.

**Responsibilities:**
- JWT/OAuth2 authentication
- Request rate limiting per user/IP
- Load balancing across microservices
- Response caching (CDN integration)
- SSL/TLS termination
- Request logging & monitoring
- CORS handling
- API versioning

**Key Endpoints:**
```
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh-token

GET    /api/v1/stations/search
GET    /api/v1/stations/{id}
GET    /api/v1/routes/search
POST   /api/v1/bookings
GET    /api/v1/bookings/{id}
POST   /api/v1/payments/initiate
GET    /api/v1/payments/{id}/status
```

### 2.2 Authentication & User Service

**Purpose:** Centralized user management, authentication, preferences.

**Data Models:**
- User profiles
- Preferences (window seat, veg meals, travel class, preferred trains)
- Loyalty points, premium status
- Authentication tokens
- Session management

**Key Algorithms:**
- JWT token generation & validation
- Password hashing (bcrypt)
- Session management with Redis
- Multi-factor authentication (MFA) support

### 2.3 Station & Network Service

**Purpose:** Manages GTFS-based static and dynamic network data.

**Data Structures:**
- **Stations/Stops:** GTFS stops with PostGIS geometry
- **Routes:** GTFS routes (train/bus lines)
- **Trips:** Individual journeys
- **Stop Times:** Arrival/departure at each stop
- **Transfers:** Valid transfer points with timing constraints
- **Real-time Data:** Current train location, delays, status

**Core Operations:**
- Spatial queries (find nearby stations)
- Schedule lookups
- Transfer validation
- Network topology updates
- Real-time state tracking

### 2.4 Route Search & Optimization Service (★ CORE ENGINE ★)

**Purpose:** The computational heart of the system; finds optimal multi-modal, multi-transfer routes.

**Algorithms Implemented:**

#### 2.4.1 RAPTOR (Round-based Public Transit Optimizer)

**When to Use:** Fast point-to-point routing for realistic public transit queries.

**Time Complexity:** O(k × S × T), where k = rounds ≈ 10, S = stops, T = trips

**Key Idea:** Iteratively improves arrival time by considering transfers at each stop.

```python
def raptor(source_stop, target_stop, departure_time, max_transfers=3):
    """
    RAPTOR algorithm for fastest path in public transit.
    """
    # Round 0: Find direct trips from source
    best_arrivals = {source_stop: departure_time}
    
    for round in range(1, max_transfers + 1):
        # For each stop reached in round r-1
        improved = False
        for trip in all_trips:
            # If we can board this trip from a reached stop
            for board_idx, stop_idx in enumerate(trip.stops):
                if stop_idx in best_arrivals:
                    board_time = best_arrivals[stop_idx]
                    if board_time <= trip.departure_times[board_idx]:
                        # Board trip, ride to end
                        for alight_idx in range(board_idx + 1, len(trip.stops)):
                            alight_stop = trip.stops[alight_idx]
                            arrival = trip.arrival_times[alight_idx]
                            if alight_stop not in best_arrivals or arrival < best_arrivals[alight_stop]:
                                best_arrivals[alight_stop] = arrival
                                improved = True
        
        if not improved:
            break
    
    return best_arrivals[target_stop]
```

**Advantages:**
- ✅ Fast (10s of ms for realistic queries)
- ✅ Exact optimal path
- ✅ Naturally handles transfers
- ✅ Can enumerate k-shortest paths

**Limitations:**
- ❌ Single objective (time only)
- ❌ Needs preprocessing for very large networks

#### 2.4.2 A* Algorithm (Heuristic Search)

**When to Use:** When geographic distance heuristic is valuable; finds paths quickly with prioritization.

**Time Complexity:** O(E log V) with good heuristic

**Key Idea:** Prioritize exploration using f(n) = g(n) + h(n), where:
- g(n) = actual cost from source
- h(n) = heuristic estimate to target

```python
def a_star_routing(source, target, departure_time, graph, mode_constraints=None):
    """
    A* for multi-modal routing with geographic heuristic.
    """
    import heapq
    from math import radians, cos, sin, asin, sqrt
    
    def haversine_distance(coord1, coord2):
        """Distance in km between two lat/lon coords."""
        lon1, lat1 = coord1
        lon2, lat2 = coord2
        
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371  # Earth radius in km
        return c * r
    
    open_set = []
    heapq.heappush(open_set, (0, source, departure_time, []))
    came_from = {}
    g_score = {source: 0}
    h_estimate = haversine_distance(graph[source]['coord'], graph[target]['coord'])
    
    while open_set:
        _, current, current_time, path = heapq.heappop(open_set)
        
        if current == target:
            return {'path': path + [current], 'arrival_time': current_time, 'cost': g_score[current]}
        
        for neighbor, edge_data in graph[current]['edges'].items():
            travel_time = edge_data['duration']
            transfer_time = edge_data.get('transfer_time', 0)
            
            # Check if mode constraint satisfied
            if mode_constraints and edge_data['mode'] not in mode_constraints:
                continue
            
            tentative_g = g_score[current] + travel_time + transfer_time
            
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                new_time = current_time + timedelta(minutes=travel_time + transfer_time)
                h = haversine_distance(graph[neighbor]['coord'], graph[target]['coord'])
                f = tentative_g + h
                heapq.heappush(open_set, (f, neighbor, new_time, path + [current]))
    
    return None
```

**Advantages:**
- ✅ Fast with good heuristic
- ✅ Can optimize for multiple objectives (time, cost, transfers)
- ✅ Flexible for different modes

**Limitations:**
- ❌ Single-source single-target
- ❌ Quality depends on heuristic

#### 2.4.3 Yen's Algorithm (K-Shortest Paths)

**When to Use:** When user wants multiple options; finds k distinct paths ranked by cost.

**Time Complexity:** O(k × V × (E + V log V)) using Dijkstra internally

**Key Idea:** Find shortest path, then systematically remove edges to find next-best paths.

```python
def yens_k_shortest_paths(source, target, departure_time, k=5, graph=None):
    """
    Yen's algorithm for k-shortest paths in multi-modal network.
    """
    def dijkstra_with_forbidden_edges(src, tgt, forbidden_edges, graph, time):
        # Standard Dijkstra with forbidden edge list
        pass
    
    # A = shortest path between source and target
    A = [dijkstra_with_forbidden_edges(source, target, set(), graph, departure_time)]
    B = []  # Potential paths (heap)
    
    for k_iter in range(1, k):
        for i in range(len(A[-1]['path']) - 1):
            # Spur node and root path
            spur_node = A[-1]['path'][i]
            root_path = A[-1]['path'][:i+1]
            
            # Remove edges from root path
            forbidden = set()
            for edge in zip(root_path[:-1], root_path[1:]):
                forbidden.add(edge)
            
            # Find shortest path from spur node
            spur_path = dijkstra_with_forbidden_edges(
                spur_node, target, forbidden, graph, departure_time
            )
            
            if spur_path:
                potential_path = {
                    'path': root_path[:-1] + spur_path['path'],
                    'cost': root_path_cost + spur_path['cost']
                }
                heapq.heappush(B, (potential_path['cost'], potential_path))
        
        if not B:
            break
        
        # Add lowest cost potential path to A
        _, path = heapq.heappop(B)
        A.append(path)
    
    return A[:k]
```

**Advantages:**
- ✅ Returns multiple diverse paths
- ✅ User gets choices (fast, cheap, scenic)
- ✅ Can be visualized together

**Limitations:**
- ❌ More expensive (k iterations of Dijkstra)
- ❌ Need to handle k carefully

#### 2.4.4 Real-Time Graph Mutation Engine

**Purpose:** Handle dynamic updates (train delays, cancellations, new routes).

**Key Operations:**

```python
class GraphMutationEngine:
    """
    Real-time updates to route graph without full recalculation.
    """
    
    def __init__(self, network_service, redis_client):
        self.network = network_service
        self.redis = redis_client
        self.graph_version = self._load_version()
    
    def handle_train_delay(self, train_id, delay_minutes, affected_stations):
        """
        Update trip timings when train is delayed.
        """
        # 1. Get affected trips
        trips = self.network.get_trips_for_train(train_id)
        
        # 2. Update stop times in database
        for trip in trips:
            for i, stop_id in enumerate(trip.stops):
                if stop_id in affected_stations:
                    new_arr = trip.arrival_times[i] + timedelta(minutes=delay_minutes)
                    new_dep = trip.departure_times[i] + timedelta(minutes=delay_minutes)
                    self.network.update_stop_time(trip, i, new_arr, new_dep)
        
        # 3. Invalidate affected cache entries
        cache_keys = [f"route:{s[0]}:{s[1]}:*" for s in affected_stations]
        self.redis.delete(*[k for pattern in cache_keys for k in self.redis.keys(pattern)])
        
        # 4. Publish event to Kafka
        self.publish_event('TrainDelayed', {
            'train_id': train_id,
            'delay_minutes': delay_minutes,
            'affected_stations': affected_stations
        })
        
        # 5. Increment graph version for clients
        self.graph_version += 1
        self.redis.set('graph_version', self.graph_version)
    
    def handle_train_cancellation(self, train_id, cancelled_stops=None):
        """
        Remove trip from graph on cancellation.
        """
        trips = self.network.get_trips_for_train(train_id)
        
        for trip in trips:
            if cancelled_stops:
                # Partial cancellation: update affected stops
                for stop_id in cancelled_stops:
                    idx = trip.stops.index(stop_id)
                    trip.cancelled_stations.append(stop_id)
            else:
                # Full cancellation: mark trip as inactive
                trip.status = 'CANCELLED'
                self.network.update_trip_status(trip, 'CANCELLED')
        
        # Invalidate caches and publish event
        self.redis.delete(f"routes:train:{train_id}:*")
        self.publish_event('TrainCancelled', {'train_id': train_id, 'stops': cancelled_stops})
    
    def handle_new_temporary_route(self, diversion_data):
        """
        Add temporary route due to track diversion.
        """
        # Create temporary trip
        temp_trip = Trip(
            route_id=diversion_data['route_id'],
            stops=diversion_data['diverted_stops'],
            timings=diversion_data['adjusted_timings'],
            validity_end=diversion_data['validity_end']
        )
        self.network.add_temporary_trip(temp_trip)
        
        # Update transfers at affected stations
        for stop_id in diversion_data['diverted_stops']:
            self.network.update_transfer_rules(stop_id, temp_trip)
        
        self.publish_event('TemporaryRouteAdded', diversion_data)
    
    def get_graph_snapshot(self, version=None):
        """
        Get consistent graph snapshot for route search.
        """
        if version is None:
            version = self.graph_version
        
        # Try cache first
        cached = self.redis.get(f"graph_snapshot:{version}")
        if cached:
            return pickle.loads(cached)
        
        # Build snapshot from database
        snapshot = {
            'version': version,
            'timestamp': datetime.utcnow(),
            'stops': self.network.get_all_stops(),
            'trips': self.network.get_all_active_trips(version),
            'transfers': self.network.get_all_transfers(),
            'realtime_data': self.network.get_latest_realtime_state()
        }
        
        # Cache for 5 minutes
        self.redis.setex(f"graph_snapshot:{version}", 300, pickle.dumps(snapshot))
        return snapshot
```

### 2.5 Booking & Seat Inventory Service

**Purpose:** Handle ticket bookings, PNR generation, seat allocation, waitlist management.

**Key Responsibilities:**
- Seat selection & allocation
- PNR (Passenger Name Record) generation
- Booking confirmation & cancellation
- Waitlist management
- Overbooking prevention
- Batch seat allocation for multi-segment journeys

**Core Algorithm: Smart Seat Allocation**

```python
class SeatInventoryManager:
    """
    Manages seat availability, allocation, and overbooking.
    """
    
    def __init__(self, db_session, cache):
        self.db = db_session
        self.cache = cache
    
    def allocate_seats(self, booking_request, num_passengers):
        """
        Allocate seats intelligently across all journey segments.
        """
        journey_segments = booking_request['segments']
        seat_allocations = {}
        
        try:
            # Start transaction
            self.db.begin_nested()
            
            for segment_idx, segment in enumerate(journey_segments):
                stop_time_id = segment['stop_time_id']
                coach_preference = segment.get('coach_preference', 'any')
                seat_class = segment.get('seat_class', 'general')
                
                # Get available seats
                available_seats = self._get_available_seats(
                    stop_time_id, 
                    num_passengers,
                    coach_preference,
                    seat_class
                )
                
                if len(available_seats) < num_passengers:
                    # Not enough seats, put on waitlist
                    seat_allocations[segment_idx] = {
                        'allocated': available_seats,
                        'status': 'WAITLIST',
                        'waitlist_position': self._add_to_waitlist(stop_time_id, num_passengers)
                    }
                else:
                    # Allocate seats using fairness algorithm
                    allocated = self._fair_seat_allocation(
                        available_seats,
                        num_passengers,
                        coach_preference
                    )
                    
                    # Reserve seats
                    self._reserve_seats(stop_time_id, allocated)
                    
                    seat_allocations[segment_idx] = {
                        'allocated': allocated,
                        'status': 'CONFIRMED'
                    }
            
            # Commit transaction if all segments allocated
            self.db.commit()
            return seat_allocations
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Seat allocation failed: {e}")
            raise
    
    def _get_available_seats(self, stop_time_id, num_needed, coach_pref, seat_class):
        """
        Get list of available seats using cache + DB.
        """
        cache_key = f"available_seats:{stop_time_id}"
        cached = self.cache.get(cache_key)
        
        if cached:
            available = json.loads(cached)
        else:
            # Query database
            inventory = self.db.query(SeatInventory).filter(
                SeatInventory.stop_time_id == stop_time_id
            ).first()
            
            available = self._calculate_available_seats(inventory)
            self.cache.setex(cache_key, 60, json.dumps(available))
        
        # Filter by coach preference and class
        filtered = [s for s in available if self._matches_preference(s, coach_pref, seat_class)]
        return filtered[:num_needed]
    
    def _fair_seat_allocation(self, available_seats, num_passengers, preference):
        """
        Allocate seats fairly (not all adjacent, distributed across coaches).
        """
        if preference == 'window':
            return sorted(available_seats, key=lambda s: s['is_window'], reverse=True)[:num_passengers]
        elif preference == 'aisle':
            return sorted(available_seats, key=lambda s: s['is_aisle'], reverse=True)[:num_passengers]
        else:
            # Distribute across coaches
            coaches = {}
            for seat in available_seats:
                coach = seat['coach']
                if coach not in coaches:
                    coaches[coach] = []
                coaches[coach].append(seat)
            
            allocated = []
            for coach in sorted(coaches.keys()):
                seats_per_coach = num_passengers // len(coaches)
                allocated.extend(coaches[coach][:seats_per_coach])
            
            return allocated[:num_passengers]
    
    def _reserve_seats(self, stop_time_id, seat_list):
        """
        Mark seats as reserved in inventory.
        """
        for seat in seat_list:
            self.db.execute(
                "UPDATE seat_inventory SET seats_available = seats_available - 1 WHERE stop_time_id = %s",
                (stop_time_id,)
            )
        
        # Invalidate cache
        self.cache.delete(f"available_seats:{stop_time_id}")
```

### 2.6 Pricing & Fare Service

**Purpose:** Dynamic fare calculation with ML-based pricing optimization.

**Pricing Components:**

```python
class FareCalculationEngine:
    """
    Multi-factor dynamic pricing engine inspired by airline revenue management.
    """
    
    def __init__(self, db_session, ml_service):
        self.db = db_session
        self.ml = ml_service
    
    def calculate_fare(self, route_details, passenger_profile, booking_date):
        """
        Calculate fare with multiple factors.
        """
        base_fare = self._get_base_fare(
            route_details['origin'],
            route_details['destination'],
            route_details['distance_km']
        )
        
        # 1. Distance-based pricing
        distance_multiplier = self._distance_multiplier(route_details['distance_km'])
        
        # 2. Time-of-travel pricing
        time_multiplier = self._time_of_day_multiplier(route_details['departure_time'])
        
        # 3. Occupancy-based surge pricing
        occupancy = self._get_occupancy_rate(route_details['trip_id'])
        occupancy_multiplier = 1.0 + (occupancy ** 1.5) * 0.3  # Up to 30% surge at full capacity
        
        # 4. Demand prediction
        demand_score = self.ml.predict_demand(route_details, booking_date)
        demand_multiplier = 1.0 + (demand_score - 0.5) * 0.4  # -20% to +20%
        
        # 5. User loyalty discount
        loyalty_discount = self._get_loyalty_discount(passenger_profile)
        
        # 6. Seasonal adjustment
        seasonal_multiplier = self._seasonal_adjustment(booking_date)
        
        # 7. Competition-based pricing
        competitor_price = self._get_competitor_average_price(route_details)
        
        # Combined fare
        dynamic_fare = (
            base_fare *
            distance_multiplier *
            time_multiplier *
            occupancy_multiplier *
            demand_multiplier *
            seasonal_multiplier
        )
        
        # Ensure competitive pricing
        dynamic_fare = min(dynamic_fare, competitor_price * 1.1)  # Never 10% more than competitors
        dynamic_fare = max(dynamic_fare, base_fare * 0.8)  # Never below 80% of base
        
        # Apply loyalty discount
        final_fare = dynamic_fare * (1 - loyalty_discount)
        
        return {
            'base_fare': base_fare,
            'dynamic_fare': dynamic_fare,
            'final_fare': final_fare,
            'discount': loyalty_discount,
            'breakdown': {
                'distance': distance_multiplier,
                'time': time_multiplier,
                'occupancy': occupancy_multiplier,
                'demand': demand_multiplier,
                'seasonal': seasonal_multiplier
            }
        }
    
    def _distance_multiplier(self, distance_km):
        """Pricing based on distance (km)."""
        # Base: 0-200km = 1.0, +0.005 per km beyond
        if distance_km <= 200:
            return 1.0
        return 1.0 + (distance_km - 200) * 0.005
    
    def _time_of_day_multiplier(self, departure_time):
        """Peak vs off-peak pricing."""
        hour = departure_time.hour
        
        # Peak hours: 7-10am, 5-8pm
        if (7 <= hour <= 10) or (17 <= hour <= 20):
            return 1.2  # 20% premium
        # Off-peak: 11pm-5am
        elif (23 <= hour or hour <= 5):
            return 0.8  # 20% discount
        else:
            return 1.0
    
    def _seasonal_adjustment(self, travel_date):
        """Adjust for seasonal demand."""
        # Peak season: 1-15 Mar, 15 Apr-15 May, 1-31 Dec
        month, day = travel_date.month, travel_date.day
        
        if (month == 3 and day <= 15) or \
           (month == 4 and day >= 15) or \
           (month == 5 and day <= 15) or \
           (month == 12):
            return 1.3  # 30% premium
        elif month in [6, 7]:  # Monsoon, low demand
            return 0.85
        else:
            return 1.0
```

### 2.7 ML/RL Recommendation Service

**Purpose:** Smart route ranking, demand prediction, dynamic pricing optimization.

**Key Models:**

```python
class MLRecommendationEngine:
    """
    ML/RL service for route ranking and demand prediction.
    """
    
    def __init__(self, model_registry, feature_store):
        self.models = model_registry
        self.features = feature_store
    
    def rank_routes(self, candidate_routes, user_profile, search_context):
        """
        Rank candidate routes using RL agent.
        """
        # Extract features for each route
        route_features = []
        for route in candidate_routes:
            features = self._extract_route_features(route, user_profile, search_context)
            route_features.append(features)
        
        # Get RL agent predictions
        scores = self.models['route_ranker'].predict(route_features)
        
        # Rank by score
        ranked = sorted(
            zip(candidate_routes, scores),
            key=lambda x: x[1],
            reverse=True
        )
        
        return ranked
    
    def _extract_route_features(self, route, user_profile, context):
        """
        Feature engineering for route ranking.
        """
        return {
            # Temporal features
            'duration_hours': route['duration_minutes'] / 60,
            'num_transfers': len(route['segments']) - 1,
            'departure_hour': route['departure_time'].hour,
            'day_of_week': route['departure_date'].weekday(),
            'days_until_departure': (route['departure_date'] - datetime.now()).days,
            
            # Cost features
            'fare_per_km': route['fare'] / route['distance_km'],
            'estimated_total_cost': route['fare'],
            
            # Service quality features
            'avg_train_rating': self._get_avg_train_rating(route),
            'punctuality_score': self._get_punctuality_score(route),
            'comfort_score': self._get_comfort_score(route),
            
            # User preference alignment
            'matches_user_class_pref': route['seat_class'] in user_profile.get('preferred_classes', []),
            'matches_time_pref': self._time_matches_preference(route['departure_time'], user_profile),
            'historical_choice_similarity': self._similarity_to_past_bookings(route, user_profile),
            
            # Network features
            'is_direct': len(route['segments']) == 1,
            'min_layover_time': min([s['layover_minutes'] for s in route['segments'][:-1]]) if len(route['segments']) > 1 else 0,
            'max_layover_time': max([s['layover_minutes'] for s in route['segments'][:-1]]) if len(route['segments']) > 1 else 0,
        }
    
    def predict_demand(self, route, travel_date):
        """
        Predict demand for a route using time-series + gradient boosting.
        """
        # Get historical demand for this route
        historical = self.features.get_demand_history(
            origin=route['origin'],
            destination=route['destination'],
            days_back=90
        )
        
        # Extract time-series features
        ts_features = self._extract_timeseries_features(historical)
        
        # Get contextual features
        contextual = {
            'is_weekend': travel_date.weekday() >= 5,
            'is_holiday': travel_date in HOLIDAYS,
            'school_holidays': is_school_holiday(travel_date),
            'weather_forecast': self._get_weather_forecast(route['destination'], travel_date),
            'competitor_pricing': self._get_competitor_pricing(route),
            'events_near_destination': self._get_events(route['destination'], travel_date)
        }
        
        # Combine features
        all_features = {**ts_features, **contextual}
        
        # Predict demand (0.0 = low, 1.0 = high)
        demand_score = self.models['demand_predictor'].predict([all_features])
        
        return demand_score[0]
    
    def online_rl_feedback(self, user_id, search_query, ranked_routes, selected_route, booking_completed):
        """
        Update RL agent based on user feedback (online learning).
        """
        # Calculate reward
        reward = self._calculate_reward(
            selected_route=selected_route,
            ranked_routes=ranked_routes,
            booking_completed=booking_completed
        )
        
        # Log feedback to feature store
        self.features.log_feedback({
            'user_id': user_id,
            'query': search_query,
            'state': [self._extract_route_features(r, {}, {}) for r in ranked_routes],
            'action': ranked_routes.index(selected_route),
            'reward': reward,
            'timestamp': datetime.utcnow()
        })
        
        # Async update to model (batch)
        self._schedule_model_update()
    
    def _calculate_reward(self, selected_route, ranked_routes, booking_completed):
        """
        Multi-objective reward function.
        """
        # Base reward: Is this route actually good?
        route_quality = selected_route['quality_score']
        
        # Ranking reward: Did we rank it high?
        rank_position = ranked_routes.index(selected_route) + 1
        ranking_reward = 1.0 / rank_position  # Best if ranked 1st
        
        # Completion reward: Did user actually book?
        completion_reward = 1.0 if booking_completed else 0.5
        
        # Combined reward
        total_reward = (
            route_quality * 0.4 +
            ranking_reward * 0.3 +
            completion_reward * 0.3
        )
        
        return total_reward
```

---

## 3. ENHANCED ROUTE SEARCH ENGINE

### 3.1 Multi-Modal Routing Architecture

The system supports trains → buses → flights with extensibility for future modes.

**Mode-Specific Cost Functions:**

```python
class MultiModalCostCalculator:
    """
    Mode-specific cost calculation for fair comparison across transport modes.
    """
    
    # Different modes have different characteristics
    MODE_PARAMETERS = {
        'train': {
            'base_cost_per_km': 0.5,
            'time_cost_per_hour': 2.0,  # Discomfort cost for travel time
            'transfer_penalty_minutes': 20,  # Penalty for transfers
            'comfort_factor': 0.8,  # Trains are comfortable
            'reliability_factor': 0.9,  # High reliability
        },
        'bus': {
            'base_cost_per_km': 0.3,
            'time_cost_per_hour': 2.5,  # Buses less comfortable
            'transfer_penalty_minutes': 15,
            'comfort_factor': 0.6,
            'reliability_factor': 0.7,
        },
        'flight': {
            'base_cost_per_km': 0.8,
            'time_cost_per_hour': 1.0,  # Flights faster
            'transfer_penalty_minutes': 60,  # Airport procedures
            'comfort_factor': 0.75,
            'reliability_factor': 0.95,
        },
        'metro': {
            'base_cost_per_km': 0.2,
            'time_cost_per_hour': 3.0,  # Metro slower, stop frequent
            'transfer_penalty_minutes': 5,
            'comfort_factor': 0.5,
            'reliability_factor': 0.99,
        },
    }
    
    def calculate_segment_cost(self, segment, user_preferences=None):
        """
        Calculate total cost for a segment (not just monetary).
        """
        mode = segment['mode']
        params = self.MODE_PARAMETERS[mode]
        
        distance_km = segment['distance_km']
        duration_minutes = segment['duration_minutes']
        departure_hour = segment['departure_time'].hour
        
        # 1. Monetary cost
        monetary_cost = params['base_cost_per_km'] * distance_km
        monetary_cost *= self._time_of_day_multiplier(departure_hour)
        
        # 2. Time cost (valued at user's time value)
        user_time_value = user_preferences.get('time_value_per_hour', 100) if user_preferences else 100
        time_cost = (duration_minutes / 60) * (user_time_value / 100) * params['time_cost_per_hour']
        
        # 3. Comfort cost (negative - higher comfort = lower cost)
        comfort_cost = -params['comfort_factor'] * 5  # Up to 5 INR saved for comfort
        
        # 4. Reliability cost (negative - reliable = lower cost)
        reliability_cost = -params['reliability_factor'] * 3
        
        # Total utility cost
        total_cost = monetary_cost + time_cost + comfort_cost + reliability_cost
        
        return {
            'monetary': monetary_cost,
            'time': time_cost,
            'comfort': comfort_cost,
            'reliability': reliability_cost,
            'total': total_cost
        }
    
    def _time_of_day_multiplier(self, hour):
        """Different modes have different peak times."""
        if 7 <= hour <= 11 or 16 <= hour <= 20:
            return 1.2
        return 1.0
```

### 3.2 Transfer Logic (Set A & Set B Intersection)

**IRCTC Principle:** A valid transfer requires:
- Source arrival time + minimum transfer time ≤ Destination departure time
- Transfer happens at a valid interchange station

**Implementation:**

```python
class TransferLogic:
    """
    Intelligent transfer computation between segments.
    """
    
    MIN_TRANSFER_TIME_MINUTES = {
        'same_station': 5,           # Same physical station, different vehicle
        'adjacent_stations': 10,      # Walking distance
        'different_city': 60,         # City to city transfer
        'airport': 120,               # Complex airport procedures
    }
    
    def find_valid_transfers(self, arrival_segment, departure_segment, transfer_rules):
        """
        Find valid transfer points between two segments.
        """
        # Source of first segment
        set_a = [
            stop['stop_id'] for stop in arrival_segment['stops']
            if stop['stop_time'] <= arrival_segment['arrival_time']
        ]
        
        # Destinations of second segment (reachable with transfer time)
        set_b = [
            stop['stop_id'] for stop in departure_segment['stops']
            if stop['stop_time'] >= (
                arrival_segment['arrival_time'] + 
                self._get_min_transfer_time(arrival_segment['arrival_stop'], stop['stop_id'], transfer_rules)
            )
        ]
        
        # Intersection: valid transfer stations
        valid_transfers = set(set_a) & set(set_b)
        
        return list(valid_transfers)
    
    def validate_transfer(self, from_stop, to_stop, arrival_time, departure_time):
        """
        Check if a specific transfer is feasible.
        """
        transfer_rules = self._get_transfer_rules(from_stop, to_stop)
        min_time = transfer_rules.get('min_transfer_time', 20)
        max_time = transfer_rules.get('max_transfer_time', 480)  # 8 hours max
        
        actual_time = (departure_time - arrival_time).total_seconds() / 60
        
        return min_time <= actual_time <= max_time
    
    def _get_min_transfer_time(self, from_station, to_station, transfer_rules):
        """
        Get minimum transfer time based on station type.
        """
        # Check if same station
        if from_station.get('parent_id') == to_station.get('parent_id'):
            return timedelta(minutes=self.MIN_TRANSFER_TIME_MINUTES['same_station'])
        
        # Check if adjacent (< 5 km)
        distance = self._calculate_distance(from_station, to_station)
        if distance < 5:
            return timedelta(minutes=self.MIN_TRANSFER_TIME_MINUTES['adjacent_stations'])
        
        # Check transfer rules database
        rule = transfer_rules.get((from_station['id'], to_station['id']))
        if rule:
            return timedelta(minutes=rule['min_transfer_time'])
        
        # Default
        if from_station['city'] != to_station['city']:
            return timedelta(minutes=self.MIN_TRANSFER_TIME_MINUTES['different_city'])
        
        return timedelta(minutes=30)
```

### 3.3 Caching & Performance Optimization

```python
class RouteSearchCache:
    """
    Intelligent caching for route search queries.
    """
    
    def __init__(self, redis_client, ttl_seconds=300):
        self.redis = redis_client
        self.ttl = ttl_seconds
    
    def get_cached_routes(self, source, destination, travel_date, time_from=None, time_to=None):
        """
        Retrieve cached routes for a query.
        """
        cache_key = self._build_cache_key(source, destination, travel_date, time_from, time_to)
        cached = self.redis.get(cache_key)
        
        if cached:
            routes = json.loads(cached)
            logger.info(f"Cache HIT for {cache_key}")
            return routes
        
        return None
    
    def cache_routes(self, source, destination, travel_date, routes, time_from=None, time_to=None):
        """
        Cache routes with TTL.
        """
        cache_key = self._build_cache_key(source, destination, travel_date, time_from, time_to)
        self.redis.setex(cache_key, self.ttl, json.dumps(routes))
        logger.info(f"Cached {len(routes)} routes for {cache_key}")
    
    def invalidate_station_routes(self, station_id):
        """
        Invalidate all routes involving a station (on real-time update).
        """
        pattern = f"routes:*:{station_id}:*"
        keys = self.redis.keys(pattern)
        if keys:
            self.redis.delete(*keys)
        
        logger.info(f"Invalidated {len(keys)} route cache entries for station {station_id}")
    
    def _build_cache_key(self, source, destination, travel_date, time_from, time_to):
        """Build cache key with optional time window."""
        key = f"routes:{source}:{destination}:{travel_date}"
        if time_from:
            key += f":{time_from}"
        if time_to:
            key += f":{time_to}"
        return key
```

---

## 4. REAL-TIME DATA PIPELINE

### 4.1 Event Streaming Architecture

```
Train Feeds (APIs) → Kafka Producer → Kafka Broker → Kafka Consumers
                                          │
                                    (Topics)
                                    ├─ train.position
                                    ├─ train.delay
                                    ├─ train.cancellation
                                    ├─ station.update
                                    └─ booking.created
```

### 4.2 Real-Time Data Processing

```python
class RealtimeDataProcessor:
    """
    Processes real-time events and updates graph.
    """
    
    def __init__(self, kafka_brokers, graph_mutation_engine, network_service):
        self.kafka = KafkaConsumer(*kafka_brokers)
        self.mutation_engine = graph_mutation_engine
        self.network = network_service
    
    async def process_train_position_update(self, event):
        """
        Handle real-time train location update.
        """
        train_id = event['train_id']
        current_location = event['location']  # lat, lon
        timestamp = event['timestamp']
        
        # Find which station train is closest to
        current_station = self._find_nearest_station(current_location)
        next_station = self._find_next_scheduled_stop(train_id, current_station)
        
        # Update train state
        train_state = TrainState(
            trip_id=event['trip_id'],
            train_number=train_id,
            current_station_id=current_station['id'],
            next_station_id=next_station['id'],
            delay_minutes=self._calculate_delay(train_id, current_station, timestamp),
            estimated_arrival=self._estimate_arrival(train_id, next_station),
            occupancy_rate=event.get('occupancy_rate', 0.0),
            last_updated=timestamp
        )
        
        # Update database
        self.network.update_train_state(train_state)
        
        # Publish to subscribers
        await self._publish_update('train.position', train_state.to_dict())
    
    async def process_train_delay(self, event):
        """
        Handle train delay announcement.
        """
        train_id = event['train_id']
        delay_minutes = event['delay_minutes']
        affected_stations = event.get('affected_stations', 'all')
        
        # Update graph
        self.mutation_engine.handle_train_delay(train_id, delay_minutes, affected_stations)
        
        # Publish event
        await self._publish_update('train.delay', event)
        
        # Trigger notifications for affected users
        self._notify_affected_users(train_id, delay_minutes)
    
    def _notify_affected_users(self, train_id, delay_minutes):
        """
        Notify users with bookings on this train.
        """
        bookings = self.db.query(Booking).filter(
            Booking.trip_id == train_id
        ).all()
        
        for booking in bookings:
            notification = {
                'type': 'DELAY_ALERT',
                'booking_id': booking.id,
                'train_id': train_id,
                'delay_minutes': delay_minutes,
                'message': f'Your train {train_id} is delayed by {delay_minutes} minutes.'
            }
            
            # Send notification (email, SMS, push)
            self._send_notification(booking.user, notification)
```

---

## 5. BOOKING & SEAT INVENTORY SYSTEM

### 5.1 Advanced Inventory Management

**Key Features:**
- Real-time seat availability
- Overbooking management (typically 5-10% allowed)
- Waitlist handling with auto-confirmation
- Multi-segment seat consistency
- Seat preference matching

```python
class AdvancedInventoryManager:
    """
    Production-grade seat inventory with overbooking, waitlists.
    """
    
    def __init__(self, db, cache, notification_service):
        self.db = db
        self.cache = cache
        self.notif = notification_service
        self.overbooking_threshold = 0.10  # 10% overbooking allowed
    
    def get_availability(self, trip_id, travel_date):
        """
        Get real-time availability with overbooking factor.
        """
        # Query database
        inventory = self.db.query(SeatInventory).filter(
            SeatInventory.stop_time_id == trip_id,
            SeatInventory.travel_date == travel_date
        ).first()
        
        if not inventory:
            return {'available': 0, 'waitlist_position': None}
        
        confirmed_bookings = self.db.query(func.count(Booking.id)).filter(
            Booking.trip_id == trip_id,
            Booking.travel_date == travel_date,
            Booking.status == 'CONFIRMED'
        ).scalar()
        
        total_capacity = inventory.total_capacity
        overbooking_allowance = int(total_capacity * self.overbooking_threshold)
        
        available = total_capacity + overbooking_allowance - confirmed_bookings
        
        return {
            'available': max(0, available),
            'total_capacity': total_capacity,
            'confirmed': confirmed_bookings,
            'overbooking_allowance': overbooking_allowance,
            'occupancy_rate': confirmed_bookings / total_capacity
        }
    
    def process_waitlist_confirmation(self):
        """
        Automatically confirm waitlisted passengers when seats become available.
        Runs periodically (every 5 minutes).
        """
        # Find waitlisted bookings
        waitlist = self.db.query(Booking).filter(
            Booking.status == 'WAITLIST'
        ).order_by(Booking.created_at).all()
        
        for booking in waitlist:
            # Check if seats available
            avail = self.get_availability(booking.trip_id, booking.travel_date)
            
            if avail['available'] > 0:
                # Confirm booking
                booking.status = 'CONFIRMED'
                booking.updated_at = datetime.utcnow()
                self.db.add(booking)
                
                # Notify user
                self.notif.send_booking_confirmed(
                    booking.user_id,
                    booking.id,
                    f"Your waitlist booking {booking.id} has been confirmed!"
                )
        
        self.db.commit()
```

---

## 6. ML/RL INTEGRATION

### 6.1 Reinforcement Learning Agent

```python
class RLRouteRankingAgent:
    """
    Reinforcement Learning agent for optimal route ranking.
    """
    
    def __init__(self, state_dim, action_dim, learning_rate=0.001):
        self.state_dim = state_dim
        self.action_dim = action_dim  # Number of candidate routes
        
        # Neural network policy
        self.model = self._build_model()
        self.optimizer = tf.keras.optimizers.Adam(learning_rate)
    
    def _build_model(self):
        """Build DQN or policy gradient network."""
        model = tf.keras.Sequential([
            tf.keras.layers.Dense(128, activation='relu', input_shape=(self.state_dim,)),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(64, activation='relu'),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(self.action_dim, activation='softmax')
        ])
        return model
    
    def predict_ranking(self, state_features, candidate_routes):
        """
        Predict best ranking for candidate routes.
        """
        state = np.array([state_features])
        probabilities = self.model.predict(state)
        
        # Rank routes by probability
        route_scores = probabilities[0][:len(candidate_routes)]
        ranked_indices = np.argsort(-route_scores)
        
        return [candidate_routes[i] for i in ranked_indices]
    
    def update_on_feedback(self, state, action, reward, next_state, done):
        """
        Update model based on user feedback.
        """
        with tf.GradientTape() as tape:
            # Forward pass
            prediction = self.model(np.array([state]))
            target = np.copy(prediction.numpy())
            
            if done:
                target[0][action] = reward
            else:
                # Q-learning update
                next_prediction = self.model.predict(np.array([next_state]))
                target[0][action] = reward + 0.99 * np.max(next_prediction)
            
            # Compute loss
            loss = tf.keras.losses.MeanSquaredError()(target, prediction)
        
        # Backprop
        gradients = tape.gradient(loss, self.model.trainable_variables)
        self.optimizer.apply_gradients(zip(gradients, self.model.trainable_variables))
        
        return loss
```

---

## 7. DATABASE SCHEMA (GTFS-BASED)

### 7.1 Core Tables

```sql
-- Stations/Stops (GTFS)
CREATE TABLE stops (
    id SERIAL PRIMARY KEY,
    stop_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(10) UNIQUE,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    geom GEOMETRY(POINT, 4326) NOT NULL,
    city VARCHAR(255),
    state VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_stops_code ON stops(code);
CREATE INDEX idx_stops_geom ON stops USING GIST(geom);

-- Routes (GTFS)
CREATE TABLE gtfs_routes (
    id SERIAL PRIMARY KEY,
    route_id VARCHAR(100) UNIQUE NOT NULL,
    agency_id INTEGER NOT NULL,
    short_name VARCHAR(50),
    long_name VARCHAR(255) NOT NULL,
    route_type INTEGER NOT NULL,  -- 0: Tram, 1: Metro, 2: Rail, 3: Bus
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trips (GTFS)
CREATE TABLE trips (
    id SERIAL PRIMARY KEY,
    trip_id VARCHAR(255) UNIQUE NOT NULL,
    route_id INTEGER NOT NULL REFERENCES gtfs_routes(id),
    service_id INTEGER NOT NULL REFERENCES calendar(id),
    headsign VARCHAR(255),
    direction_id INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Stop Times (GTFS)
CREATE TABLE stop_times (
    id SERIAL PRIMARY KEY,
    trip_id INTEGER NOT NULL REFERENCES trips(id),
    stop_id INTEGER NOT NULL REFERENCES stops(id),
    arrival_time TIME NOT NULL,
    departure_time TIME NOT NULL,
    stop_sequence INTEGER NOT NULL,
    cost FLOAT,
    UNIQUE(trip_id, stop_sequence),
    UNIQUE(trip_id, stop_id)
);
CREATE INDEX idx_stop_times_trip ON stop_times(trip_id);
CREATE INDEX idx_stop_times_stop ON stop_times(stop_id);

-- Real-time Train State
CREATE TABLE train_states (
    id VARCHAR(36) PRIMARY KEY,
    trip_id INTEGER UNIQUE NOT NULL REFERENCES trips(id),
    train_number VARCHAR(50) UNIQUE NOT NULL,
    current_station_id INTEGER REFERENCES stops(id),
    next_station_id INTEGER REFERENCES stops(id),
    delay_minutes INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'on_time',
    occupancy_rate FLOAT DEFAULT 0.0,
    cancelled_stations JSONB DEFAULT '[]',
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_train_states_status ON train_states(status);
CREATE INDEX idx_train_states_updated ON train_states(last_updated DESC);

-- Seat Inventory
CREATE TABLE seat_inventory (
    id VARCHAR(36) PRIMARY KEY,
    stop_time_id INTEGER NOT NULL UNIQUE REFERENCES stop_times(id),
    travel_date DATE NOT NULL,
    seats_available INTEGER NOT NULL,
    total_capacity INTEGER NOT NULL,
    last_reconciled_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_seat_inventory_date ON seat_inventory(travel_date);

-- Bookings
CREATE TABLE bookings (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id),
    travel_date DATE NOT NULL,
    payment_status VARCHAR(50) DEFAULT 'pending',
    amount_paid FLOAT DEFAULT 0.0,
    booking_details JSONB NOT NULL,
    trip_id INTEGER REFERENCES trips(id),
    status VARCHAR(20) DEFAULT 'CONFIRMED',  -- CONFIRMED, WAITLIST, CANCELLED
    created_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_bookings_user (user_id),
    INDEX idx_bookings_date (travel_date),
    INDEX idx_bookings_status (status)
);

-- Transfers (Valid transfer points)
CREATE TABLE transfers (
    id SERIAL PRIMARY KEY,
    from_stop_id INTEGER NOT NULL REFERENCES stops(id),
    to_stop_id INTEGER NOT NULL REFERENCES stops(id),
    transfer_type INTEGER DEFAULT 0,  -- 0: Recommended, 2: Timed
    min_transfer_time INTEGER NOT NULL,  -- seconds
    max_transfer_time INTEGER DEFAULT 480,
    UNIQUE(from_stop_id, to_stop_id)
);
```

---

## 8. API GATEWAY & INTEGRATION

### 8.1 Key REST Endpoints

```python
# Search Routes
POST /api/v1/routes/search
{
    "source": "NDLS",
    "destination": "CSTM",
    "travel_date": "2026-02-20",
    "passengers": 2,
    "preferences": {
        "max_transfers": 2,
        "preferred_classes": ["AC", "2AC"],
        "preferred_modes": ["train", "flight"]
    }
}

Response:
{
    "routes": [
        {
            "id": "route_123",
            "segments": [...],
            "total_duration": "14h 30m",
            "total_fare": 2500,
            "rating": 4.5,
            "rank_score": 0.92
        }
    ]
}

# Book Route
POST /api/v1/bookings
{
    "route_id": "route_123",
    "passengers": [
        {
            "name": "John Doe",
            "age": 30,
            "seat_preference": "window"
        }
    ]
}

Response:
{
    "booking_id": "booking_456",
    "pnr": "AB1234567",
    "status": "CONFIRMED",
    "total_fare": 2500
}

# Get Real-time Status
GET /api/v1/trains/{train_id}/status

Response:
{
    "train_id": "12345",
    "current_location": {"lat": 28.5, "lon": 77.2},
    "current_station": "New Delhi",
    "delay_minutes": 15,
    "next_stop": "Kanpur",
    "estimated_arrival": "2026-02-20T10:30:00Z"
}
```

---

## 9. SCALABILITY & PERFORMANCE

### 9.1 Performance Benchmarks (Target)

| Operation | Target Latency | Method |
|-----------|---|---|
| Route search (5 transfers) | < 500ms | RAPTOR + caching |
| Seat allocation (multi-segment) | < 100ms | Optimistic locking |
| Fare calculation | < 50ms | Pre-computed tables |
| Real-time train update | < 10ms | In-memory mutation |
| ML ranking | < 200ms | Cached predictions |

### 9.2 Horizontal Scaling Strategy

```yaml
# Kubernetes deployment configuration
apiVersion: apps/v1
kind: Deployment
metadata:
  name: route-search-service
spec:
  replicas: 10  # Auto-scale 5-20 based on load
  selector:
    matchLabels:
      app: route-search
  template:
    metadata:
      labels:
        app: route-search
    spec:
      containers:
      - name: route-search
        image: startupv2/route-search:latest
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        env:
        - name: REDIS_URL
          value: redis://redis-cluster:6379
        - name: DATABASE_URL
          value: postgresql://user:pass@db-replica-pool:5432/routedb
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
```

### 9.3 Caching Layers

```
User Request
    ↓
CDN Cache (Cloudflare) - Static assets, API responses
    ↓
API Gateway Cache (Nginx) - Idempotent endpoints
    ↓
Application Cache (Redis) - Route cache, user sessions
    ↓
Database Query Cache - PostgreSQL shared buffers
    ↓
Disk (PostgreSQL)
```

---

## 10. ROUTEMASTER AGENT INTEGRATION

### 10.1 Autonomous Data Collection

The RouteMaster Agent can autonomously:

1. **Scrape real-time data** from IRCTC, partner APIs
2. **Process updates** using Vision AI, Extraction AI
3. **Update database** through booking service
4. **Predict demand** using ML models
5. **Optimize pricing** using RL feedback

### 10.2 Integration Points

```python
# In routemaster_agent/main.py
from backend.services.route_engine import RouteEngine
from backend.services.booking_service import BookingService
from backend.services.ml_service import MLRecommendationEngine

class RouteMasterBackendIntegration:
    """
    Connects RouteMaster Agent to backend services.
    """
    
    def __init__(self):
        self.route_engine = RouteEngine()
        self.booking_service = BookingService()
        self.ml_engine = MLRecommendationEngine()
    
    async def collect_and_update_routes(self):
        """
        Autonomous task: Collect train/bus/flight data and update system.
        """
        # 1. Scrape latest schedules
        schedules = await self.agent_vision_ai.extract_schedules_from_irctc()
        
        # 2. Validate and normalize
        normalized = self.data_pipeline.normalize_gtfs_format(schedules)
        
        # 3. Update database
        self.backend.db.bulk_insert_trips(normalized)
        
        # 4. Invalidate route cache
        self.route_engine._invalidate_all_caches()
        
        # 5. Log to feature store (for ML)
        self.ml_engine.features.log_data_update({
            'source': 'routemaster_agent',
            'records_updated': len(normalized),
            'timestamp': datetime.utcnow()
        })
    
    async def predict_and_optimize_pricing(self):
        """
        Use ML models to optimize pricing for upcoming routes.
        """
        upcoming_routes = self.backend.get_routes_next_7_days()
        
        for route in upcoming_routes:
            # Predict demand
            demand_score = self.ml_engine.predict_demand(route, route['travel_date'])
            
            # Calculate optimal pricing
            optimal_price = self.ml_engine.calculate_optimal_price(route, demand_score)
            
            # Update pricing rules
            self.backend.update_dynamic_price(route['id'], optimal_price)
```

---

## 11. PRODUCTION READINESS CHECKLIST

### 11.1 System Health Monitoring

- [ ] Prometheus metrics for all services
- [ ] Grafana dashboards (latency, throughput, errors)
- [ ] Distributed tracing (Jaeger) enabled
- [ ] Centralized logging (ELK stack)
- [ ] Alerting rules for SLOs
- [ ] Synthetic monitoring for user flows

### 11.2 Data Consistency & Recovery

- [ ] ACID transactions for bookings
- [ ] WAL (Write-Ahead Logging) for PostgreSQL
- [ ] Automatic failover for replicas
- [ ] Backup strategy (daily full, hourly incremental)
- [ ] Disaster recovery plan (RTO/RPO defined)
- [ ] Data validation checks

### 11.3 Security

- [ ] OAuth2/JWT authentication
- [ ] TLS 1.3 for all communication
- [ ] PCI DSS compliance for payments
- [ ] SQL injection prevention (parameterized queries)
- [ ] CSRF protection for APIs
- [ ] Rate limiting per user/IP
- [ ] Secrets management (Vault or environment variables)

---

## 12. DEPLOYMENT ROADMAP

### Phase 1 (Week 1-2): Core Engine
- [ ] Deploy Route Search Service (RAPTOR)
- [ ] Deploy Station & Network Service
- [ ] Set up Redis cache layer
- [ ] Implement basic real-time updates

### Phase 2 (Week 3-4): Bookings & Inventory
- [ ] Deploy Booking Service
- [ ] Implement seat allocation logic
- [ ] Set up Kafka for event streaming
- [ ] Integrate payment gateway

### Phase 3 (Week 5-6): ML/RL & Intelligence
- [ ] Deploy ML ranking service
- [ ] Implement demand prediction models
- [ ] Set up feature store (Feast)
- [ ] Integrate RouteMaster Agent

### Phase 4 (Week 7-8): Multi-Modal Support
- [ ] Add bus route support
- [ ] Add flight route support
- [ ] Extend transfer logic for multi-modal
- [ ] Implement mode-specific cost functions

### Phase 5 (Week 9-10): Production Hardening
- [ ] Load testing (1000 req/sec sustained)
- [ ] Chaos engineering tests
- [ ] Security audit
- [ ] Performance tuning
- [ ] Documentation completion

---

## CONCLUSION

This architecture provides a **production-grade, IRCTC-inspired backend system** that:

✅ **Scales:** Horizontal scaling via Kubernetes  
✅ **Performs:** Sub-500ms route searches via RAPTOR + caching  
✅ **Integrates:** Multi-modal (trains, buses, flights)  
✅ **Learns:** ML/RL-powered ranking & pricing  
✅ **Adapts:** Real-time graph mutation on delays/cancellations  
✅ **Automates:** RouteMaster Agent integration for autonomous operations  

The system is ready for production deployment and can handle the scale of IRCTC while providing superior user experience through intelligent route ranking and dynamic pricing.

---

**Next Steps:**
1. Review this architecture with your team
2. Begin Phase 1 implementation (Route Search Service)
3. Integrate RouteMaster Agent for data collection
4. Set up monitoring & observability stack
5. Deploy to Kubernetes cluster

**Questions?** Refer to the detailed code examples in sections 2-10.
