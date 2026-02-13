# TODO — Freemium *Unlock Route Details* (step-by-step upgrade checklist)

Goal: close all gaps so the “Unlock Details (₹39)” freemium flow is fully functional, tested, safe to deploy and observable.

---

## ✅ Priority 0 — Blockers (must fix before deployment)
1. Standardize API paths & response shape
   - Task: update frontend calls → `/api/payments/...` (plural) OR add backend aliases.
   - Files to change:
     - Frontend: `src/lib/paymentApi.ts`, `src/api/payment.ts`, `src/components/booking/BookingPaymentStep.tsx`
     - Backend: `backend/api/payments.py` (add `order` object if frontend expects it)
   - Acceptance:
     - `POST /api/payments/create_order` returns `order: { order_id, amount, currency, key_id }` and `payment_id`
     - Frontend `createPaymentOrder` and `openRazorpayCheckout` read the `order` object successfully.
   - Estimate: 1–2 hrs

2. Wire UI → real payment flow (remove simulation)
   - Task: replace simulated `handleUnlockRoute` in `src/pages/Index.tsx` with `openUnlockPayment(...)` and ensure `setUnlockSuccess` triggers UI update.
   - Files to change:
     - `src/pages/Index.tsx` (call `useBookingFlowContext().openUnlockPayment`)
     - `src/context/BookingFlowContext.tsx` (emit `route-unlocked` CustomEvent or expose shared unlocked list)
     - `src/pages/Index.tsx` (listen for event and call `setUnlockedRouteIds`)
   - Acceptance:
     - Clicking `Unlock Details` opens the payment modal; on success the route card shows unlocked details.
   - Estimate: 1–2 hrs

3. Fix backend routing & request parsing bugs
   - Task: remove duplicate `@router.get('/is_route_unlocked')`; change `verify` endpoint to accept a Pydantic body model (`VerifyPaymentRequest`).
   - Files to change: `backend/api/payments.py`, `backend/schemas.py` (add/confirm `VerifyPaymentRequest` schema)
   - Acceptance: frontend `verifyPayment()` JSON body is parsed and returns 200/validated response.
   - Estimate: 1 hr

4. Add database migration(s)
   - Task: add migration that ensures DB schema matches models:
     - Create `unlocked_routes` (if not present)
     - Add `unlocked_route_id` to `payments` (nullable)
     - Add `payment_id` to `bookings` (nullable)
     - Add UNIQUE(user_id, route_id) index on `unlocked_routes`
   - Files to add: Alembic (or Supabase migration) SQL under `supabase/migrations/` or migrations folder
   - Acceptance: migrations run cleanly on staging and production.
   - Estimate: 1–2 hrs

---

## ⚙️ Priority 1 — API correctness, webhook & persistence
1. Implement payment webhook endpoint
   - Task: add `POST /api/payments/webhook` that verifies Razorpay signature and reconciles `Payment`, `Booking`, `UnlockedRoute`.
   - Files: `backend/api/payments.py`, `backend/services/payment_service.py`
   - Acceptance: webhook verifies signature, updates records, idempotent.
   - Estimate: 2–3 hrs

2. Ensure `create_payment_order` returns `order` object & `payment_id`
   - Task: backend must return the same object shape frontend expects.
   - Files: `backend/api/payments.py`
   - Acceptance: frontend consumes `order` and `payment_id` with no mapping code.
   - Estimate: 30–60 min

3. Add DB uniqueness & soft-race handling
   - Task: unique constraint on (`user_id`, `route_id`) + `record_unlocked_route` handles concurrent writes gracefully.
   - Files: DB migration + `backend/services/unlock_service.py` (wrap commit in try/except IntegrityError)
   - Estimate: 1 hr

---

## 🧪 Priority 2 — Tests, CI and contract checks
1. Backend tests (unit + integration)
   - Add tests for:
     - `UnlockService.record_unlocked_route` and `is_route_unlocked`
     - `POST /api/payments/create_order` with `is_unlock_payment=True`
     - `GET /api/payments/is_route_unlocked`
     - `POST /api/payments/verify` for unlock payments
   - Files: `backend/tests/test_unlock.py`, extend `backend/tests/test_payment.py`
   - Acceptance: coverage for unlock/payment endpoints and service ≥ 90% logic paths.
   - Estimate: 3–4 hrs

2. Frontend tests
   - Unit tests for `BookingFlowContext.setUnlockSuccess` and `BookingPaymentStep` behavior.
   - E2E test that simulates: open unlock modal → create order (mock) → verify (mock) → `RouteCard` shows unlocked details.
   - Files: `src/__tests__/bookingUnlock.test.tsx`, Cypress/Playwright e2e
   - Acceptance: CI runs e2e and unit tests on PRs.
   - Estimate: 4–6 hrs

3. API contract tests
   - Add small contract tests verifying frontend ↔ backend payload shapes for `create_order`, `verify`, and `is_route_unlocked`.
   - Estimate: 1–2 hrs

---

## ♻️ Priority 3 — Observability, docs, and hardening
1. Monitoring & metrics
   - Track: unlock purchases, failed payments, webhook failures, `is_route_unlocked` hit rate.
   - Add logs at payment creation/verify and webhook.
   - Acceptance: dashboards or logs available in staging.
   - Estimate: 2–4 hrs

2. Docs & README updates
   - Update `README.md`, `QUICKSTART.md` with:
     - env vars: `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `PAYMENT_WEBHOOK_SECRET` (if used)
     - migration commands
     - API contract for payments/unlock
   - Estimate: 1–2 hrs

3. Refund & dispute policy (product)
   - Write short policy and basic refund endpoints/notes.
   - Estimate: 2–4 hrs (product + engineering)

---

## 🔁 Rollout & release checklist (pre-production → GA)
1. Run DB migrations on staging; smoke-test all payment/unlock endpoints.
2. Deploy backend to staging (with Razorpay test keys) and update webhook URL in Razorpay test dashboard.
3. Run full e2e unlock purchase test (staging).
4. Monitor logs/metrics for 24–48 hours with feature-flag ON for a small percentage of users.
5. Gradually roll out to 100% and remove feature-flag.

---

## 🔬 Small implementation details / quick fixes (one-line PRs)
- Frontend: change `/payment/*` → `/payments/*` in `src/lib/paymentApi.ts` and `src/api/payment.ts`.
- Backend: return `order` object from `create_payment_order` response and remove duplicate `is_route_unlocked` route.
- Index page: replace simulated unlock with `openUnlockPayment` and add listener for `route-unlocked`.

---

## PR checklist (what each PR should include)
- [ ] Code changes + unit tests
- [ ] Migration SQL and verification steps
- [ ] API contract update (schemas + docs)
- [ ] End-to-end test for unlock purchase
- [ ] Logging / metric added where payments are created/verified
- [ ] Feature-flag for freemium unlock (optional) and rollout plan

---

## Recommended immediate next step (I can do this now)
1. Fix API-path + response-shape mismatches and wire `Index.tsx` `openUnlockPayment` → implement & verify end-to-end locally.

---

If you want, I can open PRs and implement the Priority 0 changes now — tell me which task I should start with (recommended: API-path + wiring).