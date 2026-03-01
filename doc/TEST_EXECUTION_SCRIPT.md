# Test Execution Script - Complete Testing Plan

**Date:** 2026-02-23  
**Purpose:** Execute comprehensive testing following COMPREHENSIVE_TESTING_PLAN.md

---

## 🎯 Pre-Testing Setup

### 1. Environment Configuration
```bash
# Set environment variables
export RAPIDAPI_KEY="your_rapidapi_key_here"
export RAPIDURL_KEY="your_rapidurl_key_here"  # Unlimited access
export DATABASE_URL="postgresql://..."
export RAZORPAY_KEY_ID="your_razorpay_key"
export RAZORPAY_KEY_SECRET="your_razorpay_secret"
```

### 2. Database Setup
```bash
# Run migrations
cd backend
alembic upgrade head

# Verify tables exist
python -c "from backend.database.models import BookingRequest, Refund, Payment; print('✅ Models imported')"
```

### 3. Test Data Preparation
- **Real Stations:** NDLS (New Delhi), MMCT (Mumbai Central), SBC (Bangalore)
- **Real Train:** 12951 (Rajdhani Express)
- **Real Date:** 2026-03-15 (future date)

---

## 📋 Phase 1: Route Generation & Search Testing

### TC-1.1: Real Station Search
```bash
# Test: Search NDLS → MMCT
curl -X POST http://localhost:8000/api/search/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "source": "NDLS",
    "destination": "MMCT",
    "date": "2026-03-15"
  }'

# Expected:
# - Routes returned successfully
# - Train numbers are valid (5-digit)
# - Station codes match IRCTC format
# - No RapidAPI calls made (check logs)
```

**Validation Checklist:**
- [ ] Routes returned
- [ ] Train numbers valid (5-digit format)
- [ ] Station codes correct (NDLS, MMCT)
- [ ] Schedule times realistic
- [ ] No RapidAPI calls in logs

**API Calls:** 0

---

### TC-1.2: Route with Multiple Segments
```bash
# Test: Search NDLS → SBC (Bangalore)
curl -X POST http://localhost:8000/api/search/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "source": "NDLS",
    "destination": "SBC",
    "date": "2026-03-15"
  }'

# Expected:
# - Routes with transfers shown
# - Transfer stations identified
# - Journey time calculated
```

**Validation Checklist:**
- [ ] Transfer routes shown
- [ ] Transfer stations correct
- [ ] Journey time accurate
- [ ] Database queries efficient

**API Calls:** 0

---

## 📋 Phase 2: Unlock Payment Flow Testing

### TC-2.1: Unlock Payment - Seat Availability Verification
```bash
# Step 1: Get route_id from search
ROUTE_ID="route_id_from_search_response"

# Step 2: Create unlock payment order
curl -X POST http://localhost:8000/api/payments/create_order \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "route_id": "'$ROUTE_ID'",
    "travel_date": "2026-03-15",
    "is_unlock_payment": true,
    "train_number": "12951",
    "from_station_code": "NDLS",
    "to_station_code": "MMCT"
  }'

# Expected Response:
# {
#   "success": true,
#   "order": {...},
#   "payment_id": "...",
#   "verification": {
#     "sl_availability": {...},
#     "ac3_availability": {...},
#     "sl_fare": {...},
#     "ac3_fare": {...}
#   },
#   "api_calls_made": 4
# }
```

**Validation Checklist:**
- [ ] RapidAPI called for seat availability (SL, 3AC)
- [ ] RapidAPI called for fare (SL, 3AC)
- [ ] Verification results in response
- [ ] API calls tracked correctly
- [ ] Payment order created

**API Calls:** 4 (1 SL seat + 1 3AC seat + 1 SL fare + 1 3AC fare)

---

### TC-2.2: Unlock Payment - Cache Hit
```bash
# Step 1: First unlock (makes API calls)
# (Use same command as TC-2.1)

# Step 2: Second unlock within 15 minutes (should use cache)
curl -X POST http://localhost:8000/api/payments/create_order \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "route_id": "'$ROUTE_ID'",
    "travel_date": "2026-03-15",
    "is_unlock_payment": true,
    "train_number": "12951",
    "from_station_code": "NDLS",
    "to_station_code": "MMCT"
  }'

# Expected:
# - Same verification results
# - api_calls_made: 0 (cache hit)
# - Faster response time
```

**Validation Checklist:**
- [ ] Cache hit logged
- [ ] No RapidAPI calls made
- [ ] Same verification results
- [ ] Faster response

**API Calls:** 0 (cache hit)

---

### TC-2.3: Unlock Payment - RapidAPI Failure
```bash
# Test with invalid RapidAPI key or simulate failure
export RAPIDAPI_KEY="invalid_key"

curl -X POST http://localhost:8000/api/payments/create_order \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "route_id": "'$ROUTE_ID'",
    "travel_date": "2026-03-15",
    "is_unlock_payment": true,
    "train_number": "12951",
    "from_station_code": "NDLS",
    "to_station_code": "MMCT"
  }'

# Expected:
# - Warnings in response
# - Database fallback used
# - Unlock still proceeds
```

**Validation Checklist:**
- [ ] Warnings in response
- [ ] Database fallback used
- [ ] Unlock proceeds successfully
- [ ] No errors thrown

**API Calls:** 0 (fallback used)

---

## 📋 Phase 3: Booking Request Flow Testing

### TC-3.1: Create Booking Request
```bash
# After unlock payment verified
curl -X POST http://localhost:8000/api/v1/booking/request \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "source_station": "NDLS",
    "destination_station": "MMCT",
    "journey_date": "2026-03-15",
    "train_number": "12951",
    "train_name": "Rajdhani Express",
    "class_type": "SL",
    "quota": "GN",
    "passengers": [
      {
        "name": "Test User",
        "age": 30,
        "gender": "M"
      }
    ]
  }'

# Expected:
# - Booking request created
# - Queue entry created
# - Status: QUEUED
```

**Validation Checklist:**
- [ ] Booking request created
- [ ] Queue entry created
- [ ] Status: QUEUED
- [ ] No RapidAPI calls (already verified)

**API Calls:** 0

---

## 📋 Phase 4: Payment & Refund Flow Testing

### TC-4.1: Payment Verification
```bash
# After Razorpay payment
curl -X POST http://localhost:8000/api/payments/verify \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "payment_id": "payment_id",
    "razorpay_order_id": "order_xxx",
    "razorpay_payment_id": "pay_xxx",
    "razorpay_signature": "signature_xxx"
  }'

# Expected:
# - Payment verified
# - Unlock activated
```

**Validation Checklist:**
- [ ] Payment verified
- [ ] Signature validated
- [ ] Unlock activated
- [ ] Database updated

**API Calls:** 0

---

### TC-4.2: Refund Processing
```bash
# Create refund
curl -X POST http://localhost:8000/api/v1/booking/request/REQUEST_ID/refund \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "reason": "Test refund"
  }'

# Expected:
# - Refund created
# - Razorpay refund processed
# - Status: COMPLETED
```

**Validation Checklist:**
- [ ] Refund created
- [ ] Razorpay refund processed
- [ ] Status updated
- [ ] Refund ID returned

**API Calls:** 0

---

## 📋 Phase 5: End-to-End Integration Testing

### TC-5.1: Complete User Journey
```bash
# Step 1: Search
SEARCH_RESPONSE=$(curl -X POST http://localhost:8000/api/search/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "source": "NDLS",
    "destination": "MMCT",
    "date": "2026-03-15"
  }')

ROUTE_ID=$(echo $SEARCH_RESPONSE | jq -r '.routes.direct[0].id')

# Step 2: Unlock (with verification)
UNLOCK_RESPONSE=$(curl -X POST http://localhost:8000/api/payments/create_order \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "route_id": "'$ROUTE_ID'",
    "travel_date": "2026-03-15",
    "is_unlock_payment": true,
    "train_number": "12951",
    "from_station_code": "NDLS",
    "to_station_code": "MMCT"
  }')

# Step 3: Verify payment (simulate)
# (Use Razorpay test credentials)

# Step 4: Create booking request
# (Use route_id from unlock)

# Expected:
# - All steps complete successfully
# - Only 4 RapidAPI calls (from unlock)
# - Real data throughout
```

**Validation Checklist:**
- [ ] Complete flow works
- [ ] Only 4 RapidAPI calls total
- [ ] Real stations, dates, trains
- [ ] Verification results accurate

**API Calls:** 4 per complete journey

---

## 📊 API Usage Tracking

### Track API Calls
```python
# Add to backend logging
import logging
logger = logging.getLogger("api_usage")

# In RouteVerificationService
logger.info(f"RapidAPI call made: {endpoint}, Remaining: {budget_remaining}")
```

### Monitor Daily Usage
```bash
# Check logs for API usage
grep "RapidAPI call made" backend/logs/app.log | wc -l

# Expected: < 233 calls/day (7000/month / 30 days)
```

---

## ✅ Success Criteria

### Functionality
- [ ] All features work correctly
- [ ] Real data used throughout
- [ ] Routes generate correctly
- [ ] Seat availability verified
- [ ] Fare verified

### API Usage
- [ ] Within 7000/month budget
- [ ] Caching working effectively
- [ ] Fallback working correctly

### Performance
- [ ] Response times acceptable
- [ ] Database queries optimized
- [ ] Cache hit rate > 50%

### User Experience
- [ ] No broken flows
- [ ] Error handling graceful
- [ ] Real-time data accurate

---

## 🐛 Troubleshooting

### Issue: RapidAPI calls not being made
**Check:**
- RAPIDAPI_KEY environment variable set
- RapidAPIClient initialized correctly
- Route info extracted successfully

### Issue: Cache not working
**Check:**
- Cache TTL set correctly (15 minutes)
- Cache key format correct
- Same route+date+class combination

### Issue: Database fallback not working
**Check:**
- Database connection working
- Route data exists in database
- Fallback logic executed

---

## 📝 Test Results Template

```
Test Case: TC-X.X
Date: YYYY-MM-DD
Result: PASS/FAIL
API Calls Made: X
Cache Hits: X
Errors: None/[List]
Warnings: None/[List]
Notes: [Any observations]
```

---

## 🚀 Next Steps After Testing

1. **Fix Issues Found**
2. **Optimize Based on Results**
3. **Update Documentation**
4. **Deploy to Production**
