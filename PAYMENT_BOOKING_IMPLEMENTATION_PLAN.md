# 💳 Zero-Gateway Payment & AI Booking Implementation Plan (50 Tasks)

This document outlines the step-by-step roadmap to integrate the direct UPI Escrow system and the AI-driven "Ghost Worker" booking pipeline.

---

## 💸 Phase A: UPI & QR Escrow Infrastructure (Tasks 1-25)
*Focus: Seamless, gateway-free payments with a robust state machine.*

1.  **Dynamic UPI URI Generator**
    *   Subtask: Implement standard NPCI format: `upi://pay?pa=...`
    *   Subtask: Add support for custom notes and transaction IDs.
2.  **React QR Code Renderer**
    *   Subtask: Integrate `qrcode.react` with high-error correction (Level H).
    *   Subtask: Add a "Copy UPI ID" button as a fallback.
3.  **Mobile Intent Deep-Linking**
    *   Subtask: Detect Android/iOS user agents.
    *   Subtask: Implement `intent://` and `upi://` protocol switching for GPay/PhonePe.
4.  **Unique Transaction ID (tx_id) Correlation**
    *   Subtask: Generate high-entropy TX IDs (e.g., `TX_<timestamp>_<uuid>`).
    *   Subtask: Map TX ID to the `Booking` record in SQLite.
5.  **Enhanced Payment Polling System**
    *   Subtask: Implement `usePaymentPolling` hook with exponential backoff.
    *   Subtask: Handle WebSocket fallback for status updates.
6.  **Manual UTR Upload Interface**
    *   Subtask: Create a validated 12-digit UTR input field.
    *   Subtask: Add "Checking UTR..." loading state.
7.  **Escrow Timeout Background Worker**
    *   Subtask: Setup Redis-based cron to expire `CREATED` bookings after 15 minutes.
    *   Subtask: Send "Payment Timed Out" notification to frontend.
8.  **Strict Amount Validation Sandbox**
    *   Subtask: Compare received vs. requested amount to 2 decimal places.
    *   Subtask: Reject UTRs where amounts don't match exactly.
9.  **Zero-Gateway Fee Logic**
    *   Subtask: Remove all Razorpay/Stripe percentage calculation logic.
    *   Subtask: Update UI to show "₹0.00 Processing Fee".
10. **Duplicate UTR Prevention**
    *   Subtask: Add unique constraint/index on `utr_number`.
    *   Subtask: Block re-submission of used UTRs.
11. **Refund Queue Architecture**
    *   Subtask: Create `refund_queue` table for FAILED bookings.
    *   Subtask: Store user VPA for automated/manual payouts.
12. **Partial Refund Calculator**
    *   Subtask: Logic to subtract platform fee (if any) and refund remainder.
13. **UPI App Auto-Detector**
    *   Subtask: JS check for app-specific protocols.
    *   Subtask: Show "Open PhonePe" button only if installed (where possible).
14. **Escrow State Machine (The 5-Step Flow)**
    *   Subtask: Define states: `CREATED -> UTR_SUBMITTED -> VERIFIED -> BOOKING_INITIATED -> COMPLETED`.
    *   Subtask: Implement state-guard logic (prevent jumping states).
15. **Payment Loading Skeleton (Pulsing UI)**
    *   Subtask: Add `TrainCardSkeleton` style loaders for the payment area.
16. **Session Lock Architecture**
    *   Subtask: Freeze passenger and route data once QR is generated.
17. **QR Code Expiry UI (Countdown Timer)**
    *   Subtask: Add a visual 10-minute timer inside the QR component.
18. **WhatsApp Payment Bridge**
    *   Subtask: Generate `wa.me` links with pre-filled payment request text.
19. **Fraudulent UTR Lockout (IP Ban)**
    *   Subtask: Store invalid attempts in Redis.
    *   Subtask: Ban IP for 1 hour after 3 fake UTRs.
20. **Multi-VPA Merchant Rotation**
    *   Subtask: Logic to rotate between multiple receiver UPI IDs to avoid limit hits.
21. **Confetti Celebration (Success UI)**
    *   Subtask: Integrate `react-confetti` on the COMPLETED state.
22. **Auto-Retry Polling on Network Failure**
    *   Subtask: Detect 4G/Wifi drops and resume polling on reconnect.
23. **Dynamic Fare Update Check**
    *   Subtask: Final fare check before QR generation.
24. **Split Payment Support (Architecture only)**
    *   Subtask: Database support for multiple TX IDs per booking.
25. **Nightly Ledger Reconciliation**
    *   Subtask: Script to match SQLite `VERIFIED` status against CSV bank exports.

---

## 🚄 Phase B: Automated AI Booking Pipeline (Tasks 26-50)
*Focus: The "Ghost Worker" that executes the IRCTC booking.*

26. **Headless Browser Worker Pool**
    *   Subtask: Setup Playwright/Puppeteer pool in the backend.
27. **NLP Passenger Parser**
    *   Subtask: LLM tool to convert "Book for my wife" into JSON.
28. **IRCTC Login Automator**
    *   Subtask: Scripted login flow with headless stealth.
29. **AI CAPTCHA Solver Integration**
    *   Subtask: Bridge to OCR API or Vision Model for IRCTC captchas.
30. **Train Selection Script**
    *   Subtask: Auto-navigate to correct Train No and Class.
31. **Real-time Availability Re-check**
    *   Subtask: Abort booking if seats vanish during login.
32. **Passenger Form Auto-Filler**
    *   Subtask: Rapid DOM injection of names, ages, and berth preferences.
33. **Auto-Upgradation Toggle**
    *   Subtask: Logic to always check the "Auto Upgrade" box.
34. **Payment Gateway Navigation (IRCTC Side)**
    *   Subtask: Automate "Pay via UPI" selection on IRCTC.
35. **Internal Wallet/VPA Handler**
    *   Subtask: Automation to pay IRCTC from company funds once escrow is verified.
36. **PNR/Seat Scraper**
    *   Subtask: Extract 10-digit PNR and Coach/Seat from IRCTC success page.
37. **RouteMaster E-Ticket Generator**
    *   Subtask: Generate PDF Ticket with brand headers.
38. **Tatkal Queue Prioritization**
    *   Subtask: Logic to trigger specific workers exactly at 10:00/11:00 AM.
39. **Graceful Sold-Out Abort**
    *   Subtask: If booking fails, trigger the Refund Queue (Task 11).
40. **Fast-Retry on IRCTC 503**
    *   Subtask: Session recovery logic for IRCTC downtime.
41. **Telegram Ticket Dispatcher**
    *   Subtask: Push PDF to user's Telegram ID via Bot API.
42. **Live WebSocket Log Streaming**
    *   Subtask: Stream "Ghost Worker" steps (e.g., "Navigating to Page...") to UI.
43. **Berth Preference Fallback**
    *   Subtask: Logic to "Book anyway" if preferred berth is unavailable.
44. **Boarding Point Selector**
    *   Subtask: Automate selection of different boarding station.
45. **GST/Fee Scraper**
    *   Subtask: Parse exact IRCTC convenience fees for accounting.
46. **Proxy IP Warmup/Rotation**
    *   Subtask: Use residential proxies to avoid IRCTC IP bans.
47. **Alternative Hub-Route Auto-Booking**
    *   Subtask: AI suggest and book Route B if Route A is full.
48. **Latency Analytics Logger**
    *   Subtask: Log time taken for every step (Login -> PNR).
49. **AES-256 User Credential Vault**
    *   Subtask: Securely store user's IRCTC creds for 1-click booking.
50. **Final Success Notification Formatter**
    *   Subtask: Emoji-rich message with PNR and Seat details.
