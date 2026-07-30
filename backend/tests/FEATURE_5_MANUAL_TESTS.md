# Feature #5: Search & Recommendations - Manual Testing Guide

## Overview
This guide provides step-by-step instructions for manually testing Feature #5 (Route Search and Personalized Recommendations) before marking it as complete.

---

## Part 1: Test Environment Setup

### Prerequisites
- Backend server running on `http://localhost:8000`
- Database populated with sample routes and user data
- Authentication tokens for test users (if required)

### Quick Setup
```bash
# Start backend server
cd backend
python -m uvicorn main:app --reload

# In another terminal, run tests
pytest tests/test_search_service.py -v
pytest tests/test_recommendation_service.py -v
```

---

## Part 2: Search API Testing

### Test 2.1: Basic Search - Find Direct Routes

**Endpoint:** `GET /api/v1/search/routes`

**Query Parameters:**
- source: `NDLS`
- destination: `BCT`
- date: `2026-07-15`
- persona: `COMFORT`
- limit: `10`

**Expected Response:**
- Status: 200 OK
- Response contains `journeys` array
- Each journey has:
  - `journey_id`: Unique identifier
  - `departure_time`, `arrival_time`: Times in HH:MM format
  - `total_duration`: Duration in minutes
  - `total_cost`: Fare in rupees
  - `num_transfers`: Number of transfers (0 for direct)
  - `reliability_badge`: green/yellow indicator
  - `legs`: Array with train details

**Validation Checklist:**
- [ ] Response received in < 5 seconds
- [ ] At least 3 direct routes returned
- [ ] All fares > 100 and < 15000
- [ ] Departure times are in ascending order
- [ ] All routes depart after today's date

**Curl Command:**
```bash
curl -X GET "http://localhost:8000/api/v1/search/routes?source=NDLS&destination=BCT&date=2026-07-15&persona=COMFORT&limit=10"
```

---

### Test 2.2: Search with Transfers

**Query Parameters:**
- source: `NDLS`
- destination: `CSMT`
- date: `2026-07-16`
- limit: `15`

**Expected Response:**
- Should return mix of:
  - Direct routes (num_transfers = 0)
  - One-transfer routes (num_transfers = 1)
  - Two-transfer routes (num_transfers = 2)

**Validation Checklist:**
- [ ] Routes grouped by transfer count
- [ ] One-transfer fares reasonable (slightly higher than direct)
- [ ] Two-transfer fares < direct + 30%
- [ ] Layover times >= 1 hour

---

### Test 2.3: Search by Persona

**Run 3 searches with different personas:**

#### Persona: ECONOMY
- Query: `source=NDLS&destination=BCT&persona=ECONOMY&limit=10`
- Expected: Cheapest routes prioritized, 2S/3E class preferred

#### Persona: COMFORT
- Query: `source=NDLS&destination=BCT&persona=COMFORT&limit=10`
- Expected: Balanced mix, SL/3A class preferred

#### Persona: PREMIUM
- Query: `source=NDLS&destination=BCT&persona=PREMIUM&limit=10`
- Expected: Expensive routes, 2A/1A class preferred

**Validation Checklist:**
- [ ] ECONOMY results have lowest avg fare
- [ ] COMFORT results have mid-range fares
- [ ] PREMIUM results have highest fares
- [ ] Different class distributions per persona

---

### Test 2.4: Pagination (Load More)

**First Request:**
- Query: `source=NDLS&destination=BCT&date=2026-07-15&limit=5&page=1`

**Expected:**
- Returns 5 routes
- Response includes `has_next: true`
- Contains `next_cursor` value

**Second Request (Load More):**
- Query: `source=NDLS&destination=BCT&date=2026-07-15&limit=5&page=2`

**Expected:**
- Returns next 5 routes
- Different routes from first request
- `has_next` indicates if more results exist

**Validation Checklist:**
- [ ] Page 1 and Page 2 have no duplicate journeys
- [ ] Total results ≈ expected amount
- [ ] Cursor-based pagination working

---

### Test 2.5: Error Cases

#### Test 2.5a: Same Source and Destination
- Query: `source=NDLS&destination=NDLS`
- Expected: 400 Bad Request with error message

#### Test 2.5b: Invalid Station Codes
- Query: `source=INVALID&destination=BADCODE`
- Expected: 404 or empty results with diagnostic info

#### Test 2.5c: Past Date
- Query: `date=2020-01-01`
- Expected: Empty results or 400 error

#### Test 2.5d: Very Far Future
- Query: `date=2050-12-31`
- Expected: Empty results (bookings only 120 days ahead)

**Validation Checklist:**
- [ ] All error cases handled gracefully
- [ ] User-friendly error messages returned
- [ ] No 500 server errors

---

## Part 3: Recommendations API Testing

### Test 3.1: Get Recommendations - Authenticated User

**Endpoint:** `GET /api/v1/recommendations`

**Setup:**
- Authenticate with test user ID: `test_user_123`
- User should have search history for testing

**Query Parameters:**
- source: `NDLS`
- destination: `BCT`
- date: `2026-07-20`
- persona: `COMFORT`
- limit: `10`

**Headers:**
```
Authorization: Bearer <test_token>
X-User-ID: test_user_123
```

**Expected Response:**
- Status: 200 OK
- Contains `recommendations` array
- Each recommendation includes:
  - `journey_id`: Route ID
  - `confidence_score`: 0-1 probability
  - `reason`: Why recommended (e.g., "🔥 Trending route")
  - `metadata`: Additional context

**Validation Checklist:**
- [ ] Response received in < 3 seconds
- [ ] Confidence scores between 0 and 1
- [ ] All reasons are meaningful
- [ ] Recommendations differ from straight search

---

### Test 3.2: Trending Routes

**Endpoint:** `GET /api/v1/recommendations/trending`

**Query Parameters:**
- source: `NDLS`
- destination: `BCT`
- limit: `5`

**Expected Response:**
- Routes with high search volume
- Routes with high demand
- Reason includes 🔥 emoji (trending indicator)

**Validation Checklist:**
- [ ] Trending routes exist
- [ ] All have confidence_score > 0.7
- [ ] Reasons indicate popularity/demand
- [ ] Results change over time (if new data added)

---

### Test 3.3: Personalized Recommendations

**Endpoint:** `GET /api/v1/recommendations/personalized`

**Setup:**
- Create test user with specific preferences:
  - Preferred hours: 6-9 AM
  - Preferred class: 2A
  - Price sensitive: No
  
**Query Parameters:**
- source: `NDLS`
- destination: `BCT`
- limit: `10`

**Expected:**
- Recommendations aligned with user profile
- Early morning departures prioritized
- Higher class trains prioritized
- Reasonable fares for persona

**Validation Checklist:**
- [ ] Morning departures in results
- [ ] 2A class trains prioritized
- [ ] Personalization visible in results
- [ ] Better quality than generic search

---

### Test 3.4: Recommendations without Authentication

**Query:** Same as Test 3.3 but without auth headers

**Expected:** 
- Status: 401 Unauthorized
- Error message: "Authentication required"

**Validation Checklist:**
- [ ] Properly rejects unauthenticated requests

---

## Part 4: Algorithm Validation

### Test 4.1: Ranking Algorithm

**Verify 5-factor ranking:**

1. **Timing (30%):** Early morning vs evening departures
2. **Availability (25%):** High vs low probability routes
3. **Price (25%):** Budget-aligned vs expensive routes
4. **Reliability (10%):** On-time vs frequently delayed trains
5. **Comfort (10%):** Direct vs multi-transfer routes

**Test Procedure:**
1. Run search with 20 results
2. Verify top results score highest on multiple factors
3. Compare different personas to ensure weighting changes

**Validation Checklist:**
- [ ] Top results are genuinely better
- [ ] Persona changes affect ranking
- [ ] No random/nonsensical order

---

### Test 4.2: Deduplication

**Procedure:**
1. Get recommendations for same route twice
2. Check cache is working

**Expected:**
- Second request faster than first (cached)
- Same routes returned
- Cache-hit indicator in metadata

**Validation Checklist:**
- [ ] Cache working (2nd request < 500ms)
- [ ] Results identical
- [ ] Metadata shows cache_source

---

### Test 4.3: Cold Start (New User)

**Setup:**
- Create brand new user with no history

**Test:**
- Get recommendations for NDLS → BCT

**Expected:**
- Still returns recommendations
- Based on trending/popular routes
- Confidence scores slightly lower

**Validation Checklist:**
- [ ] No error on new user
- [ ] Fallback to trending works
- [ ] Recommendations reasonable

---

## Part 5: Performance Testing

### Test 5.1: Response Time

**Acceptance Criteria:**
- Search: < 3 seconds for 10 results
- Recommendations: < 2 seconds for 10 results
- Trending: < 1 second for 5 results

**Test Procedure:**
```bash
# Use Apache Bench
ab -n 100 -c 10 "http://localhost:8000/api/v1/search/routes?source=NDLS&destination=BCT&limit=10"
```

**Expected:**
- Mean response time < 3s
- 95th percentile < 5s
- No timeouts

---

### Test 5.2: Concurrent Requests

**Procedure:**
```bash
# Simulate 50 concurrent users
ab -n 500 -c 50 "http://localhost:8000/api/v1/search/routes?source=NDLS&destination=BCT&limit=10"
```

**Validation Checklist:**
- [ ] 99% success rate
- [ ] No 500 errors
- [ ] Response times acceptable

---

### Test 5.3: Memory Usage

**Monitor with:**
```bash
watch -n 1 'ps aux | grep python'
```

**While running:**
- 100 requests to search endpoint
- 50 requests to recommendations

**Validation Checklist:**
- [ ] Memory stable (no memory leak)
- [ ] Process doesn't consume > 500MB additional

---

## Part 6: Data Quality Testing

### Test 6.1: Recommendation Variety

**Procedure:**
1. Get 10 recommendations
2. Check diversity

**Validation:**
- [ ] Mix of different routes
- [ ] Different times/fares
- [ ] Not just top-N generic results

---

### Test 6.2: Data Consistency

**Procedure:**
1. Get route A from search
2. Get route A from recommendations
3. Compare metadata

**Validation:**
- [ ] Same fare in both
- [ ] Same departure time
- [ ] Same train number

---

### Test 6.3: Stale Data Detection

**Procedure:**
1. Search once
2. Wait 10 minutes
3. Search again for same route

**Expected:**
- Fresh data loaded (not cached forever)
- Fares may update

**Validation:**
- [ ] Data refreshed appropriately
- [ ] Not serving day-old data

---

## Part 7: Integration Tests

### Test 7.1: Search → Booking Flow

**Procedure:**
1. Search for route
2. Get route ID
3. Proceed to booking with that route
4. Complete booking

**Validation Checklist:**
- [ ] Route ID from search works in booking
- [ ] Fares consistent
- [ ] No 404 errors

---

### Test 7.2: Recommendations → Booking Flow

**Procedure:**
1. Get recommendation
2. Book recommended route
3. Verify booking created

**Validation:**
- [ ] Recommendation → booking seamless
- [ ] Metadata preserved
- [ ] No errors

---

## Part 8: Edge Cases & Stress Tests

### Test 8.1: Very Popular Route

**Route:** NDLS → BCT (most popular)

**Expected:**
- Hundreds of results
- Pagination working
- No timeouts

---

### Test 8.2: Rare Route

**Route:** XYZ → ABC (obscure stations)

**Expected:**
- 0 results OR
- Fallback suggestions to nearby major stations

---

### Test 8.3: Extreme Date

**Test with:**
- Tomorrow
- 120 days from now
- 121 days from now (should return nothing)

**Validation:**
- [ ] Tomorrow has results
- [ ] 120 days has results
- [ ] 121 days returns empty gracefully

---

## Part 9: User Experience Testing

### Test 9.1: Error Messages

Verify error messages are user-friendly:
- ✓ "No routes available on this date"
- ✓ "Please specify valid station codes"
- ✗ Raw SQL errors
- ✗ Stack traces to user

---

### Test 9.2: Response Format

Verify JSON response is:
- ✓ Properly formatted
- ✓ All fields present
- ✓ No null values where not expected
- ✓ Timezone-aware timestamps

---

### Test 9.3: Mobile Responsiveness

Test with mobile user agents:
```bash
curl -H "User-Agent: Mobile Safari" http://localhost:8000/api/v1/search/routes?...
```

---

## Completion Checklist

- [ ] All search tests passed (Part 2)
- [ ] All recommendation tests passed (Part 3)
- [ ] Algorithm validation complete (Part 4)
- [ ] Performance acceptable (Part 5)
- [ ] Data quality verified (Part 6)
- [ ] Integration tests successful (Part 7)
- [ ] Edge cases handled (Part 8)
- [ ] UX verified (Part 9)
- [ ] No critical bugs found
- [ ] Documentation up to date
- [ ] Code reviewed
- [ ] Ready for production deployment

---

## Sign-Off

**Tested By:** ___________________
**Date:** ___________________
**Status:** ☐ PASS ☐ FAIL

**Notes:**
```
[Add any issues or observations here]
```

---

## Appendix: Common cURL Commands

```bash
# Basic search
curl "http://localhost:8000/api/v1/search/routes?source=NDLS&destination=BCT&date=2026-07-15"

# Search with persona
curl "http://localhost:8000/api/v1/search/routes?source=NDLS&destination=BCT&persona=PREMIUM"

# Get recommendations
curl -H "X-User-ID: test_user" "http://localhost:8000/api/v1/recommendations?source=NDLS&destination=BCT"

# Get trending
curl "http://localhost:8000/api/v1/recommendations/trending?source=NDLS&destination=BCT"

# Pagination
curl "http://localhost:8000/api/v1/search/routes?source=NDLS&destination=BCT&page=2&limit=10"
```

---

## Next Steps

After passing all manual tests:
1. ✅ Run automated test suite
2. ✅ Deploy to staging
3. ✅ Smoke test staging
4. ✅ Get stakeholder approval
5. ✅ Deploy to production
6. ✅ Monitor for errors in prod
7. ✅ Create FEATURE_5_LEARNINGS.md
