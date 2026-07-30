# ⚠️ CLEANUP MANIFEST - Files to Delete

**Date:** June 8, 2026  
**Reason:** Duplicate files created without auditing existing architecture  
**Action:** DELETE these files

---

## Files to DELETE

These files should be **COMPLETELY REMOVED** from the project:

### 1. Database
```
❌ backend/database/migrations/002_create_booking_tables.sql
   Reason: Duplicate of existing booking tables
   Solution: Use existing database/models.py instead

❌ backend/database/models/booking_models.py
   Reason: Duplicate of existing models
   Solution: Use existing database/models.py instead
```

### 2. Services
```
❌ backend/services/booking_service.py
   Reason: Duplicate of services/booking/service.py (1823 lines)
   Solution: Extend existing services/booking/service.py
```

### 3. API Endpoints
```
❌ backend/api/v1/bookings.py
   Reason: Duplicate endpoints
   Solution: Extend existing api/booking_routes.py instead
```

### 4. Webhooks
```
❌ backend/webhooks/razorpay.py
   Reason: Webhook logic should be in payment_service.py
   Solution: Extend services/payment_service.py instead

❌ backend/webhooks/__init__.py
   Reason: Created as side effect
   Solution: Delete if only contains __init__
```

### 5. Documentation (Corrections)
```
❌ FEATURE_01_BUILD_SESSION_SUMMARY.md
   Reason: Based on incorrect duplicate files
   Action: IGNORE this document

❌ NEXT_STEPS_FEATURE_01.md
   Reason: References duplicate files
   Action: IGNORE this document

❌ 00_START_HERE.md
   Reason: References incorrect approach
   Action: IGNORE this document
```

---

## What to KEEP

Use these instead:

```
✅ backend/api/booking_routes.py
   Purpose: Real booking API - EXTEND this

✅ backend/services/booking/service.py (1823 lines)
   Purpose: Real booking service - EXTEND this

✅ backend/services/payment_service.py
   Purpose: Incomplete payment service - COMPLETE this

✅ backend/database/models.py
   Purpose: Existing models - USE these

✅ frontend/src/pages/Bookings.tsx
   Purpose: Booking UI - WIRE to payment endpoints

✅ CRITICAL_ARCHITECTURE_AUDIT.md
   Purpose: What actually exists - READ THIS

✅ FEATURE_01_PARALLEL_BUILD_DELEGATION.md
   Purpose: Correct parallel execution plan - USE THIS

✅ CORRECTION_SUMMARY_AND_NEXT_STEPS.md
   Purpose: Corrected approach - READ THIS
```

---

## Deletion Instructions

Run these commands to remove duplicate files:

```bash
# Delete in backend folder
rm -f backend/database/migrations/002_create_booking_tables.sql
rm -f backend/database/models/booking_models.py
rm -f backend/services/booking_service.py
rm -f backend/api/v1/bookings.py
rm -f backend/webhooks/razorpay.py
rm -f backend/webhooks/__init__.py (if only contains comments)

# Delete incorrect documentation
rm -f FEATURE_01_BUILD_SESSION_SUMMARY.md
rm -f NEXT_STEPS_FEATURE_01.md
rm -f 00_START_HERE.md
rm -f FEATURE_01_BOOKING_FLOW_COMPLETE_DESIGN.md
```

---

## Git Cleanup

If these files were committed:

```bash
# Remove from git history
git rm --cached backend/database/migrations/002_create_booking_tables.sql
git rm --cached backend/database/models/booking_models.py
git rm --cached backend/services/booking_service.py
git rm --cached backend/api/v1/bookings.py
git rm --cached backend/webhooks/razorpay.py
git rm --cached backend/webhooks/__init__.py

# Commit the removal
git commit -m "Remove duplicate files created by mistake"
```

---

## Verification Checklist

After deletion:

- [ ] `backend/api/v1/` folder is empty or removed
- [ ] `backend/webhooks/` folder is empty or removed
- [ ] `backend/database/migrations/002_*.sql` doesn't exist
- [ ] `backend/database/models/booking_models.py` doesn't exist
- [ ] `backend/services/booking_service.py` doesn't exist
- [ ] No conflicts with existing code
- [ ] All imports still work
- [ ] Tests still pass

---

## What Now?

After cleanup, follow this plan:

1. **Read:** `CRITICAL_ARCHITECTURE_AUDIT.md`
2. **Read:** `FEATURE_01_PARALLEL_BUILD_DELEGATION.md`
3. **Activate:** Agent teams for parallel execution
4. **Extend:** Existing code (don't create new files)
5. **Target:** Feature #1 complete in 6-8 hours

---

## Key Lesson

**ALWAYS audit existing code before creating new files.**

The booking infrastructure was 80% complete. You didn't need new files—just integration of Razorpay into existing systems.

---

**Status:** 🟢 CLEANUP MANIFEST READY  
**Next:** Execute cleanup + start parallel build with agent teams
