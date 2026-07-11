# ITERATION 1: Backend API & Route Engine Stabilization

**Status:** In Progress  
**Duration:** 40 hours estimated (~5 days at 8 hours/day)  
**Branch:** `claude/project-research-architecture-xdeo8l`

---

## OBJECTIVE

Stabilize and harden the backend FastAPI application to ensure:
- Route search API returns results consistently with <500ms latency
- Database connectivity works reliably (fix Supabase IPv6 issues)
- No Python/Pydantic deprecation warnings
- RAPTOR routing engine produces correct results
- All core search endpoints are tested and working

---

## SUB-ITERATIONS

### 1.1: Fix Pydantic V2 Migration Issues (2 hours)

**Current Issues:**
- Using deprecated `@validator` decorator from Pydantic V1
- Some models still have old Config patterns
- May have warnings in logs about deprecated configurations

**Files to Update:**
- `/backend/schemas/base.py` - Uses `@validator`, needs `@field_validator`
- `/backend/database/models.py` - Check for old Config patterns
- Any other schema files with BaseModel subclasses

**Changes:**
```python
# OLD (Pydantic V1)
from pydantic import validator

class MyModel(BaseModel):
    @validator('field_name')
    def validate_field(cls, v):
        return v

# NEW (Pydantic V2)
from pydantic import field_validator

class MyModel(BaseModel):
    @field_validator('field_name')
    @classmethod
    def validate_field(cls, v):
        return v
```

**Verification:**
- [ ] No deprecation warnings in logs
- [ ] All schema validation still works
- [ ] Models serialize/deserialize correctly

**Tasks:**
1. Read all files in `/backend/schemas/`
2. Find all `@validator` decorators
3. Replace with `@field_validator` with `@classmethod`
4. Run: `python -W error::DeprecationWarning -m pytest` to catch any issues
5. Commit changes

---

### 1.2: Stabilize RAPTOR Route Engine (8 hours)

**Current State:**
- Engine exists in `/backend/core/engines/`
- SnapshotManager handles daily graph compilation
- Transfer intelligence scoring implemented
- Delay handling via Copy-on-Write overlays

**Testing Plan:**
1. **Unit Tests:** Verify algorithm correctness
   - Direct routes (0 transfers)
   - Single transfer
   - Multi-transfer (2-3 transfers)
   - Edge cases: Same station, invalid dates, no results

2. **Integration Tests:** End-to-end flow
   - Load graph from database
   - Execute search
   - Return formatted results

3. **Performance Tests:** Meet latency targets
   - Single segment: <100ms
   - 3-segment route: <500ms
   - Cache hit: <10ms

**Key Files:**
- `/backend/core/engines/__init__.py` - Engine init
- `/backend/core/base_engine.py` - Base class
- `/backend/core/data_structures.py` - Graph structures
- `/backend/tests/test_route_engine.py` - Existing tests

**Test Scenarios:**
```
# Test Case 1: Direct Route
From: Delhi (NDLS)
To: Mumbai (BCT)
Date: Tomorrow
Expected: Sorted list of direct trains

# Test Case 2: Multi-City (3+ transfers)
From: Pune
To: Varanasi
Max Transfers: 3
Expected: List of routes with connection times

# Test Case 3: Real-Time Delay Handling
Delay recorded for Train 12345
Query that uses Train 12345
Expected: Adjusted arrival time in results

# Test Case 4: Transfer Intelligence
Connection time: 15 minutes
Historical delay: 20 minutes
Expected: Risk score > 0.7

# Test Case 5: Edge Case - No Results
From: Isolated station
To: Another isolated station
Expected: Empty list, not error
```

**Verification:**
- [ ] All test cases pass
- [ ] Latency benchmarks met
- [ ] No crashes on edge cases
- [ ] Results match manual verification

**Tasks:**
1. Review `/backend/tests/test_route_engine.py`
2. Add missing test cases (multi-transfer, delay handling)
3. Run full test suite
4. Add latency benchmarks to CI
5. Document algorithm in code comments

---

### 1.3: Complete Unified Search API (6 hours)

**Current State:**
- `/api/search/` endpoint exists
- `/api/search/quick` endpoint exists
- `/api/integrated_search/` has partial implementation
- ML ranking integration partially complete

**Missing Components:**
1. ML ranking score in results
2. Caching strategy optimization
3. Error handling for no results
4. Response formatting consistency

**Files to Update:**
- `/backend/api/search.py`
- `/backend/api/integrated_search.py`
- `/backend/services/search_service.py`
- `/backend/core/ml_integration.py`

**Response Format (JSON):**
```json
{
  "source": "Delhi",
  "destination": "Mumbai",
  "date": "2026-07-15",
  "journeys": [
    {
      "id": "route_123",
      "stops": [
        {
          "station": "NDLS",
          "time": "08:00",
          "type": "departure"
        },
        {
          "station": "BCT",
          "time": "16:30",
          "type": "arrival"
        }
      ],
      "trains": [
        {
          "number": "12345",
          "name": "Rajdhani Express",
          "class": "AC1",
          "fare": 2500,
          "available_seats": 45
        }
      ],
      "total_duration": "8h 30m",
      "total_fare": 2500,
      "transfers": 0,
      "ml_score": 0.92,
      "reliability": 0.95,
      "delay_risk": "low"
    }
  ],
  "pagination": {
    "offset": 0,
    "limit": 15,
    "total": 127
  }
}
```

**Verification:**
- [ ] All search endpoints return consistent format
- [ ] ML scores included in results
- [ ] Pagination works correctly
- [ ] Cache headers set properly
- [ ] Error messages are helpful

**Tasks:**
1. Review ML integration in search flow
2. Add ML score field to response
3. Ensure consistent response format across endpoints
4. Add pagination support
5. Test with various search scenarios
6. Commit with descriptive message

---

### 1.4: Fix Supabase Connection Issues (3 hours)

**Current Issue:**
- IPv6 DNS resolution failures on some clients
- Connection pooler URL misconfiguration
- pg_trgm extension may not be installed

**Diagnosis:**
```bash
# Check current DATABASE_URL
echo $DATABASE_URL
# Should be: postgresql://user:pass@pooler.host:5432/postgres

# Test connection
psql $DATABASE_URL -c "SELECT 1"
```

**Fixes:**
1. **IPv6 Issue:**
   - Use Supabase pooler URL (IPv4 only)
   - In Supabase dashboard: Database → Connection → Pooler
   - Copy "URI" (not "Direct Connection")
   - Update `.env` with pooler URL

2. **pg_trgm Extension:**
   - If missing, search queries will fail
   - SQL command: `CREATE EXTENSION IF NOT EXISTS pg_trgm;`
   - May require Supabase support if permission denied

3. **Connection Parameters:**
   - Ensure `pool_pre_ping=True` in SQLAlchemy config
   - Set reasonable pool size: `pool_size=20, max_overflow=40`
   - Add timeout: `pool_recycle=3600`

**Files to Update:**
- `/backend/database/config.py` - Connection string and pool settings
- `/backend/database/session.py` - SQLAlchemy engine init
- `.env.example` - Document correct pooler URL format
- `/backend/alembic/env.py` - Migration connection string

**Verification:**
```python
# Test connection in Python shell
import sqlalchemy
engine = create_engine(DATABASE_URL)
with engine.connect() as conn:
    result = conn.execute("SELECT 1")
    print(result.fetchone())
# Output: (1,)
```

- [ ] Connection succeeds from dev machine
- [ ] No IPv6 errors in logs
- [ ] pg_trgm extension available
- [ ] Migrations run successfully
- [ ] Documented in README

**Tasks:**
1. Review current connection config
2. Update to use pooler URL
3. Add connection health check
4. Update documentation
5. Test connection from multiple locations
6. Commit config updates

---

### 1.5: Add Comprehensive Search Endpoint Tests (6 hours)

**Current State:**
- Test files exist in `/backend/tests/`
- Coverage partial, gaps in integration tests
- No automated latency tracking

**Test Coverage Goals:**
- Route scenarios: 20+ test cases
- Edge cases: 15+ test cases
- Performance benchmarks: latency tracking
- Error handling: API error responses

**Test Categories:**

1. **Route Scenarios (test_search_scenarios.py):**
   ```python
   def test_direct_route():
       # Single train, no transfers
       
   def test_single_transfer():
       # Two trains with connection
       
   def test_multi_transfer():
       # 3+ trains with connections
       
   def test_night_layover():
       # Long connection overnight
       
   def test_women_safety_mode():
       # Women-only coaches, no night stations
   ```

2. **Edge Cases (test_search_edge_cases.py):**
   ```python
   def test_same_station():
       # Source == Destination
       
   def test_invalid_date():
       # Past date, future date
       
   def test_no_results():
       # No trains available
       
   def test_partial_results():
       # Limited options
       
   def test_invalid_station():
       # Typo or non-existent station
   ```

3. **Performance (test_search_performance.py):**
   ```python
   def test_latency_single_segment():
       # Should be < 100ms
       
   def test_latency_multi_segment():
       # Should be < 500ms
       
   def test_cache_effectiveness():
       # Cache hit should be < 10ms
       
   def test_concurrent_searches():
       # 10 concurrent requests should complete
   ```

4. **API Contract (test_search_api.py):**
   ```python
   def test_response_format():
       # Validate JSON schema
       
   def test_pagination():
       # Offset/limit work correctly
       
   def test_error_responses():
       # Proper HTTP status codes
       
   def test_rate_limiting():
       # 60/minute limit respected
   ```

**Verification:**
- [ ] >90% test pass rate
- [ ] Latency metrics captured
- [ ] Edge cases handled gracefully
- [ ] API contract validated
- [ ] CI pipeline runs tests automatically

**Tasks:**
1. Create test files in `/backend/tests/integration/`
2. Implement test cases for each scenario
3. Add pytest fixtures for common setup
4. Add latency benchmarking
5. Integrate with GitHub Actions CI
6. Document test approach in code

---

### 1.6: Optimize Caching Layer (5 hours)

**Current Strategy:**
- Redis for API response caching (5 min TTL)
- Database query results cached (variable TTL)
- Frontend Dexie.js for local IndexedDB caching

**Optimization Plan:**

1. **Cache Warming:**
   ```python
   # Pre-load popular searches
   popular_routes = [
       ("Delhi", "Mumbai"),
       ("Mumbai", "Bangalore"),
       ("Delhi", "Kolkata"),
   ]
   
   async def warm_cache():
       for src, dst in popular_routes:
           await search_routes(src, dst)  # Fills Redis cache
   
   # Run daily via APScheduler
   ```

2. **Cache Key Strategy:**
   - Key: `search:{source}:{destination}:{date}:{budget}`
   - Different TTLs by search type:
     - Popular routes: 24 hours
     - Recent searches: 4 hours
     - Rare routes: 1 hour

3. **Cache Invalidation:**
   ```python
   # When train is delayed/cancelled
   async def on_train_delay(train_id, delay_minutes):
       # Invalidate routes using this train
       routes_affected = db.query(Route).filter(Route.trains.contains(train_id))
       for route in routes_affected:
           cache.delete(f"search:{route.source}:{route.destination}:{route.date}")
   ```

4. **Dexie.js Frontend Caching:**
   ```typescript
   // IndexedDB for recent searches
   const db = new Dexie("RouteMasterDB");
   db.table("searches").add({
       source, destination, date,
       results, timestamp
   });
   
   // Load from IndexedDB if available
   const cached = await db.table("searches").get({source, destination, date});
   if (cached && Date.now() - cached.timestamp < 3600000) {
       return cached.results;  // 1 hour cache
   }
   ```

**Files to Update:**
- `/backend/core/redis.py` - Redis client config
- `/backend/services/search_service.py` - Cache warming logic
- `/backend/api/search.py` - Cache key generation
- `/frontend/src/services/searchService.ts` - Dexie integration

**Metrics:**
- Cache hit rate target: >80%
- Search latency improvement: 10-50x for cache hits
- Memory usage: <2GB for Redis

**Verification:**
- [ ] Cache hit rate > 80%
- [ ] Cache warmed daily automatically
- [ ] Cache invalidation works on delays
- [ ] Frontend caching reduces API calls
- [ ] Latency metrics show improvement

**Tasks:**
1. Implement cache warming schedule
2. Add cache key standardization
3. Implement cache invalidation triggers
4. Add Dexie.js to frontend
5. Monitor cache hit rates
6. Commit caching improvements

---

### 1.7: Performance Profiling and Optimization (4 hours)

**Tools:**
- Python `cProfile` for backend profiling
- Chrome DevTools for frontend profiling
- Locust for load testing

**Profiling Steps:**

1. **Backend Profiling:**
   ```python
   import cProfile
   import pstats
   
   # Profile search endpoint
   profiler = cProfile.Profile()
   profiler.enable()
   
   routes = engine.find_routes(source, destination, date)
   
   profiler.disable()
   stats = pstats.Stats(profiler)
   stats.sort_stats('cumulative')
   stats.print_stats(20)  # Top 20 functions
   ```

2. **Load Testing (Locust):**
   ```python
   from locust import HttpUser, task
   
   class SearchUser(HttpUser):
       @task
       def search(self):
           self.client.post("/api/search", json={
               "source": "Delhi",
               "destination": "Mumbai",
               "date": "2026-07-15"
           })
   
   # Run: locust -f backend/tests/locustfile.py
   ```

3. **Bottleneck Identification:**
   - Database queries taking too long?
   - ML model inference slow?
   - Redis misses high?
   - Algorithm complexity issue?

4. **Optimization Priorities:**
   - Fix slowest function first (80/20 rule)
   - 10% of code usually causes 90% of slowness
   - Common optimizations:
     - Add indexes to database
     - Use batch queries instead of loops
     - Pre-compute/cache results
     - Reduce ML model size
     - Use async/await for I/O

**Target Metrics:**
- P50 latency: <200ms
- P95 latency: <500ms
- P99 latency: <1000ms
- Throughput: >100 req/sec with sustained quality

**Verification:**
- [ ] Profiling reports generated
- [ ] Bottlenecks identified
- [ ] Latency targets met
- [ ] Load test passes without errors
- [ ] Memory usage stable

**Tasks:**
1. Set up profiling tools
2. Run profiling on representative workload
3. Identify top 3 bottlenecks
4. Implement optimizations
5. Re-profile to verify improvements
6. Add load test to CI/CD
7. Document performance baseline

---

## TESTING CHECKLIST

### Before Committing Each Sub-iteration

- [ ] All new tests pass
- [ ] No deprecation warnings
- [ ] Code formatted (black for Python)
- [ ] Type hints added/checked (mypy)
- [ ] Docstrings updated
- [ ] No breaking changes to API
- [ ] Backwards compatible if possible

### Before Marking Iteration Complete

- [ ] All sub-iterations complete
- [ ] 90%+ test pass rate
- [ ] No P0/P1 bugs in new code
- [ ] Performance benchmarks met
- [ ] Documentation updated
- [ ] Code reviewed by second person (if applicable)
- [ ] Ready for production deployment

---

## RISKS & MITIGATION

| Risk | Probability | Impact | Mitigation |
|------|-----------|--------|-----------|
| Pydantic upgrade breaks something | Medium | Medium | Run full test suite, gradual rollout |
| Route engine edge case crashes | Medium | High | Add comprehensive tests, add error handling |
| Performance bottleneck found | High | Medium | Profile early, optimize incrementally |
| Supabase connection still fails | Low | High | Have fallback to SQLite, contact support |
| Breaking API changes needed | Low | High | Deprecate old endpoints, support v1 & v2 |

---

## DELIVERABLES

By end of Iteration 1:

1. ✅ **Code Quality:** No Pydantic deprecation warnings, clean linter output
2. ✅ **Route Engine:** RAPTOR algorithm verified for correctness, latency <500ms
3. ✅ **Search API:** Consistent response format, pagination working, ML scoring included
4. ✅ **Database:** Supabase connection reliable, IPv6 issues resolved
5. ✅ **Tests:** 90%+ pass rate, latency benchmarks tracked
6. ✅ **Caching:** Hit rate >80%, cache warming active
7. ✅ **Performance:** P95 latency <500ms, throughput >100 req/sec
8. ✅ **Documentation:** Updated README, API docs, performance baseline documented

---

## SCHEDULE

```
Day 1: Sub-1.1 (Pydantic) + Sub-1.2 (Route Engine Testing) - 10 hours
Day 2: Sub-1.3 (Search API) + Sub-1.4 (Supabase) - 9 hours
Day 3: Sub-1.5 (Tests) + Sub-1.6 (Caching) - 11 hours
Day 4: Sub-1.7 (Performance) + Review & Fixes - 10 hours

Total: ~40 hours
```

---

**Next Steps:** Start Sub-1.1 (Pydantic V2 migration)

*Document created on: July 11, 2026*  
*Branch: claude/project-research-architecture-xdeo8l*
