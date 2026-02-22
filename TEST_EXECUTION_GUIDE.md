# Test Execution Guide - Core Pipeline Validation

**Date:** February 23, 2026  
**Purpose:** Validate core pipeline before building refund/dashboard features

---

## 🎯 Testing Strategy

Test in this order:
1. ✅ Model validation (offline, no DB needed)
2. ✅ Schema validation (offline)
3. ✅ Migration validation (dry-run)
4. ⏳ Database migration (apply to test DB)
5. ⏳ API endpoint tests (with test DB)
6. ⏳ End-to-end flow test

---

## 📋 Test Scripts Created

### 1. `backend/tests/test_booking_queue_models.py`
**Purpose:** Validate models can be imported and relationships work

**What it tests:**
- ✅ Model imports
- ✅ Relationship definitions
- ✅ Required attributes

**Run:** `cd backend/tests && python test_booking_queue_models.py`

---

### 2. `backend/tests/test_booking_request_api.py`
**Purpose:** Validate schemas and API structure

**What it tests:**
- ✅ Schema validation
- ✅ Endpoint imports
- ✅ RapidAPI integration structure

**Run:** `cd backend/tests && python test_booking_request_api.py`

---

## 🔍 Migration Validation

### Check Migration Syntax
```bash
cd backend
python -m alembic -c alembic.ini check
```

### Dry-Run Migration (Review SQL)
```bash
cd backend
python -m alembic -c alembic.ini upgrade head --sql > migration_preview.sql
```

### Apply Migration (Test Database)
```bash
cd backend
python -m alembic -c alembic.ini upgrade head
```

### Verify Tables Created
```sql
-- Connect to database and run:
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

---

## 🧪 End-to-End Flow Test

### Prerequisites
1. ✅ Database migration applied
2. ✅ Test user created
3. ✅ Test route unlocked (₹39 payment)

### Test Flow

#### Step 1: Create Booking Request
```bash
POST /api/v1/booking/request
Headers: Authorization: Bearer <token>
Body: {
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
        "gender": "M"
    }]
}
```

**Expected:**
- ✅ Status 200
- ✅ Returns booking_request_id
- ✅ Queue entry created automatically
- ✅ Status = "QUEUED"
- ✅ Queue status = "WAITING"

#### Step 2: Get Booking Request
```bash
GET /api/v1/booking/request/{request_id}
Headers: Authorization: Bearer <token>
```

**Expected:**
- ✅ Status 200
- ✅ Returns request details
- ✅ Includes queue_status

#### Step 3: List User Requests
```bash
GET /api/v1/booking/requests/my?skip=0&limit=20
Headers: Authorization: Bearer <token>
```

**Expected:**
- ✅ Status 200
- ✅ Returns list of requests
- ✅ Includes queue status for each

---

## ✅ Validation Checklist

### Phase A.1: Model Tests
- [ ] Run `test_booking_queue_models.py` - All pass
- [ ] Run `test_booking_request_api.py` - All pass

### Phase A.2: Migration Tests
- [ ] Migration syntax valid
- [ ] Migration applies successfully
- [ ] All 6 tables created
- [ ] All indexes created
- [ ] Foreign keys work
- [ ] Migration can be rolled back

### Phase A.3: API Tests
- [ ] Create booking request works
- [ ] Unlock payment validation works
- [ ] Queue entry created automatically
- [ ] Get request works
- [ ] List requests works
- [ ] Error handling works

### Phase A.4: RapidAPI Tests
- [ ] RapidAPI client initializes (if key set)
- [ ] Fallback to database works (if key not set)
- [ ] Error handling graceful

### Phase A.5: End-to-End Flow
- [ ] Complete flow works: Search → Unlock → Request → Queue
- [ ] Data consistency maintained
- [ ] Status transitions correct

---

## 🚨 Critical Validations

1. **Payment Linkage:** Request must link to unlock payment
2. **Queue Creation:** Every request creates queue entry
3. **Status Flow:** PENDING → QUEUED → WAITING
4. **Data Integrity:** Foreign keys work
5. **Error Handling:** Graceful failures

---

## 📝 Test Results Log

Document results here as tests are executed:

### Model Tests
- [ ] Date: _____ | Result: _____ | Notes: _____

### Migration Tests
- [ ] Date: _____ | Result: _____ | Notes: _____

### API Tests
- [ ] Date: _____ | Result: _____ | Notes: _____

### End-to-End Flow
- [ ] Date: _____ | Result: _____ | Notes: _____

---

## 🔧 Troubleshooting

### Migration Fails
- Check database connection
- Verify previous migrations applied
- Check for table conflicts

### Models Don't Import
- Check Python path
- Verify imports in models.py
- Check for circular dependencies

### API Tests Fail
- Verify database migration applied
- Check authentication tokens
- Verify test data exists

---

**Next:** Execute tests and document results before proceeding to refund/dashboard.
