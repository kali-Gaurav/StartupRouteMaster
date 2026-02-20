# MASTER CONSOLIDATION EXECUTION PLAN
**Status**: CONSOLIDATION IN PROGRESS
**Target Structure**: Clean backend with domains/, platform/, intelligence/, api/, workers/

---

## PHASE 1: ANALYSIS (IN PROGRESS)

Background agent is currently:
1. Reading all duplicate files
2. Analyzing unique features in each
3. Identifying what to merge
4. Creating consolidation plan for all 12 categories

---

## PHASE 2: CONSOLIDATION (PENDING)

After analysis, will execute:

### For Each Category:
1. **READ** all duplicate versions
2. **MERGE** best code together
3. **CREATE** one ultimate consolidated file
4. **PLACE** in correct location (domains/, platform/, intelligence/)
5. **ARCHIVE** old versions to archive/duplicates_consolidated/[category]/

### Categories to Process:
1. ✓ Route Engines → domains/routing/engine.py (ULTIMATE)
2. ✓ Seat Allocation → domains/inventory/seat_allocator.py (ULTIMATE)
3. ✓ Pricing → domains/pricing/engine.py (ULTIMATE)
4. ✓ Caching → platform/cache/manager.py (ULTIMATE)
5. ✓ Booking → domains/booking/service.py (ULTIMATE)
6. ✓ Payment → domains/payment/service.py (ULTIMATE)
7. ✓ Station → domains/station/service.py (ULTIMATE)
8. ✓ User → domains/user/service.py (ULTIMATE)
9. ✓ Verification → domains/verification/unlock_service.py (ULTIMATE)
10. ✓ Events → platform/events/producer.py & consumer.py (ULTIMATE)
11. ✓ Graph → platform/graph/mutation_engine.py (ULTIMATE)
12. ✓ ML/Intelligence → intelligence/models/*.py (ULTIMATE)

---

## PHASE 3: CLEANUP

1. Delete all duplicate/old files
2. Archive versions to archive/duplicates_consolidated/[category]/v1/
3. Update all imports to point to ULTIMATE versions
4. Remove unused/deprecated directories

---

## PHASE 4: VERIFICATION

1. Test all critical imports
2. Run app.py startup test
3. Verify no broken dependencies
4. Final commit

---

## TARGET STRUCTURE

```
backend/
├── app.py                    ← FastAPI app
├── config.py                ← Configuration
├── database.py              ← Database setup
├── schemas.py               ← Data models
├── dependencies.py          ← DI container
│
├── domains/                 ← BUSINESS LOGIC (CONSOLIDATED)
│   ├── routing/             ← Route finding (ULTIMATE VERSION)
│   ├── booking/             ← Booking system (ULTIMATE VERSION)
│   ├── inventory/           ← Seat allocation (ULTIMATE VERSION)
│   ├── pricing/             ← Dynamic pricing (ULTIMATE VERSION)
│   ├── user/                ← User management (ULTIMATE VERSION)
│   ├── station/             ← Station services (ULTIMATE VERSION)
│   ├── payment/             ← Payment processing (ULTIMATE VERSION)
│   └── verification/        ← Verification/unlock (ULTIMATE VERSION)
│
├── platform/                ← SHARED INFRASTRUCTURE (CONSOLIDATED)
│   ├── cache/               ← Caching (ULTIMATE VERSION)
│   ├── graph/               ← Graph mutations (ULTIMATE VERSION)
│   ├── events/              ← Event processing (ULTIMATE VERSION)
│   ├── monitoring/          ← Monitoring (ULTIMATE VERSION)
│   ├── integrations/        ← External integrations
│   └── security/            ← Security utilities
│
├── intelligence/            ← ML + AI (CONSOLIDATED)
│   ├── models/              ← ML models (ULTIMATE VERSIONS)
│   ├── training/            ← Training pipelines
│   ├── prediction/          ← Prediction engines
│   └── registry/            ← Model registry
│
├── api/                     ← REST ROUTES (CONSOLIDATED)
│   ├── search.py            ← Search endpoints
│   ├── booking.py           ← Booking endpoints
│   ├── user.py              ← User endpoints
│   └── admin.py             ← Admin endpoints
│
├── workers/                 ← BACKGROUND JOBS
│   ├── seat_expiry_worker.py
│   ├── delay_update_worker.py
│   └── pricing_worker.py
│
├── core/                    ← SHARED PATTERNS (KEEP)
│   ├── data_structures.py   ← Dataclasses
│   ├── metrics.py           ← Metrics framework
│   ├── ml_integration.py    ← ML integration
│   ├── base_engine.py       ← Base engine
│   └── utils.py             ← Utilities
│
├── tests/                   ← Tests
├── scripts/                 ← Scripts
└── archive/                 ← OLD VERSIONS (KEEP FOR ROLLBACK)
    ├── duplicates_consolidated/
    │   ├── routing/v1/
    │   ├── seat_allocation/v1/
    │   ├── pricing/v1/
    │   ├── caching/v1/
    │   ├── booking/v1/
    │   ├── payment/v1/
    │   ├── station/v1/
    │   ├── user/v1/
    │   ├── verification/v1/
    │   ├── events/v1/
    │   ├── graph/v1/
    │   └── ml/v1/
    └── deprecated/
        ├── route_engines_v1/
        ├── seat_allocators_v1/
        ├── pricing_engines_v1/
        └── [etc]
```

---

## STATUS TRACKER

- [ ] Phase 1: Analysis complete
- [ ] Phase 2: Consolidation complete
- [ ] Phase 3: Cleanup complete
- [ ] Phase 4: Verification complete
- [ ] Final commit ready

---

**WAITING FOR BACKGROUND AGENT TO COMPLETE ANALYSIS**

