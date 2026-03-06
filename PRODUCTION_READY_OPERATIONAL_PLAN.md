# 🚀 RouteMaster V2: Production-Ready Operational Plan (500 Action Points)

This document outlines the final 50 high-priority tasks required to move RouteMaster from a "working prototype" to a "stable fintech platform."

---

## 💸 Phase A: Zero-Gateway Payment & Escrow (Tasks 1-25)

### 1. Advanced NPCI UPI Generator
1. Implement URI version 2.0 specs.
2. Support `mam` (Minimum Amount) for split payments.
3. Add `mc` (Merchant Category Code).
4. Dynamic `tid` (Transaction ID) generation.
5. QR Code logo embedding (RouteMaster branding).
6. Short-URL redirector for UPI links (sms friendly).
7. Haptic feedback on QR generation (Mobile).
8. Fallback to Deep-Link intents if QR fails to render.
9. Custom "Verified Merchant" badge in UPI apps via parameters.
10. Automatic currency locking (INR only).

### 2. Real-Time Bank SMS/Webhook Integration
1. Android companion app for SMS parsing.
2. Regex engine for 20+ Indian banks (SBI, HDFC, ICICI, etc.).
3. Secure POST webhook for incoming transaction data.
4. Duplicate UTR filtering at the webhook layer.
5. Amount matching logic (Tolerance ±0.01).
6. Latency tracking between SMS sent and Webhook received.
7. End-to-end encryption for SMS data payload.
8. Battery/Connectivity monitoring for the companion app.
9. Auto-reconnect logic for WebSocket bridge.
10. Failover to manual bank CSV upload.

### 3. Fraudulent UTR Lockout (Task 19 Pro)
1. Per-IP attempt counter in Redis.
2. Per-User-ID attempt counter.
3. Device fingerprinting (Canvas/WebGL fingerprint).
4. Geometric pattern matching for "fake" UTR sequences.
5. Automatic 1-hour ban after 3 failed attempts.
6. Admin dashboard for manual unblocking.
7. Slack notification for suspected fraud clusters.
8. Geo-fencing (Restrict payments from outside India).
9. Velocity checks (Max 5 UTRs per 10 mins).
10. Honeypot UTR detection.

### 4. Multi-VPA Merchant Load Balancer
1. Dynamic VPA health checking.
2. Per-VPA daily volume tracking (₹1L limit).
3. Weight-based rotation logic.
4. Auto-removal of blacklisted/blocked VPAs.
5. VPA "Resting" period after high volume.
6. Support for Multi-Bank accounts.
7. Real-time VPA utilization dashboard.
8. Alerts when 80% of total capacity is reached.
9. Fallback VPA for "Emergency Only" status.
10. Per-region VPA assignment (South vs North bank nodes).

### 5. Platform Fee & GST Engine
1. Dynamic fee calculation based on ticket value.
2. Separate ledger entries for "Fare" vs "Service Fee".
3. GST (18%) auto-calculation on the Service Fee component.
4. Tax Invoice generator (PDF) for the user.
5. Monthly GSTR-1 export utility.
6. Support for "Discount Codes" on service fees.
7. Zero-fee toggle for "First Time Users".
8. Round-off logic to the nearest rupee.
9. Multi-currency architecture (Internal conversion only).
10. Merchant settlement delay simulator.

### 6. Refund Queue State Machine
1. `REFUND_PENDING` -> `REFUND_INITIATED` -> `REFUND_SUCCESS`.
2. Automatic refund trigger on IRCTC "Sold Out" status.
3. User VPA verification before refund.
4. Manual approval workflow for high-value refunds (>₹5000).
5. Partial refund logic (Subtracting IRCTC cancellation charges).
6. Refund receipt generation.
7. Bulk refund processing via Bank API/CSV.
8. Customer support "One-Click Refund" button.
9. Slack bot alerts for failed refunds.
10. Auto-retry logic for "VPA not found" errors.

### 7. Session Lock & Navigation Guard
1. Prevent browser "Back" during active Escrow.
2. Disable UI buttons once payment is confirmed.
3. WebSocket-based "Session Expired" overlay.
4. Sync state across multiple tabs.
5. Save "In-Progress" state to LocalStorage for recovery.
6. Warning popup if user tries to close the window.
7. Auto-cancel booking if user is idle for 15 mins.
8. Hardware back-button override (Mobile wrappers).
9. Redirect to success page if user refreshes after completion.
10. Heartbeat check to ensure user is still on the payment page.

### 8. Nightly Ledger Reconciliation (Task 25 Pro)
1. Auto-fetch bank CSV via SFTP/API.
2. Fuzzy matching for UTRs (handle typos).
3. "Suspense Account" for payments with no matching booking.
4. Automatic "VERIFIED" promotion for late-arriving payments.
5. Profit/Loss statement generator (Daily).
6. Discrepancy report sent to Admin email at 4:00 AM.
7. Audit trail for every status change.
8. Support for multiple bank statement formats.
9. Historical search for old transactions (up to 7 years).
10. Rollback logic for incorrectly verified bookings.

### 9. Mobile Deep-Link Detector
1. JS detection for PhonePe/GPay/Paytm installation.
2. Priority sorting of apps (Most used first).
3. `intent://` vs `upi://` protocol switching.
4. Device-specific CSS for "Open in App" buttons.
5. Fallback to "Copy VPA" if no apps found.
6. Auto-launch top app on button click.
7. Track "App Click-through Rate" (Analytics).
8. Custom handlers for iOS (Apple Pay fallback checks).
9. Delay-based fallback (If app doesn't open in 2s, show QR).
10. Branded "Payment Picker" modal.

### 10. QR Code Countdown & Expiry
1. 10-minute visual countdown timer.
2. Server-side timestamp validation.
3. "Refresh QR" button for expired sessions.
4. UI blur effect when timer hits 0.00.
5. Progressive color change (Green -> Orange -> Red).
6. Sync timer with Redis TTL.
7. Background tab timer pausing prevention.
8. Sound alert when 60 seconds remain.
9. Auto-cancel backend booking on expiry.
10. "Why did my QR expire?" tooltip.

*(Note: Tasks 11-25 involve Payment Latency Tracking, High-Entropy TXID Mapping, Split-Payment Architecture, Confetti Triggering, etc., with similar 10-point depth.)*

---


### 29. NLP Passenger Schema Mapper (Task 27 Pro)
1. Gemini-based name/age extraction.
2. Gender inference logic.
3. Berth preference normalization (LB -> Lower).
4. Senior Citizen quota detection (Age > 60).
5. Child passenger handling (Age < 5).
6. Validation against IRCTC character limits (16 chars).
7. Auto-correction of common typos in names.
8. Support for multi-passenger bulk text.
9. Identity document type mapping (Aadhar/Voter).
10. Confidence scoring for extracted data.

### 30. Tatkal Timing Precision (Task 38 Pro)
1. Millisecond-perfect login at 09:59:50 AM.
2. NTP Time sync for server clock.
3. Pre-filling form in background before 10 AM.
4. Auto-retry on "Service Unavailable" loop.
5. Prioritizing AC vs Non-AC workers.
6. Distributed workers across 3 servers for redundancy.
7. Automated logout/re-login to clear session cache.
8. "Tatkal Mode" UI for users (simplified).
9. One-click Tatkal "Force Start".
10. Success probability calculator.

### 32. Branded PDF Ticket Engine (Task 37 Pro)
1. `reportlab` template with SVG icons.
2. QR Code for PNR verification inside PDF.
3. Passenger-wise seat/coach mapping.
4. Advertisement/Promotional footer.
5. "Emergency SOS" numbers on ticket.
6. Branded color palette (RouteMaster Blue).
7. Auto-emailing PDF to user.
8. Ticket password protection (DOB).
9. Low-res vs High-res export options.
10. Dynamic boarding/destination station images.

### 33. Telegram Standalone Dispatcher (Task 41 Pro)
1. Bot API integration (Task 41).
2. Instant PNR notification.
3. Direct PDF download button in Telegram.
4. "Check PNR Status" inline button.
5. Support for multiple Telegram IDs per user.
6. Welcome message for new subscribers.
7. Offline notification queuing.
8. Rich-text formatting (HTML).
9. Bot command for "Last Booking".
10. Secure token rotation for the Bot API.

### 34. Alternative Hub-Route Suggestion (Task 47 Pro)
1. Graph-based hub-route search (Task 47).
2. Price difference calculator.
3. "Book Alternative" user prompt.
4. Automatic booking of 2 separate tickets for hub route.
5. Buffer time validation between trains (Min 2 hrs).
6. Unified PNR view for hub journeys.
7. Baggage handling warnings for transfers.
8. Platform number suggestions for hub stations.
9. Refund logic if Leg 1 succeeds but Leg 2 fails.
10. AI "Destination Guarantee" logic.

### 35. AES-256 Credential Vault (Task 49 Pro)
1. PBKDF2 key derivation from Master Key.
2. Per-user IV (Initialization Vector) for salt.
3. Auto-wipe credentials after booking completion.
4. "Store for 1-Click" user opt-in.
5. Security audit log for vault access.
6. Hardware security module (HSM) mock for dev.
7. Detection of weak passwords.
8. Multi-factor auth (MFA) challenge bridge.
9. Vault encryption at REST (Postgres).
10. Secure UI input (Hidden fields).

*(Tasks 36-50 involve Latency Analytics, IRCTC DOM Change detection, Auto-Upgradation logic, Boarding Point switching, GST Scrapers, and Latency-based Worker optimization.)*
