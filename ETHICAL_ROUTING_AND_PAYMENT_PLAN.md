# 🚄 RouteMaster V2: Ethical Intelligence & Payment Blueprint (1000 Action Points)

This document outlines the 100 critical tasks to build a 100% ethical, non-scraping railway intelligence platform. The business model relies on charging users to unlock highly optimized, multi-transfer routes, followed by manual IRCTC deep-linking or human-agent booking.

---

## 🔍 Phase 1: Real-Time Seat & Fare Verification (Tasks 1-20)
*Focus: Replacing all scraping with ethical partner APIs (RapidAPI / B2B Providers).*

**Task 1: Official API Integration Architecture**
1. Remove all Playwright headless browser code for availability checks.
2. Establish secure connection to RapidAPI IRCTC partner endpoints.
3. Create generic interface `ISeatAvailabilityProvider`.
4. Implement fallback logic if primary API fails.
5. Setup Redis caching for seat availability (5-minute TTL).
6. Log API latency and success rates.
7. Map API response codes to internal RouteMaster codes.
8. Handle quota-specific availability (GN, TQ, LD).
9. Setup alerting for API rate limits.
10. Verify data consistency between API and IRCTC portal.

**Task 2: Dynamic Fare Calculator Engine**
1. Fetch base fares from official APIs.
2. Calculate dynamic Tatkal/Premium Tatkal surges.
3. Calculate age-based concessions (if applicable via API).
4. Add RouteMaster platform fee (₹49) to the final presentation.
5. Cache fare rules in SQLite to reduce API calls.
6. Calculate combined fares for multi-leg journeys.
7. Implement caching for static fares (24-hour TTL).
8. Handle GST breakdowns for AC classes.
9. Support multi-currency display (backend conversion).
10. Audit trail for fare calculations.

*(Tasks 3-20: Caching strategies, Webhook listeners for live status, Station master data sync, Predictive waitlist algorithms, PNR status tracking API, Live Train tracking integration, Train cancellation detection, Route disruption alerts...)*

---

## 🗺️ Phase 2: Multi-Transfer Route Optimization (Tasks 21-40)
*Focus: Generating the core value proposition—complex routes that users will pay to unlock.*

**Task 21: RAPTOR Algorithm Refinement**
1. Optimize multi-leg routing for speed.
2. Filter out transfers with less than 45 mins buffer.
3. Prioritize routes where both legs have confirmed seats.
4. Calculate total journey fatigue scores.
5. Implement max-transfer limits (e.g., max 3 changes).
6. Factor in station infrastructure for transfer safety.
7. Penalize late-night layovers (e.g., 2 AM at small stations).
8. Generate alternative routes if direct trains are waitlisted.
9. Pre-compute popular routes nightly.
10. Expose REST endpoint for complex route queries.

**Task 22: Route Scoring & Sorting System**
1. Weight routes by total duration.
2. Weight routes by ticket availability confidence.
3. Weight routes by cost efficiency.
4. Combine weights into a `RouteMaster Score`.
5. Tag routes as "Fastest", "Cheapest", or "Highest Confirmation".
6. Sort API responses based on user preferences.
7. Implement safety-first sorting for solo travelers.
8. Highlight routes with "Guaranteed Seats" across all legs.
9. Filter out "risky" transfers.
10. A/B testing framework for sorting logic.

*(Tasks 23-40: Historical delay analysis, Hub-station logic, Geofenced transfer walking times, Platform predictability, Multi-modal integration (Bus to Train), User preference memory...)*

---

## 🔒 Phase 3: Route Masking & Unlock Escrow (Tasks 41-60)
*Focus: The Paywall—hiding data until the user pays ₹49.*

**Task 41: Frontend Route Masking Logic**
1. Intercept search results before rendering.
2. Show origin/destination and duration.
3. Mask Train Names and Numbers (e.g., "Train 1: AC 3-Tier").
4. Mask exact departure/arrival times (e.g., "Morning Departure").
5. Display a clear "Pay ₹49 to Unlock" Call to Action.
6. Show aggregate availability ("Confirmed Seats Available").
7. Add "Trust Badges" explaining what unlocking provides.
8. Prevent DOM inspection hacks (hide data in backend).
9. Implement skeleton loaders for masked data.
10. Mobile-optimized unlock drawer.

**Task 42: Secure Backend Payload Truncation**
1. Modify Search API to return `is_locked=True`.
2. Strip out `train_number` and `exact_times` from JSON response.
3. Return a `route_hash` to identify the route for unlocking.
4. Store the full unmasked route in Redis with a 30-min TTL.
5. Create endpoint to exchange `payment_id` for full route data.
6. Ensure no sensitive data leaks in network tabs.
7. Add JWT claims for unlocked routes.
8. Rate-limit the unlock endpoint.
9. Validate payment status before returning unmasked data.
10. Handle expired `route_hash` gracefully.

**Task 43: Payment Escrow Initialization (Unlock)**
1. Generate ₹49 UPI URI (Task 1 from previous phase).
2. Create `Payment` record linked to `route_hash`.
3. Display QR code and Mobile Deep Links.
4. Start 15-minute countdown for fare/seat lock.
5. Implement WebSocket polling for payment status.
6. Handle UTR submission for manual verification.
7. Auto-verify via Bank Webhook/SMS.
8. Mark `Payment` as `VERIFIED`.
9. Trigger UI transition to "Unlocked State".
10. Generate PDF Tax Invoice for the ₹49 service fee.

*(Tasks 44-60: Split payments, Promo codes, Wallet integration, Fraud UTR lockout, Daily revenue reconciliation, Refund queue for failed unmasks, Session persistence across devices...)*

---

## 🔗 Phase 4: IRCTC Deep-Linking & Smart Autofill (Tasks 61-80)
*Focus: Empowering the user to book manually but lightning-fast.*

**Task 61: IRCTC Deep-Link Generator**
1. Map RouteMaster station codes to IRCTC formats.
2. Construct base URL: `https://www.irctc.co.in/nget/train-search`.
3. Generate JS snippet to open IRCTC in a new tab.
4. Pre-fill "From" and "To" station caches if possible via URL params.
5. Pass Date parameters to IRCTC format (DD/MM/YYYY).
6. Create multi-leg deep links (open two tabs for two trains).
7. Track "Click-through Rate" to IRCTC.
8. Show a "How to Book" popup before redirecting.
9. Implement fallback to generic IRCTC homepage if deep-link fails.
10. Test deep-links across Chrome, Safari, and Mobile web.

**Task 62: Client-Side Autofill Helper**
1. Create a "Copy Passenger Data" button.
2. Format data into an easy-to-read clipboard string.
3. Develop an optional Chrome Extension for 1-click autofill.
4. Inject passenger data into Extension local storage.
5. Extension content script to detect IRCTC form fields.
6. Auto-populate Name, Age, Gender, Berth.
7. Ensure strict data privacy (clear clipboard/storage after 5 mins).
8. Handle multi-passenger forms dynamically.
9. Provide visual feedback when autofill completes.
10. Fallback instructions for manual entry.

*(Tasks 63-80: IRCTC session management tips, Captcha typing assistants, Fare mismatch alerts, Post-booking PNR entry prompt, Multi-tab synchronization for hub routes...)*

---

## 🤵 Phase 5: Agent-Assisted Booking Portal (Tasks 81-100)
*Focus: The premium human-touch service for users who don't want to book themselves.*

**Task 81: Agent Service Request Flow**
1. Add "Hire an Agent to Book" button on the Unlocked route page.
2. Display extra Agent Service Fee (e.g., ₹99).
3. Generate combined UPI payment request (Fare + Agent Fee).
4. Verify payment into Escrow.
5. Create `Booking` record with `service_type="AGENT_BOOKING"`.
6. Add record to the "Pending Agent Queue".
7. Notify all online Agents via WebSocket.
8. Send WhatsApp confirmation to user: "Agent assigned shortly."
9. Implement a 30-minute SLA countdown for Agent fulfillment.
10. Auto-refund logic if no Agent claims the task.

**Task 82: Agent Dashboard & Task Fulfillment**
1. Secure `/agent-portal` UI.
2. List all pending `AGENT_BOOKING` tasks.
3. "Claim Task" atomic lock (prevent double booking).
4. Display unmasked route and passenger details to the Agent.
5. Agent manually books on IRCTC using their own/company credentials.
6. Form to input final PNR and upload the official PDF ticket.
7. Mark task as `COMPLETED`.
8. Automatically email/WhatsApp the ticket to the User.
9. Transfer Escrow funds to Agent's ledger (minus platform cut).
10. Push notification to User's app with the PNR.

*(Tasks 83-100: Agent rating system, Dispute resolution, Document vault for ID proofs, Admin agent onboarding, SLA tracking, Automated PNR verification of uploaded tickets, Post-trip feedback...)*
