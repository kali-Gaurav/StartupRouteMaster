# Comprehensive Testing Plan - Frontend & Backend Integration

**Date:** 2026-02-23  
**API Budget:** 7000 RapidAPI IRCTC requests/month (~233/day, ~10/hour)  
**Goal:** Test all features with minimal API usage, validate real data flows

---

## 🎯 Testing Strategy: Intelligent API Usage

### API Usage Hierarchy (Priority Order)

1. **Database First** (No API cost)
   - Route generation
   - Schedule data
   - Historical fare data
   - Station information

2. **RapidURL** (Unlimited - Use Freely)
   - Live train running status
   - Real-time delays
   - Platform information
   - Current train position

3. **RapidAPI IRCTC** (Limited - Use Strategically)
   - **ONLY for:** Seat availability verification (SL, 3AC)
   - **ONLY for:** Total fare verification
   - **When:** During unlock payment flow (critical verification point)
   - **Caching:** 15-minute cache to reduce duplicate calls

---

## 📋 Test Plan Structure

### Phase 1: Route Generation & Search (No RapidAPI)
**Goal:** Verify routes generate correctly between real stations with real dates

### Phase 2: Unlock Payment Flow (Minimal RapidAPI)
**Goal:** Verify seat availability and fare verification during unlock

### Phase 3: Booking Request Flow (No RapidAPI)
**Goal:** Verify booking request creation and queue system

### Phase 4: Payment & Refund Flow (No RapidAPI)
**Goal:** Verify payment processing and refund system

### Phase 5: End-to-End Integration (Strategic RapidAPI)
**Goal:** Complete user journey with minimal API calls

---

## 🔍 Phase 1: Route Generation & Search Testing

### Test Cases

#### TC-1.1: Real Station Search
**Input:**
- Source: NDLS (New Delhi)
- Destination: MMCT (Mumbai Central)
- Date: Real future date (e.g., 2026-03-15)

**Expected:**
- Routes generated successfully
- Real train numbers (e.g., 12951, 12953)
- Real schedule times
- Real station codes

**Validation:**
- ✅ Routes returned from database
- ✅ Train numbers are valid (5-digit format)
- ✅ Station codes match IRCTC format
- ✅ Schedule times are realistic
- ✅ No RapidAPI calls made

**API Calls:** 0

---

#### TC-1.2: Route with Multiple Segments
**Input:**
- Source: NDLS
- Destination: SBC (Bangalore)
- Date: Real future date

**Expected:**
- Routes with transfers shown
- Transfer stations identified
- Total journey time calculated

**Validation:**
- ✅ Transfer logic works
- ✅ Journey time accurate
- ✅ Database queries efficient

**API Calls:** 0

---

#### TC-1.3: Invalid Station Codes
**Input:**
- Source: INVALID
- Destination: MMCT

**Expected:**
- Error message returned
- No routes generated

**Validation:**
- ✅ Error handling works
- ✅ No database errors

**API Calls:** 0

---

## 🔍 Phase 2: Unlock Payment Flow Testing

### Test Cases

#### TC-2.1: Unlock Payment - Seat Availability Verification
**Flow:**
1. User searches route (NDLS → MMCT)
2. User selects route
3. User clicks "Unlock" (₹39)
4. **CRITICAL:** System verifies seat availability via RapidAPI
5. Payment order created
6. Payment verified
7. Route unlocked

**Input:**
- Route: NDLS → MMCT
- Train: 12951
- Date: 2026-03-15
- Class: SL (Sleeper)

**Expected:**
- RapidAPI called for seat availability
- Response cached for 15 minutes
- Seat availability displayed
- Fare verified via RapidAPI
- Unlock payment processed

**Validation:**
- ✅ RapidAPI called ONCE per route+date+class combination
- ✅ Response cached (subsequent unlocks use cache)
- ✅ Seat availability accurate (SL, 3AC)
- ✅ Total fare accurate
- ✅ Payment processed successfully

**API Calls:** 2 (1 seat availability + 1 fare) per unique route+date+class

---

#### TC-2.2: Unlock Payment - Cache Hit
**Flow:**
1. User A unlocks route (NDLS → MMCT, 2026-03-15, SL)
2. User B unlocks same route within 15 minutes

**Expected:**
- Cache hit for User B
- No RapidAPI call made
- Same availability data returned

**Validation:**
- ✅ Cache working correctly
- ✅ No duplicate API calls
- ✅ Response time faster

**API Calls:** 0 (cache hit)

---

#### TC-2.3: Unlock Payment - Multiple Classes
**Flow:**
1. User unlocks route for SL
2. User unlocks same route for 3AC

**Expected:**
- Two separate RapidAPI calls (different class)
- Both cached separately
- Both verifications successful

**Validation:**
- ✅ Separate cache entries per class
- ✅ Both classes verified correctly

**API Calls:** 4 (2 seat availability + 2 fare) for 2 classes

---

#### TC-2.4: Unlock Payment - RapidAPI Failure
**Flow:**
1. RapidAPI returns error or timeout
2. System falls back to database

**Expected:**
- Fallback to database data
- Unlock still proceeds
- Warning logged

**Validation:**
- ✅ Graceful degradation
- ✅ System continues working
- ✅ User experience not broken

**API Calls:** 1 (failed, then fallback)

---

## 🔍 Phase 3: Booking Request Flow Testing

### Test Cases

#### TC-3.1: Create Booking Request
**Flow:**
1. User has unlocked route
2. User creates booking request
3. Booking request queued

**Input:**
- Booking request with passenger details
- Payment ID (from unlock)

**Expected:**
- Booking request created
- Queue entry created
- Status: QUEUED

**Validation:**
- ✅ Database records created
- ✅ Queue entry created
- ✅ No RapidAPI calls (already verified during unlock)

**API Calls:** 0

---

#### TC-3.2: Booking Request Status Retrieval
**Flow:**
1. User queries booking request status
2. Status returned

**Expected:**
- Current status returned
- Queue status included
- Passenger details included

**Validation:**
- ✅ Status accurate
- ✅ All data returned

**API Calls:** 0

---

## 🔍 Phase 4: Payment & Refund Flow Testing

### Test Cases

#### TC-4.1: Payment Verification
**Flow:**
1. User completes Razorpay payment
2. Payment verified
3. Unlock activated

**Expected:**
- Payment verified successfully
- Unlock activated
- Booking confirmed (if applicable)

**Validation:**
- ✅ Payment signature verified
- ✅ Database updated
- ✅ Unlock activated

**API Calls:** 0

---

#### TC-4.2: Refund Processing
**Flow:**
1. User requests refund
2. Refund processed via Razorpay
3. Booking request status updated

**Expected:**
- Refund created
- Razorpay refund processed
- Status: REFUNDED

**Validation:**
- ✅ Refund API working
- ✅ Razorpay integration working
- ✅ Status updated correctly

**API Calls:** 0

---

## 🔍 Phase 5: End-to-End Integration Testing

### Test Cases

#### TC-5.1: Complete User Journey
**Flow:**
1. **Search** (No API)
   - User searches NDLS → MMCT
   - Routes displayed

2. **Unlock** (2 RapidAPI calls)
   - User unlocks route
   - Seat availability verified (SL)
   - Fare verified
   - Payment processed

3. **Booking Request** (No API)
   - User creates booking request
   - Request queued

4. **Status Check** (No API)
   - User checks status
   - Status returned

**Expected:**
- All steps complete successfully
- Minimal API usage
- Real data throughout

**Validation:**
- ✅ Complete flow works
- ✅ Only 2 RapidAPI calls (seat + fare)
- ✅ Real stations, dates, trains

**API Calls:** 2 per complete journey

---

#### TC-5.2: Multiple Users, Same Route
**Flow:**
1. User A unlocks route (NDLS → MMCT, 2026-03-15, SL)
2. User B unlocks same route within 15 minutes
3. User C unlocks same route after 15 minutes

**Expected:**
- User A: 2 API calls
- User B: 0 API calls (cache)
- User C: 2 API calls (cache expired)

**Validation:**
- ✅ Caching working correctly
- ✅ API usage minimized

**API Calls:** 4 total (2 + 0 + 2)

---

## 📊 API Usage Optimization Strategy

### Current Implementation Review

1. **Where RapidAPI is Called:**
   - `DataProvider.verify_seat_availability_unified()` - ✅ Correct (only during unlock)
   - `DataProvider.verify_fare_unified()` - ✅ Correct (only during unlock)

2. **Caching Strategy:**
   - 15-minute cache TTL
   - Cache key: `train_no:from_stn:to_stn:date:quota:class_type`
   - ✅ Good for reducing duplicate calls

3. **Fallback Strategy:**
   - Database fallback if RapidAPI fails
   - ✅ Graceful degradation

### Optimization Recommendations

1. **Increase Cache TTL** (if acceptable)
   - Current: 15 minutes
   - Recommended: 30 minutes for seat availability
   - Reason: Seat availability doesn't change rapidly

2. **Batch Verification** (Future Enhancement)
   - Verify multiple routes in single API call
   - Not currently supported by RapidAPI

3. **Smart Caching** (Current)
   - ✅ Already implemented
   - Cache per route+date+class combination

4. **Database Pre-validation** (Current)
   - ✅ Check database first
   - Only call RapidAPI if database shows availability

---

## 🧪 Test Execution Plan

### Step 1: Setup Test Environment
- [ ] Configure RapidAPI key
- [ ] Configure RapidURL key
- [ ] Setup test database with real data
- [ ] Prepare test stations (NDLS, MMCT, SBC, etc.)
- [ ] Prepare test dates (future dates)

### Step 2: Run Phase 1 Tests
- [ ] TC-1.1: Real Station Search
- [ ] TC-1.2: Route with Multiple Segments
- [ ] TC-1.3: Invalid Station Codes

### Step 3: Run Phase 2 Tests
- [ ] TC-2.1: Unlock Payment - Seat Availability Verification
- [ ] TC-2.2: Unlock Payment - Cache Hit
- [ ] TC-2.3: Unlock Payment - Multiple Classes
- [ ] TC-2.4: Unlock Payment - RapidAPI Failure

### Step 4: Run Phase 3 Tests
- [ ] TC-3.1: Create Booking Request
- [ ] TC-3.2: Booking Request Status Retrieval

### Step 5: Run Phase 4 Tests
- [ ] TC-4.1: Payment Verification
- [ ] TC-4.2: Refund Processing

### Step 6: Run Phase 5 Tests
- [ ] TC-5.1: Complete User Journey
- [ ] TC-5.2: Multiple Users, Same Route

### Step 7: API Usage Audit
- [ ] Count total RapidAPI calls made
- [ ] Verify within budget (7000/month)
- [ ] Document cache hit rate
- [ ] Document fallback usage

---

## 📈 Expected API Usage

### Per User Journey (Complete Flow)
- **Search:** 0 calls
- **Unlock (SL):** 2 calls (seat + fare)
- **Unlock (3AC):** 2 calls (seat + fare)
- **Booking Request:** 0 calls
- **Payment:** 0 calls
- **Refund:** 0 calls

**Total per user:** 2-4 calls (depending on classes unlocked)

### With Caching (200 Users)
- **First user:** 2 calls
- **Next 199 users (same route, within cache):** 0 calls
- **After cache expiry:** 2 calls per user

**Estimated:** ~400-800 calls for 200 users (if all unlock different routes)

**Budget:** 7000/month = ~233/day = ~10/hour

**Conclusion:** ✅ Within budget with proper caching

---

## ✅ Success Criteria

1. **Functionality:**
   - ✅ All features work correctly
   - ✅ Real data used throughout
   - ✅ Routes generate correctly
   - ✅ Seat availability verified
   - ✅ Fare verified

2. **API Usage:**
   - ✅ Within 7000/month budget
   - ✅ Caching working effectively
   - ✅ Fallback working correctly

3. **Performance:**
   - ✅ Response times acceptable
   - ✅ Database queries optimized
   - ✅ Cache hit rate > 50%

4. **User Experience:**
   - ✅ No broken flows
   - ✅ Error handling graceful
   - ✅ Real-time data accurate

---

## 🚀 Next Steps

1. **Review & Approve Plan**
2. **Implement Optimizations** (if needed)
3. **Execute Tests**
4. **Document Results**
5. **Fix Issues Found**
6. **Re-test**
7. **Deploy**

---

## 📝 Notes

- RapidAPI calls should ONLY happen during unlock payment flow
- All other operations use database or RapidURL
- Cache aggressively to minimize API usage
- Monitor API usage daily to stay within budget
- Set up alerts if approaching budget limit
