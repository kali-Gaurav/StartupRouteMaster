# MVP Implementation Manifest
**Goal**: Build production-ready MVP for 10k users/month with demand-based redistribution, multi-transfer routes, and SOS safety features

## Current State Assessment
- ✅ Search service and Telegram bot integrated
- ✅ Route algorithms (RAPTOR, TBR) documented
- ✅ FastAPI backend with health checks
- ✅ MCP Supabase integration configured
- ❌ Booking workflow not implemented
- ❌ Payment processing missing
- ❌ SOS safety features not integrated
- ❌ Multi-transfer route generation incomplete
- ❌ No deployment configuration

## Implementation Plan (8 Weeks)

### Phase 1: Core Booking Workflow (Week 1-2)
1. **Create Booking API Service**
   - POST /api/v1/bookings endpoint
   - Booking state machine implementation
   - PNR generation logic
   - Idempotency handling

2. **Seat Allocation Integration**
   - Connect to InventoryService
   - Implement seat locking with timeout
   - Waitlist management

3. **Passenger Details Collection**
   - Passenger schema and validation
   - Berth preference handling
   - Family grouping logic

### Phase 2: Payment Processing (Week 3)
1. **Payment Gateway Integration**
   - UPI payment flow
   - Payment webhook handler
   - Payment state management

2. **Transaction Management**
   - Payment records database
   - Refund processing
   - Reconciliation reports

### Phase 3: Multi-Transfer Routes (Week 4)
1. **RAPTOR Algorithm Implementation**
   - Multi-leg route discovery
   - Hub intersection algorithm
   - Route optimization

2. **Route Merging & Deduplication**
   - Merge direct + transfer routes
   - Remove duplicates
   - Sort by departure time

### Phase 4: SOS Safety Features (Week 5)
1. **Safety Index Integration**
   - Real-time safety scoring
   - Station safety ratings
   - Coach safety indicators

2. **Emergency Features**
   - SOS button functionality
   - Location sharing
   - Emergency contacts
   - Safety alerts

### Phase 5: Demand-Based Redistribution (Week 6)
1. **Dynamic Pricing Engine**
   - Demand surge detection
   - Price adjustment algorithms
   - Capacity redistribution

2. **Waitlist Management**
   - Auto-confirmation logic
   - Probability calculations
   - Notification system

### Phase 6: Deployment & Scale (Week 7-8)
1. **Infrastructure Setup**
   - Docker configuration
   - Database setup (Supabase)
   - Redis caching layer
   - Load balancing

2. **MCP Integration**
   - Supabase database connection
   - User authentication
   - Booking persistence

3. **Performance Optimization**
   - Caching strategy
   - Query optimization
   - Load testing for 10k users

## Success Criteria
- [ ] Search returns results in <2 seconds
- [ ] Booking flow completes in <30 seconds
- [ ] Payment processing works end-to-end
- [ ] Multi-transfer routes discovered correctly
- [ ] SOS safety features functional
- [ ] System handles 10k concurrent users
- [ ] 99.9% uptime during 2-month pilot