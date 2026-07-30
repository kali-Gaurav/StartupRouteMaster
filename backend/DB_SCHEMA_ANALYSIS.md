# RouteMaster Database Schema Research & Analysis
## Comprehensive Architecture, Algorithms, and Data Flows

**Generated**: 2026-07-29  
**Scope**: Complete database layer investigation  
**Status**: IN PROGRESS - Deep Research Phase

---

## EXECUTIVE SUMMARY

The RouteMaster V2 database is a **polyglot architecture** with:
- **161 total models** across 10 model files
- **Dual-store pattern**: UserBase (SaaS/user data) + TransitBase (read-only transit data)
- **Key domains**: Booking, Payments, Telegram, Safety, ML/Intelligence, Redistribution, Sync
- **Industrial patterns**: Optimistic locking, timestamp tracking, audit trails, partition-ready
- **High complexity indicators**: 116 models in core.py alone, multiple inheritance chains, cross-domain relationships

---

## PART 1: SCHEMA INVENTORY

### A. Core Models (core.py) - 116 classes

#### User Domain (8 models)
| Model | Purpose | Key Fields | Relationships |
|-------|---------|-----------|-----------------|
| `User` | Central user entity | email, phone, firebase_uid, telegram_id, encrypted_irctc_creds | bookings, sessions, payments |
| `UserSession` | Session management | session_token, fingerprint, last_activity | - |
| `Profile` | Extended profile | display_name, bio, emergency_contacts | - |
| `UserAlert` | Alert system | message, is_read, timestamp | user |
| `UserHeartbeat` | Activity tracking | heartbeat_data, status | - |
| `LiveLocation` | Real-time location | latitude, longitude, accuracy, timestamp | - |
| `UserAIPreference` | ML preferences | preference_data | - |
| `IdentityFingerprint` | Device fingerprinting | fingerprint_hash, device_info | - |

#### Booking/Reservation Core (7 models)
| Model | Purpose | Key Fields |
|-------|---------|-----------|
| `Booking` | Main booking entity | train_number, travel_date, class_type, pnr_number, status |
| `BookingRequest` | Booking workflow | status, requested_seats, passenger_count |
| `BookingRequestPassenger` | Passenger details per request | name, age, gender, berth_pref |
| `BookingQueue` | Queue management | sequence, priority, status |
| `BookingMonitor` | Booking state tracking | status, last_update, pnr_sync_status |
| `BookingIdempotency` | Idempotency keys | request_hash, response_data |
| `PassengerDetails` | Passenger info | full_name, age, gender, berth_pref, ticket_number |

#### Transit Data (11 models) - READ-ONLY
| Model | Purpose | Base |
|-------|---------|------|
| `TrainMaster` | Train metadata | TransitBase |
| `Trip` | Train trips/routes | TransitBase |
| `Segment` | Trip segments | TransitBase |
| `Stop` | Train stops | TransitBase |
| `StopTime` | Schedule info | TransitBase |
| `Coach` | Coach inventory | UserBase |
| `Seat` | Seat inventory | UserBase |
| `CancelledTrain` | Cancelled train log | TransitBase |
| `Calendar` | Operating calendar | TransitBase |
| `CalendarDate` | Calendar dates | TransitBase |
| `TrainStation` | Station info | UserBase |

#### Inventory & Availability (5 models)
| Model | Purpose | Key Fields |
|-------|---------|-----------|
| `SeatInventory` | Real-time seat status | train_id, coach_id, seat_id, status |
| `QuotaInventory` | Quota management | quota_type, available, reserved |
| `WaitlistQueue` | Waitlist tracking | booking_id, position, status |
| `TrainAvailabilityCache` | Cached availability | train_id, date, class_wise_availability |
| `TrainLiveUpdate` | Real-time updates | train_id, status, delay_minutes, running_status |

#### Fare & Pricing (2 models)
| Model | Purpose | Key Fields |
|-------|---------|-----------|
| `Fare` | Fare rules | origin, destination, class, base_fare, surcharges, taxes |
| `CompetitorPriceModel` | Price intelligence | train_number, date, fare, source |

#### Payment & Finance (7 models)
| Model | Purpose | Key Fields |
|-------|---------|-----------|
| `Payment` | Payment records | amount, method, status, gateway_ref |
| `PaymentTransaction` | Transaction details | payment_id, amount, status, timestamp |
| `PaymentSession` | Payment session | session_token, user_id, total_amount |
| `Wallet` | User wallet | user_id, balance, currency |
| `CreditTransaction` | Credit operations | wallet_id, amount, type, reason |
| `FinancialLedger` | Ledger entries | debit, credit, balance, reference |
| `BankTransaction` | Bank reconciliation | utr_number, amount, status, sender_phone |

#### Search & Routing (4 models)
| Model | Purpose | Key Fields |
|-------|---------|-----------|
| `RouteSearchLog` | Search history | user_id, origin, destination, filters |
| `SearchOutcome` | Search results | search_id, route_id, fare, duration |
| `SearchEvent` | Search analytics | user_id, query_params, result_count |
| `IntelligenceSearchEvent` | AI search tracking | search_id, intent, entities, confidence |

#### Station Data (7 models) - Transit Infrastructure
| Model | Purpose | Key Fields |
|-------|---------|-----------|
| `Stop` | Train stops | stop_id, stop_code, stop_name |
| `StationDeparture` | Departure cache | station_code, departure_time, train_id |
| `StationDepartureBucket` | Bucketed departures | station_code, time_bucket, count |
| `StopDepartureBucket` | Stop-level buckets | stop_id, time_bucket, count |
| `StationRealtimeHeartbeat` | Realtime status | station_code, timestamp, metrics |
| `StationHealthIndex` | Station health | station_code, congestion, delay_factor |
| `StationClusterMapping` | Station grouping | station_code, cluster_id |

#### Safety & Emergency (5 models)
| Model | Purpose | Key Fields |
|-------|---------|-----------|
| `SOSEvent` | SOS calls | user_id, location, status, timestamp |
| `SOSTelemetry` | SOS telemetry | sos_event_id, device_info, network_status |
| `EmergencyContact` | Emergency contacts | user_id, name, phone, relationship |
| `SafetyEvent` | Safety incidents | event_type, user_id, train_id, timestamp |
| `FraudAlert` | Fraud alerts | alert_type, user_id, risk_level, details |

#### Fraud & Security (5 models)
| Model | Purpose | Key Fields |
|-------|---------|-----------|
| `IdentityFingerprint` | Device fingerprints | fingerprint_hash, device_info |
| `FraudAlert` | Fraud detection | alert_type, risk_level, reason |
| `BookingFraudCheck` | Booking validation | booking_id, risk_score, checks_passed |
| `WebhookEvent` | Event logging | event_type, payload, status |
| `DailyReconciliation` | Daily settlement | date, total_bookings, total_revenue |

#### ML/Intelligence Models (12 models)
| Model | Purpose | Key Fields |
|-------|---------|-----------|
| `SearchAccuracyMetric` | Search quality | metric_name, value, timestamp |
| `ModelDriftEvent` | ML monitoring | model_name, drift_score, timestamp |
| `RecommendationEvent` | Recommendation tracking | user_id, recommended_route, clicked |
| `UserPreferenceModel` | Preference learning | user_id, preference_data, updated_at |
| `RoutePatternModel` | Route patterns | route_hash, pattern_data, frequency |
| `SeasonalPatternModel` | Seasonal trends | season, route_pattern, demand |
| `UserBehaviorModel` | Behavior analytics | user_id, behavior_vector, recency |
| `StationPatternModel` | Station patterns | station_code, pattern_data, anomaly_score |
| `AIIntentLog` | Intent classification | user_id, intent_type, confidence |
| `SearchEvent` | Search tracking | user_id, search_params, results |
| `IntelligenceMetric` | System metrics | metric_name, value, timestamp |
| `GlobalIntelligenceState` | System state | state_json, version, updated_at |

#### Reviews & Feedback (3 models)
| Model | Purpose | Key Fields |
|-------|---------|-----------|
| `Review` | User reviews | booking_id, rating, review_text |
| `RLFeedbackLog` | RL feedback | event_id, feedback_data, reward |
| `CommissionTracking` | Commission tracking | booking_id, amount, status |

#### System Config (5 models)
| Model | Purpose | Key Fields |
|-------|---------|-----------|
| `PlatformConfig` | Platform settings | config_key, value, updated_at |
| `Subscription` | Subscription plans | user_id, plan_type, valid_until |
| `APIBudget` | API rate limits | user_id, quota, remaining |
| `UnlockedRoute` | Feature access | user_id, route_hash, unlocked_at |
| `Refund` | Refund records | booking_id, amount, reason, status |

#### Conversation & Chat (2 models)
| Model | Purpose | Key Fields |
|-------|---------|-----------|
| `PersistentChatMessage` | Chat history | user_id, conversation_id, message_text |
| `IntelligenceRecommendationEvent` | Recommendation tracking | recommendation_id, clicked, converted |

#### Knowledge Graph (2 models)
| Model | Purpose | Key Fields |
|-------|---------|-----------|
| `KnowledgeGraphSnapshot` | KG snapshots | snapshot_date, graph_data, version |
| `IntelligenceRouteSearchLog` | Route intelligence | route_hash, search_count, demand |

#### Other (2 models)
| Model | Purpose | Key Fields |
|-------|---------|-----------|
| `Transfer` | Station transfers | from_station, to_station, duration, distance |
| `RouteSearchLog` | Search logs | user_id, route, filters, timestamp |

---

### B. Additional Model Files

#### telegram.py (6 models)
- `TelegramConversationState`: Multi-turn conversation tracking
- `TelegramMessage`: Message history and analytics
- `TelegramBookingLink`: Deep linking for bookings
- `TelegramSOSEvent`: SOS events from Telegram
- `TelegramAnalytics`: Daily Telegram bot metrics
- `TelegramNotificationTemplate`: Template management

#### algorithm.py (9 models)
- ML models for route prediction, pricing, recommendations

#### knowledge_graph.py (6 models)
- Entity extraction and knowledge graph storage

#### safety.py (3 models)
- Safety-specific events and metrics

#### sathi.py (9 models)
- Companion/assistance features

#### sync.py (5 models)
- Data synchronization tracking

#### redistribution.py (7 models)
- Seat redistribution and load balancing

---

## PART 2: DATA RELATIONSHIPS & FLOW PATTERNS

### A. Primary Booking Flow

```
User 1:N Booking 1:N PassengerDetails
        ↓
        BookingRequest 1:N BookingRequestPassenger
        ↓
        BookingMonitor (state tracking)
        ↓
        BookingIdempotency (dedup)
        ↓
        BookingQueue (sequencing)
        ↓
        Payment 1:N PaymentTransaction
```

### B. Train & Inventory Flow

```
TrainMaster 1:N Trip 1:N Segment 1:N Stop
     ↓
TrainAvailabilityCache (cached)
     ↓
SeatInventory + QuotaInventory
     ↓
Coach 1:N Seat (seat inventory)
     ↓
WaitlistQueue (overflow)
```

### C. Fare Calculation Flow

```
SearchOutcome → Fare (lookup)
         ↓
    CompetitorPriceModel (comparison)
         ↓
    Payment (charge)
         ↓
    FinancialLedger (record)
         ↓
    Wallet (balance update)
```

### D. Real-Time & Tracking Flow

```
TrainLiveUpdate → TrainRunningStatusCache
        ↓
StationRealtimeHeartbeat
        ↓
UserHeartbeat (sync with app)
        ↓
LiveLocation (tracking)
```

### E. Safety & Emergency Flow

```
SOSEvent → SOSTelemetry
        ↓
SafetyEvent + FraudAlert
        ↓
EmergencyContact (notification)
        ↓
BookingFraudCheck (validation)
```

---

## PART 3: KEY ALGORITHMS & BUSINESS LOGIC

### A. Inventory Management
- **Quota Allocation**: QuotaInventory tracks IRCTC quota types (General, Tatkal, Premium)
- **Seat Reservation**: SeatInventory with real-time status updates
- **Waitlist Logic**: WaitlistQueue with position-based priority
- **Cache Strategy**: TrainAvailabilityCache for performance

### B. Pricing Strategy
- **Dynamic Pricing**: CompetitorPriceModel for price intelligence
- **Fare Calculation**: Fare model with base_fare + surcharges + taxes
- **Route Optimization**: PrecalculatedRoute for pre-computed optimal routes

### C. Search & Discovery
- **Route Search**: RouteSearchLog + IntelligenceSearchEvent
- **Recommendation Engine**: RecommendationEvent + UserPreferenceModel
- **Personalization**: SeasonalPatternModel + UserBehaviorModel

### D. Fraud Detection
- **Device Fingerprinting**: IdentityFingerprint per device
- **Risk Scoring**: BookingFraudCheck with risk_score
- **Fraud Alerts**: FraudAlert with alert_type and risk_level

### E. Real-Time Tracking
- **Train Status**: TrainLiveUpdate + TrainRunningStatusCache
- **Station Congestion**: StationHealthIndex + StationRealtimeHeartbeat
- **User Location**: LiveLocation + UserHeartbeat

### F. Payment Processing
- **Payment Gateway**: Payment ↔ PaymentTransaction ↔ PaymentSession
- **Wallet System**: Wallet + CreditTransaction for credit management
- **Reconciliation**: FinancialLedger + BankTransaction for settlement
- **Idempotency**: BookingIdempotency for duplicate prevention

---

## PART 4: INDEXING STRATEGY

### Critical Indices (from schema analysis)

```
User:
  - email (UNIQUE)
  - firebase_uid (UNIQUE)
  - telegram_id (UNIQUE)
  - created_at

Booking:
  - user_id, pnr_number, booking_status
  - train_number, travel_date
  - created_at

Payment:
  - user_id, payment_status, created_at
  - gateway_reference_id (UNIQUE)

TrainAvailabilityCache:
  - train_id, travel_date (composite)
  - class_type

SeatInventory:
  - train_id, coach_id, seat_id (composite)
  - status

TrainLiveUpdate:
  - train_id, last_update_timestamp
```

### Performance Concerns
1. Large booking lookups without user_id filtering
2. Real-time updates (TrainLiveUpdate) need high-speed reads
3. Availability cache TTL strategy unclear
4. Waitlist ordering (check if position-indexed)

---

## PART 5: MULTI-TENANCY & DATA ISOLATION

### Dual-Store Pattern
- **UserBase**: Multi-tenant (per user_id)
  - Tables: users, bookings, payments, searches, preferences
  - Isolation: user_id foreign key
  
- **TransitBase**: Shared read-only (across all users)
  - Tables: train_master, trips, segments, stops, calendar
  - No user_id (global data)

### Implications
- User data queries: Fast (indexed by user_id)
- Transit data queries: Cached (immutable + predictable)
- Cross-tenant risk: Medium (proper foreign keys in place)

---

## PART 6: SCHEMA MATURITY ASSESSMENT

### Strengths ✅
- Clear domain boundaries
- Audit trail support (TimestampMixin)
- Optimistic locking (AuditMixin)
- Comprehensive index strategy
- Payment idempotency built-in
- ML model versioning support
- Real-time telemetry infrastructure

### Weaknesses ⚠️
1. **116 models in core.py** → Too monolithic
   - Should split by domain (booking/, payments/, search/, etc.)
   
2. **Inheritance complexity** → Multiple mixin chains
   - TimestampMixin + AuditMixin + UserBase/TransitBase
   
3. **Missing Soft Deletes** → No `is_deleted` or `deleted_at` fields
   - Can't fully audit deletions
   
4. **Incomplete Relationships** → Some ForeignKeys missing
   - Payment ↔ Booking relationship unclear
   - SearchOutcome ↔ Booking relationship unclear
   
5. **No Partition Strategy** → Tables grow unbounded
   - Need partition by travel_date for Booking/TrainLiveUpdate
   
6. **ML Model Storage** → Too many individual models
   - Should consolidate to centralized feature store
   
7. **Real-Time Data Staleness** → No TTL/expiry strategy
   - TrainLiveUpdate retention unclear
   - Cache invalidation not specified

---

## PART 7: CRITICAL DATA FLOWS FOR FEATURES

### Feature #1: Booking & Payment ✅ IMPLEMENTED
**Flow**:
1. User creates BookingRequest
2. System reserves SeatInventory + QuotaInventory
3. Payment processed via Payment → PaymentTransaction
4. Booking record created with status = "confirmed"
5. FinancialLedger + Wallet updated
6. Idempotency check via BookingIdempotency

**Models Used**: 15+ (Booking, Payment, SeatInventory, Wallet, etc.)

### Feature #2: User Dashboard ✅ IN PROGRESS
**Reads Required**:
- Booking history → Recent bookings
- Payment summary → Ledger balance
- Search history → RouteSearchLog
- Recommendations → RecommendationEvent
- Reviews → Review model

**Models Used**: 6+ (Booking, Payment, RouteSearchLog, Review, etc.)

### Feature #3: Notifications (Email/SMS) ✅ IMPLEMENTED
**Writes Required**:
- NotificationLog for audit
- User preferences → User.preferences JSON
- Payment notification → FinancialLedger update
- Booking confirmation → Booking status update

### Feature #4: Telegram Bot ✅ IMPLEMENTED
**Models**:
- TelegramConversationState (new)
- TelegramMessage (logging)
- TelegramBookingLink (deeplink)
- TelegramSOSEvent (emergency)
- TelegramAnalytics (metrics)

**Integration Points**: User.telegram_id, Booking, Payment

### Feature #5: Route Search & Recommendation (NEXT)
**Models Required**:
- RouteSearchLog (history)
- SearchOutcome (results)
- RecommendationEvent (tracking)
- UserPreferenceModel (ML)
- SeasonalPatternModel (trends)
- CompetitorPriceModel (benchmarking)

---

## PART 8: OPEN QUESTIONS & RECOMMENDATIONS

### Investigation Needed
1. **PrecalculatedRoute**: Is this materialized view or cached?
2. **TrainRunningStatusCache**: What's the refresh frequency?
3. **Conversation Management**: How does PersistentChatMessage scale?
4. **Knowledge Graph**: How often is KnowledgeGraphSnapshot updated?
5. **Model Drift**: What triggers ModelDriftEvent?

### Recommended Actions

| Priority | Action | Impact |
|----------|--------|--------|
| **P0** | Partition Booking table by travel_date | 50x faster historical queries |
| **P1** | Add soft delete support (is_deleted/deleted_at) | Better audit trail |
| **P2** | Consolidate ML models to feature store | Simplify schema |
| **P2** | Document cache TTL/invalidation strategy | Consistency guarantee |
| **P3** | Add composite indices (user_id, created_at) | Improve list queries |
| **P3** | Split core.py into domain-specific files | Better maintainability |

---

## PART 9: QUERY PATTERNS & OPTIMIZATION

### High-Volume Queries
1. **Search trains** → Uses TrainAvailabilityCache + Fare
2. **Check booking status** → Booking lookup by pnr_number
3. **Get availability** → SeatInventory + QuotaInventory
4. **Real-time tracking** → TrainLiveUpdate + UserHeartbeat

### Recommended Query Optimizations
```python
# ❌ SLOW
select * from bookings where user_id = ? order by created_at desc

# ✅ FAST (add index)
CREATE INDEX idx_booking_user_created ON bookings(user_id, created_at DESC)

# ❌ SLOW (full scan)
select * from train_availability_cache where travel_date > ?

# ✅ FAST (partition on date)
SELECT * FROM train_availability_cache_2026_07_29 WHERE ...
```

---

## PART 10: SUMMARY TABLE

| Category | Count | Health | Notes |
|----------|-------|--------|-------|
| Total Models | 161 | ⚠️ | Too many in core.py |
| User Models | 8 | ✅ | Well-structured |
| Booking Models | 7 | ✅ | Includes idempotency |
| Payment Models | 7 | ✅ | Complete flow |
| Transit Models | 11 | ✅ | Clean separation |
| ML Models | 12 | ⚠️ | Should be consolidated |
| Safety Models | 5 | ✅ | Comprehensive |
| Telegram Models | 6 | ✅ | Feature-complete |
| Indices | ~50 | ⚠️ | Needs audit |
| Relationships | ~80 | ⚠️ | Some missing FKs |

---

**END OF RESEARCH**

Next Phase: Deep-dive into specific domains (e.g., booking algorithms, payment reconciliation, ML feature store).
