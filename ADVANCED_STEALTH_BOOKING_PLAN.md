# 🕵️ Advanced Stealth & Production Booking Blueprint (500 Action Points)

This document outlines the elite architecture for RouteMaster V2, focusing on bypassing Cloudflare/IRCTC bot detection and ensuring financial integrity.

---

## 🥷 Phase 1: Stealth & Fingerprint Mimicry (Tasks 1-15)

### 1. Playwright Stealth & Fingerprint Mimicry
1. Install `playwright-stealth` and `fake-useragent`.
2. Integrate `stealth_async` into the worker initialization.
3. Mask `navigator.webdriver` to `undefined`.
4. Spoof `chrome.runtime` and `navigator.plugins`.
5. Randomize WebGL renderer and vendor strings.
6. Emulate realistic `navigator.hardwareConcurrency`.
7. Fake `navigator.languages` to Indian English/Hindi.
8. Override `navigator.permissions` for geolocation.
9. Mask automation-specific Error stacks.
10. Implement periodic fingerprint "drift" to avoid static patterns.

### 2. Real Chrome Binary & TLS Mimicry
1. Detect system-installed Google Chrome path.
2. Implement `executable_path` launch logic in Playwright.
3. Disable `--enable-automation` and `--remote-debugging-port` flags.
4. Add `--disable-blink-features=AutomationControlled`.
5. Match TLS Hello signatures of real Chrome versions.
6. Configure Indian-resident `Accept-Language` headers.
7. Mimic real Chrome's `Sec-CH-UA` client hint headers.
8. Handle Brotli (`br`) compression correctly in responses.
9. Implement realistic HTTP/2 frame window sizing.
10. Verify TLS JA3 fingerprints against real browser databases.

### 3. Persistent Browser Profile Manager (Cookie Pool)
1. Create a `browser_profiles/` directory structure.
2. Implement `launch_persistent_context` logic.
3. Manage per-user or per-node persistent sessions.
4. Auto-save LocalStorage and SessionStorage.
5. Encrypt profile data using Task 49 logic.
6. Implement profile "locking" to prevent concurrent access.
7. Automated profile cleanup (clear cache/history only).
8. Backup/Restore logic for warmed sessions.
9. Profile health monitoring (Cookie expiry checks).
10. Logic to link specific IRCTC accounts to specific profiles.

### 4. Session Warm-up & Cookie Farming Engine
1. Background worker to browse IRCTC homepage.
2. Simulate random scrolling and element hovering.
3. Perform mock train searches to generate "History" cookies.
4. Stay on page for 30-60 seconds to satisfy Cloudflare.
5. Intercept and store "Clearance Tokens".
6. Navigate to secondary pages (Terms, Contact) to mimic human curiosity.
7. Schedule warm-up tasks every 6 hours.
8. Distribute warm-up tasks across the proxy pool.
9. Verify session validity before handing off to Ghost Worker.
10. Log "Warm-up Success Rate" metrics.

### 5. Human-Like Interaction Engine (Jitter)
1. Bezier curve mouse movement logic.
2. Random typing speed (CPM) with realistic delays.
3. Simulate occasional "typos" and "backspaces" during form filling.
4. Implement "Human Hesitation" before clicking "Pay".
5. Non-linear scrolling (acceleration/deceleration).
6. Random window resizing/viewport adjustments.
7. Tab-switching simulation (if applicable).
8. Element hover before clicking.
9. Random jitter in sleep intervals (`asyncio.sleep(random.uniform)`).
10. Verification: Playwright trace recording for "Visual Turing Test".

... (Tasks 6-15: WebGL randomization, Geolocation Spoofing, Network Jittering, etc.) ...

---

## 🚄 Phase 2: AI Booking & IRCTC Intelligence (Tasks 16-35)

### 16. Human-in-the-Loop CAPTCHA (Task 29 Pro)
1. Extract CAPTCHA element via OCR-friendly selectors.
2. Base64 encode and stream via WebSocket (Task 42).
3. Frontend UI component for manual entry.
4. Backend "Wait & Poll" logic for user response.
5. Captcha "Refresh" signal handler.
6. AI Fallback: Gemini Vision API implementation.
7. Auto-submit on 5-character length.
8. Latency logging for user response time.
9. Notification sound when CAPTCHA appears.
10. Automatic worker retry on "Invalid Captcha".

... (Tasks 17-35: NLP Parsing, Tatkal Timing, Seat Scrapers, Fee Parsers, etc.) ...

---

## 💸 Phase 3: Zero-Gateway Payment & Escrow (Tasks 36-50)

### 36. Advanced NPCI UPI Generator
1. URI 2.0 implementation with `tr`, `tid`, and `mc`.
2. Dynamic VPA rotation from Task 20.
3. Combined Fare + Platform Fee calculation.
4. High-error correction QR rendering.
5. Mobile deep-link detection logic.
6. WhatsApp Request Bridge (Task 18).
7. Haptic feedback on QR interaction.
8. Expiry countdown timer (15 mins).
9. Session lock during active payment.
10. Dynamic amount update on fare jump.

... (Tasks 37-50: Refund Queues, Ledger Recon, Fraud Lockout, IP Bans, etc.) ...
