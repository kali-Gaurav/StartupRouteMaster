# Core Pipeline Review & Testing Checklist

**Date:** February 23, 2026  
**Status:** Ready for Testing  
**Phase:** A - Core Pipeline Validation

---

## ✅ What Has Been Built

### 1. Database Models (Step 1) ✅
**Location:** `backend/database/models.py` (lines ~665-900)

**Models Added:**
- ✅ `BookingRequest` - Core booking intent model
- ✅ `BookingRequestPassenger` - Passenger details
- ✅ `BookingQueue` - Execution queue
- ✅ `BookingResult` - PNR storage after execution
- ✅ `Refund` - Refund tracking
- ✅ `ExecutionLog` - Audit trail

**Migration:** `backend/alembic/versions/c3d4e5f6a7b8_add_booking_queue_system_models.py`

**Status:** ✅ Created, ready for review and application

---

### 2. API Endpoints (Step 2.1) ✅
**Location:** `backend/api/bookings.py` (lines ~216-425)

**Endpoints Added:**
- ✅ `POST /api/v1/booking/request` - Create booking request
- ✅ `GET /api/v1/booking/request/{request_id}` - Get request details
- ✅ `GET /api/v1/booking/requests/my` - List user requests

**Schemas:** `backend/schemas.py` - Added 6 new schemas

**Key Features:**
- ✅ Validates unlock payment before creating request
- ✅ Automatically creates queue entry
- ✅ Links passengers to request
- ✅ Returns queue status

---

### 3. RapidAPI Integration (Step 2.2) ✅
**Location:** `backend/core/route_engine/data_provider.py`

**Changes:**
- ✅ Imported RapidAPIClient
- ✅ Initialized client in `__init__`
- ✅ Enhanced `verify_seat_availability_unified()` with RapidAPI calls
- ✅ Enhanced `verify_fare_unified()` with RapidAPI calls
- ✅ Added fallback to database when API unavailable
- ✅ Proper error handling

**Configuration:** Requires `RAPIDAPI_KEY` environment variable

---

## 🧪 Testing Checklist

### Phase A.1: Model Validation (Offline)

**Test Script:** `backend/tests/test_booking_queue_models.py`

**What to Test:**
- [ ] Models can be imported without errors
- [ ] All relationships are properly defined
- [ ] Required attributes exist on models
- [ ] No circular import issues

**How to Run:**
```bash
cd backend/tests
python test_booking_queue_models.py
```

**Expected:** All tests pass ✅

---

### Phase A.2: Schema Validation (Offline)

**Test Script:** `backend/tests/test_booking_request_api.py`

**What to Test:**
- [ ] Schemas can be imported
- [ ] Schema validation works correctly
- [ ] Required fields are enforced
- [ ] Date format validation works

**How to Run:**
```bash
cd backend/tests
python test_booking_request_api.py
```

**Expected:** All tests pass ✅

---

### Phase A.3: Migration Validation

**What to Test:**
- [ ] Migration file syntax is correct
- [ ] Migration can be applied (dry-run first)
- [ ] All 6 tables are created
- [ ] All indexes are created
- [ ] Foreign keys work correctly
- [ ] Migration can be rolled back

**How to Test:**

1. **Review Migration SQL (Dry-Run):**
   ```bash
   cd backend
   python -m alembic -c alembic.ini upgrade head --sql > migration_preview.sql
   ```
   Review `migration_preview.sql` for correctness

2. **Apply Migration:**
   ```bash
   cd backend
   python -m alembic -c alembic.ini upgrade head
   ```

3. **Verify Tables:**
   ```sql
   SELECT table_name 
   FROM information_schema.tables 
   WHERE table_schema = 'public' 
   AND table_name IN (
       'booking_requests',
       'booking_request_passengers',
       'booking_queue',
       'booking_results',
       'refunds',
       'execution_logs'
   );
   ```

**Expected:** All 6 tables exist ✅

---

### Phase A.4: API Endpoint Tests

**Prerequisites:**
- ✅ Migration applied
- ✅ Test user exists
- ✅ Test unlock payment completed (₹39)

**Test 1: Create Booking Request**

```bash
POST /api/v1/booking/request
Headers:
  Authorization: Bearer <test_token>
  Content-Type: application/json

Body:
{
    "source_station": "NDLS",
    "destination_station": "MMCT",
    "journey_date": "2026-03-15",
    "train_number": "12951",
    "train_name": "Rajdhani Express",
    "class_type": "AC3",
    "quota": "GENERAL",
    "passengers": [{
        "name": "Test User",
        "age": 30,
        "gender": "M",
        "berth_preference": "LOWER"
    }]
}
```

**Expected Results:**
- ✅ Status: 200 OK
- ✅ Response includes `id` (booking_request_id)
- ✅ Response includes `status: "QUEUED"`
- ✅ Response includes `queue_status: "WAITING"`
- ✅ Database: `booking_requests` table has new row
- ✅ Database: `booking_queue` table has new row
- ✅ Database: `booking_request_passengers` table has new row

**Validation Checks:**
- [ ] Request links to unlock payment (`payment_id` set)
- [ ] Queue entry created automatically
- [ ] Status transitions: PENDING → QUEUED
- [ ] Queue status is WAITING

---

**Test 2: Get Booking Request**

```bash
GET /api/v1/booking/request/{request_id}
Headers:
  Authorization: Bearer <test_token>
```

**Expected Results:**
- ✅ Status: 200 OK
- ✅ Returns request details
- ✅ Includes `queue_status`
- ✅ Includes all passenger details

**Validation Checks:**
- [ ] Returns correct request
- [ ] Includes queue status
- [ ] User can only see their own requests

---

**Test 3: List User Requests**

```bash
GET /api/v1/booking/requests/my?skip=0&limit=20
Headers:
  Authorization: Bearer <test_token>
```

**Expected Results:**
- ✅ Status: 200 OK
- ✅ Returns list of requests
- ✅ Includes queue status for each
- ✅ Pagination works

**Validation Checks:**
- [ ] Returns only user's requests
- [ ] Pagination works correctly
- [ ] Queue status included for each

---

### Phase A.5: RapidAPI Integration Test

**Test 1: RapidAPI Client Initialization**

**If RAPIDAPI_KEY is set:**
- [ ] Client initializes successfully
- [ ] Logs show "RapidAPI client initialized successfully"

**If RAPIDAPI_KEY is NOT set:**
- [ ] Falls back gracefully
- [ ] Logs show "RAPIDAPI_KEY not configured"
- [ ] Uses database verification

**Test 2: Verification Methods**

Test `verify_seat_availability_unified()`:
- [ ] Calls RapidAPI if client available
- [ ] Falls back to database if API fails
- [ ] Returns proper response structure
- [ ] Includes `source` field ("rapidapi" or "database")

Test `verify_fare_unified()`:
- [ ] Calls RapidAPI if client available
- [ ] Falls back to database if API fails
- [ ] Returns proper response structure

---

### Phase A.6: End-to-End Flow Test

**Complete Flow:**
1. ✅ User searches routes
2. ✅ User unlocks route (pays ₹39)
3. ✅ System verifies via RapidAPI (or database fallback)
4. ✅ User creates booking request
5. ✅ Request added to queue automatically
6. ✅ User can check request status

**Test Steps:**

1. **Search Routes:**
   ```bash
   POST /api/search/
   ```
   ✅ Get route_id

2. **Unlock Route:**
   ```bash
   POST /api/payments/create_order
   Body: { "route_id": "...", "is_unlock_payment": true }
   ```
   ✅ Complete payment flow
   ✅ Verify `UnlockedRoute` created

3. **Create Booking Request:**
   ```bash
   POST /api/v1/booking/request
   ```
   ✅ Request created
   ✅ Queue entry created
   ✅ Status = QUEUED

4. **Check Status:**
   ```bash
   GET /api/v1/booking/request/{request_id}
   ```
   ✅ Returns request with queue status

**Validation:**
- [ ] All steps complete successfully
- [ ] Data consistency maintained
- [ ] Status transitions correct
- [ ] Queue entry exists

---

## 🚨 Critical Validations

### 1. Payment Linkage ✅
- Booking request MUST link to unlock payment
- Request creation fails if no unlock payment exists
- Request creation fails if payment not completed

### 2. Queue Creation ✅
- Every booking request creates queue entry automatically
- Queue entry has status "WAITING"
- Queue entry has execution_mode "MANUAL"

### 3. Status Flow ✅
- Request status: PENDING → QUEUED
- Queue status: WAITING
- Verification status: VERIFIED (after unlock)

### 4. Data Integrity ✅
- Foreign keys work correctly
- Relationships properly defined
- No orphaned records

### 5. Error Handling ✅
- Graceful failures at each step
- Proper error messages
- No crashes on invalid input

---

## 📝 Test Results Log

**Date:** _____________

### Model Tests
- [ ] Result: _____ | Notes: _____

### Schema Tests
- [ ] Result: _____ | Notes: _____

### Migration Tests
- [ ] Result: _____ | Notes: _____

### API Endpoint Tests
- [ ] Create Request: _____ | Notes: _____
- [ ] Get Request: _____ | Notes: _____
- [ ] List Requests: _____ | Notes: _____

### RapidAPI Tests
- [ ] Client Init: _____ | Notes: _____
- [ ] Verification: _____ | Notes: _____

### End-to-End Flow
- [ ] Complete Flow: _____ | Notes: _____

---

## ✅ Next Steps After Testing

**If All Tests Pass:**
1. ✅ Proceed to Step 2.3 - Refund API
2. ✅ Proceed to Step 3.1 - Admin Dashboard

**If Tests Fail:**
1. ❌ Fix identified issues
2. ❌ Re-test affected components
3. ❌ Document fixes

---

## 🔧 Troubleshooting

### Migration Issues
- Check database connection
- Verify previous migrations applied
- Review migration SQL before applying

### API Issues
- Check authentication tokens
- Verify database migration applied
- Check request/response formats

### RapidAPI Issues
- Verify RAPIDAPI_KEY is set (if using)
- Check API rate limits
- Verify fallback works

---

**Status:** Ready for comprehensive testing. Execute tests in order and document results.
