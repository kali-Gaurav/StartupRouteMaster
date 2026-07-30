# 🚀 Production MVP Roadmap: The "Fundable" Stage

**Core Goal:** Perfect the existing system (Routing, Verification, Payments, Auth, and UX) to handle 1,000+ concurrent users with zero crashes, sub-50ms latency, and a delightful user experience. This is the stage to validate the product, win user trust, and secure funding.

---

## 🛠️ Phase 1: Core Engine & UX Hardening (50 Tasks)

### 🛤️ Bucket A: Advanced Routing & Categorization
1. **Intelligent Paginated Route Discovery & Verification** *(Expanded below)*
2. **Multi-Day Search Expansion Engine:** Auto-search +/- 1 day if exact date yield is < 5 routes.
3. **Smart Transfer Weighting:** Heavily penalize transfers < 30 mins (risk of missing) or > 6 hours (exhaustion).
4. **Category Normalization Algorithm:** Ensure "Fastest" isn't 10x more expensive; apply standard deviation bounds to categories.
5. **Route Deduplication Strictness:** Fix edge cases where identical trains with 1 min difference appear as separate routes.
6. **Hub-Only Routing Fallback:** If direct routing fails, force routing through major A1-tier hubs.
7. **Vectorized Haversine Upgrades:** Optimize geo-spatial queries for station proximity to sub-millisecond speeds.
8. **Train Cancellation Graph Pruning:** Instantly remove cancelled trains from the daily routing graph snapshot.
9. **Alternative Quota Suggestions:** Auto-suggest TATKAL or PREMIUM TATKAL if GN is WL>50.
10. **Dynamic Persona Overrides:** Allow users to toggle "Budget/Comfort/Fast" weights on the frontend live.

### 🔍 Bucket B: Verification & API Resilience
11. **RapidAPI Circuit Breaker:** Auto-fallback to historical/ML heuristics if the external API latency > 3s.
12. **Batched Availability Lookups:** Send 5 trains per request to external APIs to cut HTTP overhead.
13. **Stale Cache Prediction:** Cache availability for 6 hours if travel is > 30 days away, but only 5 mins if travel is tomorrow.
14. **Partial Verification Rescue:** If 1 leg of a 2-leg journey fails verification, retry exactly once before dropping.
15. **Fare Anomaly Detection:** Block routes where calculated fare deviates > 30% from the API response.
16. **ML Heuristic Fine-Tuning:** Improve the accuracy of the `get_route_availability_score` mock using historical data.
17. **Async Verification Streaming:** Stream verified routes to the frontend one-by-one so the UI populates instantly.
18. **Quota-Specific Cache Segmentation:** Ensure GN and TATKAL caches don't collide.
19. **Automated Graph Snapshot Refresh:** Build a cron job to rebuild the transit graph every night at 2 AM.
20. **Zero-Result Intelligent Explainer:** If no routes exist, clearly explain *why* (e.g., "No trains run on Tuesdays").

### 💳 Bucket C: Payment & Escrow Perfection
21. **Idempotent Payment Webhooks:** Ensure double-firing bank webhooks don't credit a user twice.
22. **QR Code Regeneration on Expiry:** Auto-refresh the QR code and VPA if the 15-minute window expires.
23. **Distributed Lock on UTR Submission:** Prevent double-clicking "Submit" from crashing the database.
24. **Fuzzy UTR Matching:** Detect and handle if a user types 'O' instead of '0' in the UTR.
25. **Partial Refund Ledger:** Handle cases where a user overpaid by mistake.
26. **Escrow State Machine Hardening:** Write comprehensive DB-level constraints preventing illegal state jumps.
27. **Agent Booking Concurrency Test:** Ensure 50 agents clicking "Claim" on 1 booking results in exactly 1 winner.
28. **Dynamic Fee Adjuster:** Admin toggle to change the ₹49 unlock fee live without server restart.
29. **Payment Session Recovery:** If a user closes the tab after paying but before submitting UTR, recover session via LocalStorage.
30. **Webhook IP Whitelisting Validation:** Strictly reject simulated payments from non-authorized IPs in production.

### 🔐 Bucket D: Authentication & Security
31. **Supabase JWT Verification Middleware:** Strictly validate frontend tokens on every secure backend route.
32. **Silent Token Refresh:** Implement interceptors in React to refresh auth tokens without logging users out.
33. **Encrypted Credential Vault Hardening:** Ensure IRCTC credentials (AES-256) are never logged in plain text.
34. **Brute-Force Login Protection:** Block IPs attempting > 10 failed logins in 5 minutes.
35. **Cross-Device Session Invalidation:** Logging in on Mobile should optionally invalidate Desktop.
36. **Role-Based Access Control (RBAC) Audit:** Ensure regular users cannot hit `/api/v2/admin` endpoints.
37. **GDPR/DPDP Account Deletion:** Implement a single endpoint to wipe all user data, logs, and un-anonymized bookings.
38. **API Payload Sanitization:** Strip malicious SQL/XSS from search parameters (Source, Dest).
39. **Admin Action Reversion:** Allow SuperAdmins to "Undo" an accidental payment rejection.
40. **Secure Password Reset Flow:** Deep link email integration for Supabase password recovery.

### 📱 Bucket E: Frontend UX & "Love" Features
41. **Skeleton Loaders for Everything:** Never show a blank screen during data fetching.
42. **Smooth Route Expansion Accordions:** Animate the "View Details" click on a route card.
43. **Mobile-First Touch Targets:** Ensure all buttons (Copy UTR, Claim, Load More) are at least 44x44px.
44. **Progressive Web App (PWA) Manifest:** Allow users to "Add to Home Screen".
45. **Network Reconnection Toasts:** Show "You are offline" and "Back online" gracefully.
46. **Search History Quick-Select:** Show last 3 searched routes when the user clicks the search bar.
47. **Interactive Station Autocomplete:** Highlight the matched substring in the dropdown.
48. **Date Picker Smart Constraints:** Disable past dates and dates > 120 days in the future.
49. **"Why this route?" Tooltips:** Add a ? icon explaining exactly why a route was categorized as "Best Value".
50. **System-Wide Dark Mode Toggle:** Implement a clean, bug-free dark mode for night-time booking.

---

## 🔬 Task 1 Deep Dive: Intelligent Paginated Route Discovery & Verification
*Currently, we might be verifying too many routes upfront (slow) or returning too few. We need a robust "Load More" system.*

* **[1.1] Cursor-Based Search Pagination Architecture:** Replace standard `OFFSET` with a robust `last_score` or `last_arrival_time` cursor in the backend `search_routes` API to allow deep, efficient graph traversal without performance degradation.
* **[1.2] Deferred Verification (Lazy Loading):** Modify the Orchestrator to only pass the first 15 *unverified* candidate routes to the RapidAPI verification step. Keep the rest in a temporary Redis list.
* **[1.3] Yield-Aware "Load More" Endpoint:** Create `GET /api/v2/search/load-more`. When clicked, the backend pulls the next batch from the Redis list, verifies them, and returns them. If the list is empty, it expands the graph search radius.
* **[1.4] Stale Cache Invalidation Logic:** Ensure that when pulling from the cache, routes verified > 15 minutes ago are re-verified silently in the background (Stale-While-Revalidate).
* **[1.5] Duplicate Cross-Page Prevention:** Implement a session-specific Bloom Filter or tracking set in Redis so that routes loaded on Page 2 absolutely never duplicate routes from Page 1, even if fares/availabilities shift.
* **[1.6] Frontend "Load More" Integration:** Implement the UI button in React. It must maintain the existing scroll position and smoothly append new routes to the DOM without jarring layout shifts.
* **[1.7] Categorization Merging:** Ensure that newly loaded routes correctly merge into existing categories (e.g., if a new route is cheaper than the current "Cheapest", it updates the category).
* **[1.8] RapidAPI Batching & Rate Limit Guard:** Group the verification of the 15 new routes into `asyncio.gather` batches of 5, adding a 200ms sleep between batches to prevent triggering RapidAPI's 429 Too Many Requests error.
* **[1.9] Heuristic Fallback on Timeout:** If the user clicks "Load More" and RapidAPI hangs for > 3 seconds, gracefully fall back to the internal ML availability heuristic and flag the routes with `is_estimated=True`.
* **[1.10] Comprehensive Pagination Verification Script:** Write a rigorous test `tests/verify_mvp_task_1.py` that simulates a user doing an initial search, then clicking "Load More" 3 times. It must mathematically assert that zero duplicates exist across all 4 pages and that API call counts were strictly minimized.