# Database & Backend Optimization Loop
## Spec: Routes Storage & User Information Architecture

**Slug**: `database-backend-loop`  
**Created**: 2026-07-29  
**Status**: SPEC (awaiting approval)

---

## PROBLEM / GOAL

Feature #5 (Route Search & Recommendations) is fully implemented and verified, but the underlying database layer requires optimization for production deployment. Current schema lacks:

1. **Performance indexes** on frequently-queried columns (search_count, demand_score, reliability_score)
2. **Materialized views** for trending/popular routes (causing N+1 queries)
3. **Journey ID uniqueness** constraints for deduplication guarantee
4. **User preference learning** mechanisms to capture booking behavior
5. **Data retention policies** for large tables (DemandSnapshot, SearchOutcome)
6. **Query optimization** specifically for the 4-source candidate generation pipeline

This loop designs and implements a production-ready database layer that supports:
- Sub-2-second recommendation queries (with optimized indexing)
- Efficient user personalization (preference tracking & segmentation)
- Real-time demand data management (cache invalidation strategies)
- Scalable data growth (partitioning & retention policies)

---

## SCOPE

### In Scope
**Database Schema & Indexes**
- Add missing indexes on RouteKnowledge (search_count, demand_score, reliability_score)
- Add missing indexes on DemandSnapshot (source_code, destination_code, travel_date, demand_score)
- Add missing indexes on UserTravelPreference (user_id, preference_confidence)
- Add journey_id uniqueness constraint to SearchOutcome
- Add partial indexes for active routes (where search_count > threshold)

**User Preferences & Learning**
- Enhance UserTravelPreference with booking behavior tracking
- Add new table: UserBookingHistory (tracks every booking per user)
- Add new table: UserPreferenceUpdate (audit trail of preference changes)
- Implement preference update logic (after booking completion)

**Materialized Views & Query Optimization**
- Create materialized view: trending_routes (top routes by search_count + demand_score)
- Create materialized view: user_segmentation (group users by persona/budget)
- Create materialized view: route_quality_scores (pre-computed reliability + comfort scores)
- Optimize 4-source candidate generation queries (profile & document)

**Data Management Strategy**
- Define retention policy for DemandSnapshot (keep 90 days)
- Define retention policy for SearchOutcome (keep 60 days)
- Create archive tables for historical data
- Add soft-delete mechanism (is_archived flag)

**Performance Benchmarks**
- Baseline: Current query times for candidate generation
- Target: <500ms for all 4 sources combined
- Target: <50ms for each individual source query
- Measure: Cache hit rate, index usage, query plans

**Configuration & Monitoring**
- Document all indexes in migration script
- Document materialized view refresh strategy
- Add monitoring queries for index performance
- Document connection pooling recommendations (pool size, timeout)

### Out of Scope (Future Loops)
- Redis distributed caching (in-memory cache already implemented)
- PostgreSQL full-text search integration
- Partitioning by date (not needed until >1M records)
- Machine learning on preference data
- Data warehouse / analytics pipeline
- GDPR data deletion mechanism (beyond scope here)

---

## EXIT CRITERIA (Binary, Checkable)

**Must be met for loop completion:**

1. ✅ **All indexes created and documented**
   - `route_knowledge_search_count_idx` exists
   - `route_knowledge_demand_score_idx` exists
   - `route_knowledge_reliability_idx` exists
   - `demand_snapshot_indexes` (source, dest, date, demand_score) exist
   - `user_travel_preference_idx` exists
   - Verify with: `SELECT * FROM pg_indexes WHERE schemaname='public'` OR SQLite equivalent

2. ✅ **Journey ID uniqueness enforced**
   - SearchOutcome.journey_id has UNIQUE constraint
   - ALTER TABLE succeeds without conflicts
   - Verify with: `\d search_outcome` or schema inspection

3. ✅ **Materialized views created and tested**
   - trending_routes view exists and returns results
   - user_segmentation view exists with correct persona grouping
   - route_quality_scores view exists with pre-computed scores
   - Each view refreshable via SQL or function call
   - Verify with: `SELECT * FROM trending_routes LIMIT 5` returns data

4. ✅ **User booking history tracking implemented**
   - UserBookingHistory table created with: user_id, booking_id, route_id, persona, fare, timestamp
   - Booking completion flow updated to write to UserBookingHistory
   - Verify with: Insert test booking, check table populated

5. ✅ **Query optimization documented**
   - Profile report showing before/after times for 4-source candidate generation
   - Each source <50ms (target)
   - Combined <500ms (target)
   - Actual measured times in evidence/query-performance.md

6. ✅ **Data retention policy implemented**
   - DemandSnapshot cleanup script exists (archive >90 days)
   - SearchOutcome cleanup script exists (archive >60 days)
   - Migration scripts handle existing data
   - Verify with: Script runs without errors, old records archived

7. ✅ **All tests pass**
   - Migration scripts run: `pytest tests/test_migrations.py` → 100% pass
   - New model tests: `pytest tests/test_models.py` → all CRUD ops work
   - Verification that Feature #5 queries still work post-migration
   - Verify with: test output in evidence/test-results.txt

8. ✅ **Documentation complete**
   - README updated with schema changes
   - Migration guide for deployment
   - Monitoring queries documented
   - Connection pooling recommendations in place
   - Verify with: README section "Database Optimization" exists

---

## VERIFICATION PLAN

**Mode**: Static (migrations + tests) + Manual validation

**Step 1: Run migrations** (proof in `evidence/migration-output.txt`)
```bash
pytest tests/test_migrations.py -v --tb=short
alembic upgrade head  # If using Alembic
```

**Step 2: Verify indexes exist** (proof in `evidence/indexes-verification.md`)
```sql
SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='public';
```

**Step 3: Test materialized views** (proof in `evidence/views-test.md`)
```sql
SELECT * FROM trending_routes LIMIT 5;
SELECT * FROM user_segmentation LIMIT 5;
SELECT * FROM route_quality_scores LIMIT 5;
```

**Step 4: Query performance test** (proof in `evidence/query-performance.md`)
- Run each 4-source query 10 times, measure latency
- Compare BEFORE optimization vs AFTER
- Target: <50ms per source, <500ms combined

**Step 5: Feature #5 integration test** (proof in `evidence/feature5-test.md`)
```bash
pytest backend/tests/test_recommendation_service.py -v
curl http://localhost:8000/api/v1/recommendations?source=NDLS&destination=BCT
```

**Step 6: Manual schema inspection** (proof in `evidence/schema-inspection.md`)
- Table row counts
- Index sizes
- Foreign key relationships verified

---

## RISK MITIGATION

| Risk | Mitigation |
|------|-----------|
| Migration breaks existing data | Test migrations on copy of prod DB first; rollback script ready |
| Indexes too large | Monitor index sizes; drop low-usage indexes after 1 week |
| Materialized view refresh slow | Cache refresh async; test with >10M rows |
| Journey ID uniqueness violates existing data | Script to deduplicate SearchOutcome before adding constraint |
| Tests don't catch regressions | Add integration tests that hit database directly |

---

## TIMELINE ESTIMATE

- Phase 1 (Implement): 2-3 hours
- Phase 2 (Review): 30 min
- Phase 3 (Fix): 30 min - 1 hour (if needed)
- Phase 4 (Verify): 30 min (tests + manual checks)
- Phase 5 (PR): 15 min
- Phase 6 (Monitor): 1 hour (watch for deployment issues)

**Total**: ~5 hours wall-clock (6-8 hours active work)

---

## SUCCESS METRICS

After this loop completes, the database should support:

- ✅ Sub-500ms recommendation queries (measured in evidence/)
- ✅ User personalization based on booking history
- ✅ Reliable deduplication (unique journey_ids)
- ✅ Trending/popular route queries <100ms (via materialized views)
- ✅ Zero query timeout in tests
- ✅ Clear data retention policy (no unbounded table growth)

---

## APPROVAL

**Status**: AWAITING USER APPROVAL

**User**: [To confirm before implementation begins]

**Approved**: [ ] Yes  [ ] No  [ ] Modify spec

**Comments**: ___________________________________________________________

---

**Next Step**: Upon approval, move to Phase 1: IMPLEMENT
