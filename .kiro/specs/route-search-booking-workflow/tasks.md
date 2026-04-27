# Implementation Plan: route-search-booking-workflow

## Overview

This implementation plan breaks down the route-search-booking-workflow feature into actionable tasks organized by the four phases defined in the design document. The plan covers database schema updates, API endpoint implementation, service integration, Telegram bot extension, notification integration, and comprehensive testing.

The implementation uses Python with FastAPI, building upon the existing codebase structure in `backend/services/`, `backend/database/models.py`, and `backend/telegram_bot/handlers/`.

## Phase 1: Foundation (Weeks 1-2)

### 1.1 Database Schema Updates

- [x] 1.1.1 Create booking_idempotency table
  - Add idempotency_key (unique), booking_id, request_hash, created_at, expires_at columns
  - Create unique index on idempotency_key
  - _Requirements: REQ-005 (Booking Creation with Idempotency)_

- [x] 1.1.2 Create booking_fraud_checks table
  - Add booking_id, user_id, check_type, risk_score, flags, decision columns
  - Create indexes on booking_id and user_id
  - _Requirements: REQ-008 (Fraud Detection Integration)_

- [x] 1.1.3 Add indexes to existing bookings table
  - Create composite index on (user_id, travel_date)
  - Create index on booking_status
  - _Requirements: REQ-027 (Database Scalability)_

- [x] 1.1.4 Create payment_transactions table
  - Add payment_id, booking_id, amount, method, status, provider_reference, utr_number columns
  - Create indexes on payment_id and booking_id
  - _Requirements: REQ-011 (Payment Reconciliation)_

- [x] 1.1.5 Create notification_logs table
  - Add notification_id, booking_id, channel, status, retry_count, error_message columns
  - Create indexes on booking_id and status
  - _Requirements: REQ-015 (Notification Retry Logic)_

### 1.2 Booking API Service Setup

- [ ] 1.2.1 Set up FastAPI application structure
  - Create backend/api/booking_routes.py with APIRouter
  - Configure CORS and middleware
  - Set up dependency injection for services
  - _Requirements: REQ-028 (REST API Specification)_

- [-] 1.2.2 Implement POST /api/v1/bookings endpoint
  - Create BookingRequest schema with validation
  - Implement booking creation logic with idempotency
  - Return BookingResponse with PNR number
  - _Requirements: REQ-005, REQ-030_

- [ ] 1.2.3 Implement GET /api/v1/bookings/{booking_id} endpoint
  - Add JWT authentication dependency
  - Return booking details with current status
  - Validate user owns the booking
  - _Requirements: REQ-023 (Authentication and Authorization)_

- [ ] 1.2.4 Implement GET /api/v1/bookings/pnr/{pnr_number} endpoint
  - Add PNR lookup without authentication (public endpoint)
  - Return booking summary for the PNR
  - _Requirements: REQ-030_

- [ ] 1.2.5 Implement GET /api/v1/bookings endpoint
  - Add pagination support
  - Filter by user_id from JWT token
  - Support filtering by booking_status
  - _Requirements: REQ-030_

- [ ] 1.2.6 Implement POST /api/v1/bookings/{booking_id}/cancel endpoint
  - Validate booking can be cancelled
  - Update booking status to cancelled
  - Trigger refund processing if applicable
  - _Requirements: REQ-012 (Refund Processing)_

### 1.3 Payment Webhook Handler

- [ ] 1.3.1 Create payment webhook endpoint structure
  - Create backend/api/payment_webhook.py
  - Set up POST /api/v1/webhooks/payment/{provider} endpoint
  - _Requirements: REQ-010 (Payment Webhook Handling)_

- [ ] 1.3.2 Implement webhook signature verification
  - Add signature verification for each payment provider
  - Create provider-specific verification logic
  - Return 401 for invalid signatures
  - _Requirements: REQ-034 (Payment Security)_

- [ ] 1.3.3 Implement webhook idempotency handling
  - Check payment_id and status before processing
  - Return success for duplicate webhook calls
  - Log duplicate attempts
  - _Requirements: REQ-010_

- [ ] 1.3.4 Implement payment status update logic
  - Update payment record status
  - Trigger booking confirmation on success
  - Trigger booking cancellation on failure
  - _Requirements: REQ-010_

- [ ] 1.3.5 Add UPI transaction ID and UTR handling
  - Extract UTR from webhook payload
  - Store in payment_transactions table
  - Update booking.upi_tx_id and booking.utr_number
  - _Requirements: REQ-011_

### 1.4 Checkpoint - Foundation Review

- [ ] 1.4.1 Run unit tests for booking API
  - Ensure 80% code coverage on booking_routes.py
  - Test all validation scenarios
  - _Requirements: REQ-028_

- [ ] 1.4.2 Verify database migrations
  - Run migrations on test database
  - Verify all indexes are created
  - Test idempotency key uniqueness

- [ ] 1.4.3 Ensure all tests pass, ask the user if questions arise.

## Phase 2: Core Workflow (Weeks 3-4)

### 2.1 Seat Allocation Integration

- [ ] 2.1.1 Create seat allocation service client
  - Create backend/services/seat_allocation_service.py
  - Implement methods for checking availability
  - Implement seat locking with timeout
  - _Requirements: REQ-006 (Seat Allocation and Locking)_

- [ ] 2.1.2 Integrate with InventoryService
  - Call inventory service for real-time availability
  - Handle inventory service unavailability gracefully
  - Return availability status in search results
  - _Requirements: REQ-003 (Real-Time Availability Integration)_

- [ ] 2.1.3 Implement seat preference matching
  - Match berth preferences (lower, middle, upper, side)
  - Apply family grouping logic
  - Handle gender-based allocation rules
  - _Requirements: REQ-006_

- [ ] 2.1.4 Implement seat lock mechanism
  - Lock seats for 30 minutes during payment
  - Implement lock timeout handler
  - Release locks on payment completion or timeout
  - _Requirements: REQ-006_

- [ ] 2.1.5 Implement waitlist management
  - Add to waitlist queue when seats unavailable
  - Track waitlist position
  - Promote from waitlist when seats become available
  - _Requirements: REQ-006_

### 2.2 Booking State Machine

- [ ] 2.2.1 Define explicit state machine states
  - Create backend/core/booking_state_machine.py
  - Define states: SEARCH_INITIATED, ROUTE_DISPLAYED, SEAT_ALLOCATING, PRICING, PAYMENT_PENDING, PAYMENT_PROCESSING, CONFIRMING, CONFIRMED, CANCELLED
  - _Requirements: REQ-007 (Booking State Management)_

- [ ] 2.2.2 Implement state transition validation
  - Validate transitions before applying
  - Reject invalid transitions
  - Log all state transitions for audit
  - _Requirements: REQ-007_

- [ ] 2.2.3 Implement timeout handling for pending states
  - Add timeout handler for PAYMENT_PENDING state
  - Auto-cancel booking after 30 minutes
  - Release seat locks on timeout
  - _Requirements: REQ-006_

- [ ] 2.2.4 Add state to booking responses
  - Include current_state in GET /bookings/{id} response
  - Include valid_next_actions in response
  - Include state_transition_history in response
  - _Requirements: REQ-007_

- [ ] 2.2.5 Implement audit logging for state transitions
  - Create audit log entries for each transition
  - Store old_state, new_state, timestamp, user_id
  - Make audit logs queryable
  - _Requirements: REQ-007_

### 2.3 Pricing Engine Integration

- [ ] 2.3.1 Create pricing calculation service
  - Create backend/services/pricing_engine.py
  - Calculate base fare from fare rules
  - Apply quota-based pricing
  - Calculate total with taxes and fees
  - _Requirements: REQ-009 (Payment Processing)_

- [ ] 2.3.2 Implement fare calculation for different class types
  - Support SL, AC3, AC2, AC1, CC, EC class types
  - Apply class-specific pricing rules
  - Handle Tatkal pricing
  - _Requirements: REQ-009_

- [ ] 2.3.3 Apply concession discounts
  - Support senior citizen, student, military concessions
  - Validate concession eligibility
  - Calculate discounted fare
  - _Requirements: REQ-009_

- [ ] 2.3.4 Generate price breakdown for display
  - Create detailed price breakdown response
  - Include base fare, GST, convenience fees
  - Show concession discounts separately
  - _Requirements: REQ-009_

### 2.4 Fraud Detection Integration

- [ ] 2.4.1 Create fraud detection service client
  - Create backend/services/fraud_detection_service.py
  - Implement risk assessment API calls
  - Handle service timeouts gracefully
  - _Requirements: REQ-008, REQ-025 (Fraud Prevention)_

- [ ] 2.4.2 Implement velocity checks
  - Check bookings per user (5 per 24h, 20 per 7d)
  - Check amount limits (max 100,000 per booking)
  - Return risk score and flags
  - _Requirements: REQ-025_

- [ ] 2.4.3 Implement amount-based risk scoring
  - Calculate risk score based on booking amount
  - Flag high-value transactions
  - Require additional verification for high risk
  - _Requirements: REQ-025_

- [ ] 2.4.4 Store fraud check results
  - Save to booking_fraud_checks table
  - Include in booking audit trail
  - Support fraud check history queries
  - _Requirements: REQ-008_

### 2.5 Checkpoint - Core Workflow Review

- [ ] 2.5.1 Run integration tests for booking flow
  - Test complete booking creation flow
  - Test state machine transitions
  - Test seat allocation and locking
  - _Requirements: REQ-006, REQ-007_

- [ ] 2.5.2 Test fraud detection integration
  - Test velocity check limits
  - Test high-value transaction flags
  - Test fraud rejection scenarios
  - _Requirements: REQ-008, REQ-025_

- [ ] 2.5.3 Ensure all tests pass, ask the user if questions arise.

## Phase 3: Integration (Weeks 5-6)

### 3.1 Telegram Bot Booking Flow Extension

- [ ] 3.1.1 Create booking handler module
  - Create backend/telegram_bot/handlers/booking_handler.py
  - Implement conversation state management
  - Handle multi-step booking flow
  - _Requirements: REQ-032 (Telegram Bot Booking Flow)_

- [ ] 3.1.2 Implement passenger detail collection
  - Collect passenger names, ages, genders
  - Handle berth and meal preferences
  - Validate input format
  - _Requirements: REQ-032_

- [ ] 3.1.3 Implement price summary display
  - Show fare breakdown in Telegram message
  - Display class and quota information
  - Show passenger count summary
  - _Requirements: REQ-032_

- [ ] 3.1.4 Implement payment link handling
  - Generate payment URL from booking
  - Send payment link via Telegram
  - Handle payment completion callback
  - _Requirements: REQ-032_

- [ ] 3.1.5 Implement booking confirmation message
  - Format confirmation with PNR and train details
  - Include passenger list
  - Add action buttons (view ticket, my bookings)
  - _Requirements: REQ-032_

- [ ] 3.1.6 Implement /mybookings command
  - List user's recent bookings
  - Show booking status and PNR
  - Allow quick access to booking details
  - _Requirements: REQ-032_

### 3.2 Notification Service Integration

- [ ] 3.2.1 Create notification service client
  - Create backend/services/notification_service.py
  - Implement multi-channel delivery (SMS, email, push)
  - Handle provider failover
  - _Requirements: REQ-013 (Multi-Channel Notification)_

- [ ] 3.2.2 Implement booking confirmation templates
  - Create SMS template with PNR and train details
  - Create email template with full booking info
  - Support HTML email formatting
  - _Requirements: REQ-014 (Notification Templates)_

- [ ] 3.2.3 Implement notification retry logic
  - Add exponential backoff retry (3 attempts)
  - Store retry count in notification_logs
  - Queue failed notifications for manual review
  - _Requirements: REQ-015_

- [ ] 3.2.4 Implement status update notifications
  - Send PNR status change notifications
  - Send delay alerts when detected
  - Send cancellation notifications
  - _Requirements: REQ-016 (Status Update Notifications)_

- [ ] 3.2.5 Implement payment reminder notifications
  - Send reminder before payment expiry
  - Include payment link in reminder
  - Handle reminder timing configuration
  - _Requirements: REQ-016_

### 3.3 Payment Gateway Integration

- [ ] 3.3.1 Implement UPI payment flow
  - Create payment request with UPI intent
  - Generate QR code for UPI payment
  - Handle UPI webhook callbacks
  - _Requirements: REQ-009, REQ-033 (Payment Provider Integration)_

- [ ] 3.3.2 Implement card payment flow
  - Create payment request with card token
  - Support Visa, Mastercard, RuPay
  - Implement 3D Secure handling
  - _Requirements: REQ-033, REQ-034_

- [ ] 3.3.3 Implement net banking flow
  - Create payment request with bank selection
  - Generate bank-specific payment URL
  - Handle net banking webhooks
  - _Requirements: REQ-033_

- [ ] 3.3.4 Implement provider failover
  - Detect provider unavailability
  - Fallback to secondary provider
  - Log failover events
  - _Requirements: REQ-033_

- [ ] 3.3.5 Implement refund processing
  - Create refund request for cancelled bookings
  - Handle partial refunds for partial cancellations
  - Update escrow status on refund completion
  - _Requirements: REQ-012_

### 3.4 Event-Driven Communication

- [ ] 3.4.1 Set up Kafka event producers
  - Create booking.created event producer
  - Create payment.completed event producer
  - Create booking.confirmed event producer
  - _Requirements: REQ-026 (Horizontal Scaling)_

- [ ] 3.4.2 Implement event consumers
  - Create notification.queued event consumer
  - Create inventory.update event consumer
  - Create analytics.booking event consumer
  - _Requirements: REQ-026_

- [ ] 3.4.3 Implement event-driven notification triggering
  - Subscribe to booking.confirmed event
  - Queue notifications for delivery
  - Handle event processing failures
  - _Requirements: REQ-013_

### 3.5 Checkpoint - Integration Review

- [ ] 3.5.1 Test Telegram bot booking flow
  - Test complete conversation flow
  - Test passenger detail collection
  - Test payment link generation
  - _Requirements: REQ-031, REQ-032_

- [ ] 3.5.2 Test notification delivery
  - Test SMS delivery with retry logic
  - Test email delivery with templates
  - Test notification status tracking
  - _Requirements: REQ-013, REQ-015_

- [ ] 3.5.3 Ensure all tests pass, ask the user if questions arise.

## Phase 4: Polish (Weeks 7-8)

### 4.1 Error Handling and Resilience

- [ ] 4.1.1 Implement circuit breakers
  - Add circuit breaker for external service calls
  - Configure failure thresholds and reset times
  - Return degraded response when circuit open
  - _Requirements: REQ-021 (Graceful Degradation)_

- [ ] 4.1.2 Implement retry logic with backoff
  - Add retry decorator for service calls
  - Implement exponential backoff
  - Handle retry exhaustion gracefully
  - _Requirements: REQ-021_

- [ ] 4.1.3 Implement graceful degradation for search
  - Return cached results when search engine unavailable
  - Return results without availability when inventory unavailable
  - Show degradation notice to users
  - _Requirements: REQ-021_

- [ ] 4.1.4 Implement booking queue for payment gateway unavailability
  - Queue bookings when payment gateway down
  - Process queued bookings when gateway recovers
  - Notify users of delay
  - _Requirements: REQ-021_

- [ ] 4.1.5 Add comprehensive error codes
  - Define error codes for all failure scenarios
  - Include resolution hints in error responses
  - Log errors with context for debugging
  - _Requirements: REQ-021_

### 4.2 API Documentation

- [ ] 4.2.1 Create OpenAPI 3.0 specification
  - Document all booking endpoints
  - Include request/response schemas with examples
  - Document error codes and meanings
  - _Requirements: REQ-028_

- [ ] 4.2.2 Document search API endpoints
  - Document POST /api/v1/search
  - Document GET /api/v1/search/{search_id}
  - Document GET /api/v1/stations autocomplete
  - _Requirements: REQ-029 (Search API Endpoints)_

- [ ] 4.2.3 Document booking API endpoints
  - Document all booking CRUD endpoints
  - Include authentication requirements
  - Document rate limits
  - _Requirements: REQ-030_

- [ ] 4.2.4 Document webhook endpoints
  - Document payment webhook format
  - Document signature verification requirements
  - Include example payloads
  - _Requirements: REQ-010_

### 4.3 Unit Testing

- [ ] 4.3.1 Write unit tests for booking service
  - Test booking creation with idempotency
  - Test state machine transitions
  - Test fraud detection integration
  - _Requirements: REQ-028_

- [ ] 4.3.2 Write unit tests for payment service
  - Test payment creation
  - Test webhook handling
  - Test refund processing
  - _Requirements: REQ-010, REQ-012_

- [ ] 4.3.3 Write unit tests for notification service
  - Test template rendering
  - Test retry logic
  - Test multi-channel delivery
  - _Requirements: REQ-014, REQ-015_

- [ ] 4.3.4 Write unit tests for Telegram handler
  - Test conversation flow
  - Test input validation
  - Test message formatting
  - _Requirements: REQ-031, REQ-032_

### 4.4 Integration Testing

- [ ] 4.4.1 Write integration tests for booking flow
  - Test complete booking creation to confirmation
  - Test payment webhook to booking confirmation
  - Test cancellation and refund flow
  - _Requirements: REQ-005, REQ-010, REQ-012_

- [ ] 4.4.2 Write integration tests for search flow
  - Test search with availability hydration
  - Test pagination and filtering
  - Test caching behavior
  - _Requirements: REQ-001, REQ-003, REQ-004_

- [ ] 4.4.3 Write integration tests for notification delivery
  - Test SMS delivery with mock provider
  - Test email delivery with mock provider
  - Test retry behavior
  - _Requirements: REQ-013, REQ-015_

- [ ] 4.4.4 Write integration tests for Telegram bot
  - Test search flow through bot
  - Test booking flow through bot
  - Test /mybookings command
  - _Requirements: REQ-031, REQ-032_

### 4.5 Performance Optimization

- [ ] 4.5.1 Optimize database queries
  - Add missing indexes based on query patterns
  - Optimize slow queries with EXPLAIN ANALYZE
  - Implement query result caching
  - _Requirements: REQ-027_

- [ ] 4.5.2 Implement connection pooling
  - Configure database connection pool
  - Set appropriate pool limits
  - Monitor pool utilization
  - _Requirements: REQ-027_

- [ ] 4.5.3 Optimize search caching
  - Configure cache TTL by quota type
  - Implement cache invalidation on availability change
  - Monitor cache hit rates
  - _Requirements: REQ-004 (Search Result Caching)_

- [ ] 4.5.4 Load test booking throughput
  - Test 50 concurrent booking requests per second
  - Verify booking creation within 3 seconds
  - Identify and fix bottlenecks
  - _Requirements: REQ-018 (Booking Throughput)_

### 4.6 Final Checkpoint

- [ ] 4.6.1 Run full test suite
  - Execute all unit tests
  - Execute all integration tests
  - Verify 80% code coverage
  - _Requirements: REQ-028_

- [ ] 4.6.2 Performance testing
  - Run load tests for search API
  - Run load tests for booking API
  - Verify performance targets
  - _Requirements: REQ-017, REQ-018, REQ-019_

- [ ] 4.6.3 Security review
  - Verify authentication on all endpoints
  - Verify authorization checks
  - Verify PII encryption
  - _Requirements: REQ-023, REQ-024 (Data Protection)_

- [ ] 4.6.4 Documentation review
  - Review API documentation completeness
  - Review inline code comments
  - Review README updates
  - _Requirements: REQ-028_

- [ ] 4.6.5 Ensure all tests pass, ask the user if questions arise.

## Implementation Notes

### Task Dependencies

The implementation follows a dependency chain where each phase builds on the previous:
- Phase 1 (Foundation) must be complete before Phase 2
- Phase 2 must be complete before Phase 3
- Phase 3 must be complete before Phase 4

Within each phase, some tasks can be done in parallel:
- 1.1 (Database) and 1.2 (Booking API) can proceed in parallel
- 2.1 (Seat Allocation) and 2.2 (State Machine) can proceed in parallel
- 3.1 (Telegram) and 3.2 (Notifications) can proceed in parallel

### Codebase Integration Points

The implementation integrates with the existing codebase at these locations:
- `backend/database/models.py` - Existing Booking, PassengerDetails, SeatInventory models
- `backend/telegram_bot/handlers/search_handler.py` - Existing search handler to extend
- `backend/services/` - Existing service modules to follow patterns
- `backend/api/` - API route structure to follow

### Configuration Requirements

The following configuration parameters should be added to config.yaml:
```yaml
booking:
  max_bookings_per_user_24h: 5
  max_bookings_per_user_7d: 20
  max_amount_per_booking: 100000
  lock_timeout_seconds: 30
  payment_expiry_minutes: 30

search:
  max_results_per_page: 50
  cache_ttl_seconds: 300
  rate_limit_requests_per_minute: 10

payment:
  providers:
    upi:
      - provider1
      - provider2
    card:
      - provider1
```

### Testing Strategy

Tests are organized by type and location:
- Unit tests: `backend/tests/unit/`
- Integration tests: `backend/tests/integration/`
- API tests: `backend/tests/api/`
- Telegram tests: `backend/tests/telegram/`

Use pytest with fixtures from `backend/tests/conftest.py`.

### Deployment Considerations

- Database migrations should be run before deploying new code
- Kafka topics should be created before enabling event producers
- Payment provider credentials should be configured in environment variables
- Redis should be available for caching and distributed locking