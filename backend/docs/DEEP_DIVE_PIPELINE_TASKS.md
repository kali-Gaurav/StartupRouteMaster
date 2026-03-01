# RouteMaster V2 - Deep Dive Pipeline Audit & Implementation Tasks (75 Tasks)

## Phase 1: System Health & Foundations (1-10)
- [x] 1. Verify `curl http://localhost:8000/health` endpoint.
- [x] 2. Verify Redis connectivity via ping.
- [x] 3. Validate DB pool exhaustion via `/health/ready`.
- [ ] 4. Audit Supabase connection latency.
- [ ] 5. Check Upstash Redis latency for caches.
- [x] 6. Verify environment variables loaded completely.
- [ ] 7. Audit Python dependencies & uv lock.
- [x] 8. Ensure single-flight request coalescing is active for searches.
- [ ] 9. Verify logging and tracing headers configuration.
- [x] 10. Confirm caching layers L1/L2 setup.

## Phase 2: Transit Graph Engine (11-20)
- [x] 11. Run `/debug/engine` to check loaded nodes & edges.
- [ ] 12. Verify snapshot age and expiry.
- [ ] 13. Test `reload-graph` admin endpoint.
- [x] 14. Ensure background hub connectivity precomputation is not blocking.
- [x] 15. Check limits on `RAPTOR_MAX_INITIAL_DEPARTURES` and `ONWARD`.
- [ ] 16. Ensure GTFS/Graph model loads correctly in SQLite/Postgres.
- [ ] 17. Verify multi-modal routing engine components initialization.
- [ ] 18. Test graph traversal query time.
- [ ] 19. Inspect `station_utils.py` for station name to code resolution.
- [ ] 20. Audit memory usage of route engine after cache warmup.

## Phase 3: Route Generation & Search (21-30)
- [x] 21. Run unified search API test: NDLS to BCT.
- [ ] 22. Verify correct unified schema response (Fix current `[]` empty list bug).
- [ ] 23. Validate journey segments (train numbers, times).
- [x] 24. Run unified search performance benchmark.
- [x] 25. Verify Request Coalescing works for simultaneous search hits.
- [x] 26. Verify caching mechanism (`unified_v2` key) stores results.
- [ ] 27. Test search ranking: `preferences="fastest"`.
- [ ] 28. Test search ranking: `preferences="cheapest"`.
- [ ] 29. Test search ranking: `preferences="safest"`.
- [x] 30. Audit time & distance estimations on routes.

## Phase 4: Live Status & Seat Verification (31-40)
- [x] 31. Verify Live Status injection in top 10 search results.
- [ ] 32. Test Live Status Rappid.in API fallback mechanism.
- [x] 33. Verify Seat Availability execution on top 3 results asynchronously.
- [x] 34. Validate Seat Verification stops after finding first available coach.
- [x] 35. Test Seat Availability Cache caching results for 10 minutes.
- [ ] 36. Ensure failed RapidIRCTC checks fallback to PENDING or default state gracefully.
- [ ] 37. Test direct Live Status API endpoint: `/api/realtime/train/{id}/status`.
- [ ] 38. Ensure RapidIRCTC seat check consumes quota correctly.
- [x] 39. Validate caching in `SeatVerificationService`.
- [x] 40. Verify journey caching structure handles `availability_status`.

## Phase 5: Payment Session Code System (41-50)
- [x] 41. Design `payment_sessions` database table/model.
- [x] 42. Create endpoint to generate a Payment Session Code.
- [x] 43. Integrate Payment Session Code generation in `/api/payments/create_order_v2`.
- [x] 44. Map Payment Session Code to UPI Intent link.
- [x] 45. Implement manual confirmation endpoint using the code.
- [x] 46. Create `PaymentSession` schema definitions.
- [ ] 47. Handle expired Payment Sessions (e.g., 15 mins TTL).
- [x] 48. Connect Payment Session validation to route unlock.
- [ ] 49. Update frontend or mock a flow for testing the code entry.
- [x] 50. Verify idempotent payment confirmation (prevent double unlocks).

## Phase 6: Journey Unlock & State Management (51-60)
- [x] 51. Verify Journey State Cache holds full journey object for 15 mins.
- [x] 52. Test `POST /api/journey/unlock` with valid journey ID.
- [ ] 53. Verify unlocked route is saved in `unlocked_routes` table.
- [ ] 54. Test double-unlock does not trigger redundant seat verifications.
- [ ] 55. Check that Unlock API returns detailed journey segments.
- [ ] 56. Test Unlock API behavior when journey cache expires.
- [ ] 57. Verify `cache_service` correctly locks seats/journeys.
- [ ] 58. Audit payment status propagation to `unlocked_routes.is_active`.
- [ ] 59. Confirm the verification info is passed along in the unlock response.
- [ ] 60. Ensure robust error handling for missing/invalid journey IDs.

## Phase 7: Manual Booking Execution (61-70)
- [x] 61. Validate `POST /api/v1/booking/request` flow.
- [x] 62. Test passenger details insertion and parsing.
- [x] 63. Verify Telegram Alert triggers automatically on new request.
- [x] 64. Inspect `BookingQueue` entry creation.
- [ ] 65. Validate Admin UI endpoints (`/api/admin/bookings`) can read the queue.
- [ ] 66. Test Admin manual status update for `booking_requests`.
- [ ] 67. Ensure user can view `PENDING` booking status via `/requests/my`.
- [ ] 68. Verify DB cascading deletes/updates for booking passengers.
- [ ] 69. Check that queue prioritizes requests properly.
- [x] 70. Ensure Telegram message format contains all needed manual booking info.

## Phase 8: Real-time Tracking & Feedback (71-75)
- [x] 71. Confirm `live_locations` endpoint correctly stores GPS data.
- [ ] 72. Implement PNR status mock update endpoint.
- [ ] 73. Test Refund API endpoint for failed bookings.
- [ ] 74. Verify Cancellation rule application.
- [ ] 75. Review final end-to-end metrics (`latency_ms`, API calls).
