# Core Pipeline Testing Plan

**Date:** February 23, 2026  
**Phase:** A - Core Pipeline Validation  
**Goal:** Validate end-to-end flow before building refund/dashboard

---

## 🎯 Test Flow

```
1. Search Routes
   ↓
2. Unlock Payment (₹39)
   ↓
3. RapidAPI Verification
   ↓
4. Create Booking Request
   ↓
5. Queue Creation
   ↓
6. Status Retrieval
```

---

## ✅ Test Checklist

### Phase A.1: Database Migration Test
- [ ] Verify migration file syntax
- [ ] Test migration upgrade
- [ ] Test migration downgrade
- [ ] Verify all tables created
- [ ] Verify indexes created
- [ ] Verify foreign keys work

### Phase A.2: Model Import Test
- [ ] Import all new models
- [ ] Verify relationships work
- [ ] Test model instantiation

### Phase A.3: API Endpoint Tests
- [ ] Test POST /api/v1/booking/request (create request)
- [ ] Test GET /api/v1/booking/request/{id} (get request)
- [ ] Test GET /api/v1/booking/requests/my (list requests)
- [ ] Verify unlock payment validation
- [ ] Verify queue entry creation
- [ ] Verify passenger linking

### Phase A.4: RapidAPI Integration Test
- [ ] Test RapidAPI client initialization
- [ ] Test with valid API key
- [ ] Test fallback when API unavailable
- [ ] Test error handling

### Phase A.5: End-to-End Flow Test
- [ ] Complete flow: Search → Unlock → Verify → Request → Queue
- [ ] Verify data consistency
- [ ] Verify status transitions

---

## 🚨 Critical Validations

1. **Payment Linkage:** Booking request must link to unlock payment
2. **Queue Creation:** Every request must create queue entry
3. **Status Flow:** PENDING → QUEUED → (WAITING in queue)
4. **Data Integrity:** All foreign keys must work
5. **Error Handling:** Graceful failures at each step

---

## 📝 Test Results

Will be documented as tests are executed.
