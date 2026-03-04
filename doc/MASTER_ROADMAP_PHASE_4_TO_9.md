# 🏆 The Master Roadmap: Phases 4 to 9

This document outlines the specific, high-priority tasks required to evolve RouteMaster into a fully autonomous, hyper-safe, AI-driven railway ticketing and tracking platform.

---

## 🤖 Phase 4: Web Chatbot Intelligence (25 Tasks)
*Focus: Creating a sub-50ms, context-aware AI assistant that feels like a human travel agent.*

1. **Local NLP Intent Router**: Implement a lightweight Regex/Trie-based pre-processor to route obvious intents (`/pnr`, `/search`) without hitting the LLM API.
2. **WebSocket Token Streaming**: Stream LLM responses chunk-by-chunk via WebSockets for <200ms Time-To-First-Token (TTFT).
3. **Session Context Windowing**: Use Redis to store the last 10 messages of conversational context, mapped to the user's `session_id`.
4. **Entity Extraction Middleware**: Auto-extract Source, Destination, and Date from natural language (e.g., "Delhi to Mumbai tomorrow") using a fast NER (Named Entity Recognition) model.
5. **RAG Database Grounding**: Connect the Chatbot directly to `transit_graph.db` using Text-to-SQL so it answers queries based on *real* train data, not AI hallucinations.
6. **Dynamic Suggestion Chips**: Auto-generate clickable chips (e.g., "Check Availability", "Alternative Routes") based on the current conversational state.
7. **Offline Message Queue**: Use IndexedDB to queue messages sent while passing through a tunnel, auto-sending when 4G restores.
8. **Voice-to-Text Integration**: Integrate Web Speech API for native voice commands with a custom wake-word listener.
9. **Multi-lingual Translation Layer**: Auto-detect language (Hindi, Tamil, etc.) and translate inputs/outputs on the fly without changing the core English AI prompt.
10. **Typing Cadence Indicator**: Add a dynamic `...` typing indicator that calculates the expected LLM generation time to manage user psychology.
11. **Chatbot-to-UI Event Bus**: Allow the chatbot to trigger UI changes (e.g., "Show me the map" auto-opens the map component).
12. **Markdown & Table Renderer**: Upgrade the chat UI to render rich markdown tables for train schedules.
13. **Auto-Correction Dictionary**: Implement a fuzzy-matching spell checker for Indian station names (e.g., "Hwrah" -> "Howrah").
14. **Fare Calculation Tool**: Give the LLM a specific `calculate_fare` tool call to accurately quote prices from the `class_fare_matrix`.
15. **Sentiment Analysis Throttle**: Detect angry/frustrated user sentiment and automatically switch to a more concise, apologetic, and solution-oriented prompt.
16. **Token Usage Limiter**: Implement a daily token limit per anonymous session to prevent API abuse.
17. **Conversational PNR Status**: Allow users to paste a PNR and have the bot parse the status, delay, and coach position naturally.
18. **Prompt Injection Firewalls**: Add strict pre-prompt guardrails to prevent users from jailbreaking the travel bot.
19. **Cache "Frequent Questions"**: Use an LRU cache for identical queries (e.g., "What is the tatkal timing?") to save LLM costs.
20. **Visual Route Summaries**: Generate mini inline SVG route maps inside the chat bubble when discussing a specific journey.
21. **Auto-Scroll Management**: Smoothly pin the chat to the bottom during streaming, but pause auto-scroll if the user scrolls up to read.
22. **Interactive Date Picker in Chat**: Render a React Calendar component *inside* the chat flow when the bot asks "Which date?".
23. **Historical Chat Retrieval**: Allow authenticated users to load previous travel planning conversations from Supabase.
24. **Local Fallback Responses**: If the LLM API fails, seamlessly fallback to a local rule-based engine ("I'm having trouble connecting to my brain, but I can still search routes if you click here").
25. **Feedback Loop (RLHF)**: Add 👍/👎 buttons to bot responses, feeding back into `rl_feedback_logs` for future fine-tuning.


---

## 🛡️ Phase 5: Safety & Emergency Systems (25 Tasks)
*Focus: Life-saving features that trigger automatically during transit anomalies.*

1. **Background Geolocation Worker**: Implement a Service Worker to track GPS coordinates even when the screen is off.
2. **Haversine Deviation Engine**: Calculate if the user's GPS strays more than 5km from the `trip_geometry_blob` path.
3. **Automated SOS Trigger**: Trigger an automatic countdown to SOS if the user's location remains stationary in a known high-risk zone for >30 mins.
4. **"Dead Zone" Prediction**: Warn the user 10 minutes before the train enters a known cellular dead zone (based on historical tracking data).
5. **One-Tap SOS Widget**: A persistent, red floating action button on the tracking screen that bypasses all locks to send an alert.
6. **Telegram Emergency Broadcast**: Instantly send a predefined SOS message + live Google Maps link to the user's linked Telegram emergency contacts.
7. **Offline SMS Fallback**: If internet fails during SOS, auto-generate a pre-filled SMS with coordinates via `sms:` URI scheme.
8. **Battery Drain Monitor**: Stop aggressive GPS tracking if battery drops below 15% and send a "Low Battery Last Known Location" ping.
9. **Female Traveler "Safe Mode"**: Highlight routes that arrive during daylight hours and avoid transfers at poorly lit stations.
10. **Crowdsourced Station Safety Ratings**: Allow users to rate stations on lighting, police presence, and crowds.
11. **RPF Helpline Integration**: Provide 1-click dial to 139 (Railway Police) with spoken instructions in the local language.
12. **Journey Sharing Link Generation**: Generate a secure, time-limited web link that parents/friends can view without downloading the app.
13. **Geo-Fenced Wake-Up Alarm**: An alarm that rings exactly 15 km before the destination station, calculated via live GPS, not schedule.
14. **Platform Change Alerts**: Push notification if the live API detects a sudden platform change at the upcoming junction.
15. **Train Reversal Warning**: Warn users when a train reverses direction (loco change) so they aren't disoriented.
16. **High-Speed Derailment Monitor**: Use the device accelerometer to detect sudden, violent G-force changes, prompting an "Are you safe?" check.
17. **Secure Medical Profile**: Store encrypted blood type and emergency allergies locally to display during an SOS event.
18. **Delay Ripple Warning**: Alert users if the train *ahead* of them on the same track breaks down, predicting an impending halt.
19. **Coach Position Navigator**: Show exactly where the user's coach (e.g., S4) will halt on the platform relative to the exit stairs.
20. **Station Facility Pre-Check**: Warn the user if their transfer station has no waiting rooms or food during night hours.
21. **Fake GPS Spoofing Detection**: Prevent fake location injections using browser API integrity checks.
22. **WebRTC Audio/Video Streaming Prep**: Build the architectural hooks to allow a live audio feed to a responder during an active SOS.
23. **Incident Heatmap UI**: Show a visual heatmap of recent delays/incidents on the route selection map.
24. **Periodic "Check-In" Ping**: For solo travelers, prompt a subtle "Everything okay?" notification every 4 hours.
25. **Post-Journey Safety Verification**: Require a final PIN or biometric scan to close the journey tracking successfully.

---

## 🔐 Phase 6: Multi-Level Verification (25 Tasks)
*Focus: Eradicating fraud, fake tickets, and bot abuse.*

1. **PNR Checksum Validation**: Implement Modulo-10 logic to instantly reject fake 10-digit PNRs on the frontend before hitting the API.
2. **Ticket PDF OCR Parsing**: Use Tesseract.js to extract PNR, Train No, and Passenger names directly from uploaded IRCTC PDFs.
3. **Live Status Cross-Check**: If a user uploads a ticket for a train that is cancelled in `transit_graph.db`, instantly flag it.
4. **Device Fingerprinting**: Generate a unique device hash using Canvas API to prevent one user creating 100 accounts.
5. **IRCTC Credential Pre-Validation**: Validate user-provided IRCTC UserIDs via a lightweight proxy ping before attempting booking.
6. **CAPTCHA Bypass Architecture**: Build the internal queue system to route IRCTC captchas to 3rd party OCR solvers (e.g., AntiCaptcha) during automation.
7. **Email OTP Parser**: Implement a secure webhook to parse IRCTC OTPs sent to the user's linked email address.
8. **SMS Intent Parsing (Android)**: Use the WebOTP API to auto-read IRCTC confirmation texts.
9. **Station Geofence Verification**: Verify a user is *actually* at the station when submitting a "Live Delay" report.
10. **JWT Token Rotation**: Implement short-lived (15m) access tokens and rolling refresh tokens in `apiClient.ts`.
11. **Tatkal Timing Rate Limiter**: Strictly throttle API requests at 09:59 AM and 10:59 AM to prevent server DDOS.
12. **IP Rotation Manager**: Build a proxy rotation manager for backend scraper workers to avoid IRCTC IP bans.
13. **Passenger Name NLP Regex**: Reject invalid names (e.g., "asdfgh") using regex and Indian name dictionaries.
14. **Age/Gender Quota Mismatch**: Auto-verify that Senior Citizen quotas are only applied to Males > 60 and Females > 58.
15. **Duplicate Journey Detection**: Prevent a user from booking two overlapping journeys on the same date.
16. **Payment UTR Regex**: Validate 12-digit UPI UTR numbers strictly before moving to manual verification queues.
17. **Honeypot Traps**: Add invisible form fields to the booking UI to catch dumb bots.
18. **Telegram Deep-Link Auth**: Use Telegram `initData` crypto-verification to securely log users into the Mini App without passwords.
19. **Route Feasibility Verification**: Ensure `arrival_time` > `departure_time`, handling midnight crossovers using the day offset logic.
20. **Fare Discrepancy Alert**: Flag bookings if the backend estimated fare deviates > 15% from the scraped IRCTC fare.
21. **Concurrent Login Blocker**: Invalidate old sessions if the same user logs in from a new device (configurable).
22. **Waitlist Probability ML Check**: Reject auto-booking if historical ML data shows the WL has < 10% chance of confirmation.
23. **Headless Browser Stealth**: Implement `puppeteer-extra-plugin-stealth` for the automated booking workers.
24. **Dynamic Request Signatures**: Add a rotating cryptographic signature to frontend API calls to block cURL scripting.
25. **Admin Audit Dashboard**: A UI for admins to manually verify flagged "suspicious" bookings or UTRs.

---

## 💸 Phase 7: UPI & QR-Based Payments (25 Tasks)
*Focus: Seamless, Zero-Gateway, Zero-Fee Indian Payments (No Razorpay/Stripe).*

1. **Dynamic UPI URI Generator**: Create `upi://pay?pa=MERCHANT_UPI_ID&pn=RouteMaster&am=AMOUNT&tr=ORDER_ID` strings dynamically.
2. **React QR Code Renderer**: Implement `qrcode.react` to display the dynamic UPI URI as a scannable QR code for desktop users.
3. **Mobile Intent Deep-Linking**: On mobile, render buttons that directly open GPay, PhonePe, or Paytm using the `intent://` scheme.
4. **Order ID Correlation**: Generate a unique `tx_id` and embed it in the `&tr=` parameter of the UPI link to track the exact transaction.
5. **Payment Polling Hook**: Create `usePaymentPolling` to ping the backend every 3 seconds to check if the transaction status changed to "SUCCESS".
6. **Manual UTR Upload UI**: A fallback UI allowing users to manually type their 12-digit UPI reference number if auto-polling fails.
7. **Transaction Timeout Cron**: A background worker that automatically marks pending payments as "FAILED" after 10 minutes.
8. **Amount Validation Sandbox**: Backend logic to verify the received UPI amount matches the exact requested cart amount down to the decimal.
9. **Zero-Fee Calculation**: Remove all gateway surcharges from the UI to emphasize the "P2P" nature of the transaction.
10. **Bank SMS Webhook Integration**: Set up an Android companion app or banking webhook to auto-parse incoming bank SMS for UTRs and amounts.
11. **Refund Queue Architecture**: A table to queue failed bookings that require manual/auto UPI refunds back to the user's VPA.
12. **Partial Refund Logic**: Logic to calculate cancellation charges and refund the remainder via UPI.
13. **UPI App Auto-Detect**: JavaScript logic to detect installed UPI apps on Android and hide buttons for apps the user doesn't have.
14. **Escrow State Machine**: Define strict DB states: `CREATED -> QR_SCANNED -> UTR_SUBMITTED -> VERIFIED -> BOOKING_INITIATED`.
15. **Payment Loading Skeleton**: A smooth pulsing UI while waiting for the user to complete the payment on their phone.
16. **Session Lock During Payment**: Prevent the user from navigating away or modifying passengers once the QR code is generated.
17. **QR Code Expiry UI**: Add a visual 10-minute countdown timer inside the QR code component.
18. **WhatsApp Payment Integration**: Generate links formatted for WhatsApp Pay if the user prefers it.
19. **Fraudulent UTR Lockout**: Temporarily ban IP/User if they submit invalid or duplicate UTRs 3 times in a row.
20. **Multi-VPA Load Balancing**: Rotate between multiple Merchant UPI IDs if transaction limits (e.g., ₹1 Lakh/day) are reached.
21. **Payment Confirmation Confetti**: Trigger a satisfying UI animation when the backend confirms receipt of funds.
22. **Auto-Retry Failed Polling**: Implement exponential backoff for the polling API to handle spotty internet during payment.
23. **Fare Update Re-calculation**: If IRCTC dynamic fare changes during checkout, instantly update the QR code amount.
24. **Split Payment Logic**: (Future) Allow two passengers to scan two different QR codes for 50% of the fare each.
25. **Ledger Reconciliation Script**: A nightly script to match DB `VERIFIED` transactions against an exported bank CSV.

---

## 🚄 Phase 8: Automated AI Booking Pipeline (25 Tasks)
*Focus: The "Ghost Worker" that actually logs into IRCTC and books the ticket.*

1. **Headless Browser Pool Setup**: Initialize a Puppeteer/Playwright worker pool specifically for managing multiple headless IRCTC sessions.
2. **NLP to Passenger JSON Mapper**: Use the LLM to convert a chat message like "Book for me and my mom (55)" into the strict JSON schema required for booking.
3. **IRCTC Session Login Automator**: Script the login flow, handling the User ID, Password, and initiating the CAPTCHA solver.
4. **AI Captcha Solving Module**: Integrate an OCR API or a lightweight vision model to solve the IRCTC login/payment captchas.
5. **Train Search Automator**: Script the navigation to the specific train, date, and class within the headless browser.
6. **Availability Re-Verification**: The worker must explicitly check if the seats are still available before proceeding to passenger details.
7. **Passenger Form Auto-Filler**: Rapidly inject the `fullName`, `age`, `gender`, and `berth_preference` into the IRCTC DOM.
8. **Auto-Upgradation Opt-in**: Automatically check the "Consider for Auto Upgradation" checkbox during the flow.
9. **Payment Gateway Navigation**: Script the selection of the UPI/Wallet option on the final IRCTC payment page.
10. **Internal Virtual Card / Merchant Payment**: Automate the payment *to* IRCTC using a corporate wallet/UPI handler.
11. **Booking Confirmation Scraper**: Once paid, scrape the final PNR, Coach, and Seat numbers from the success page.
12. **PDF Ticket Generator**: Use Puppeteer's `page.pdf()` to generate a visually clean E-Ticket containing the scraped data.
13. **Queue Prioritization (Tatkal vs General)**: Ensure Tatkal requests bypass the standard queue and are executed with maximum priority at 10:00 AM.
14. **Failure State Handling**: If the train is sold out during the flow, gracefully abort and trigger the refund queue.
15. **Auto-Retry on Timeout**: If IRCTC servers hang (HTTP 503), the worker must auto-refresh and attempt to recover the session.
16. **Telegram API Dispatcher**: Use `python-telegram-bot` to push the generated PDF ticket directly to the user's Telegram chat.
17. **Webhook Callbacks to Frontend**: Send real-time updates (e.g., "Solving Captcha...", "Making Payment...") back to the UI via the multiplexed WebSocket.
18. **Preference Fallback Logic**: If Lower Berth is unavailable but the user requested it, implement logic to decide whether to book anyway or abort.
19. **Boarding Point Selection**: Automate selecting a different boarding point if requested by the user.
20. **GST/Convenience Fee Parser**: Scrape the exact IRCTC convenience fee to ensure our internal ledgers match perfectly.
21. **Proxy IP Warmup**: Ensure the proxy IP being used has visited IRCTC recently to avoid sudden Cloudflare blocks.
22. **Alternative Route Auto-Booking**: If Route A fails, the AI automatically calculates Route B (via hub) and begins booking that instead (if pre-authorized).
23. **Booking Analytics Logger**: Log the exact time taken for each step (Login -> Search -> Fill -> Pay) to monitor IRCTC latency.
24. **User Credential Vault**: Securely encrypt and retrieve the user's IRCTC password using AES-256 for the automation process.
25. **Success Notification Formatter**: Format a beautiful, emoji-rich summary message to send alongside the PDF ticket.

---

## 📱 Phase 9: Telegram Standalone Chatbot (25 Tasks)
*Focus: A fully-featured conversational interface living inside Telegram.*

1. **Telegram Bot API Initialization**: Set up the `python-telegram-bot` library with async webhooks (no polling in production).
2. **State Machine / Conversation Handler**: Implement states (e.g., `CHOOSING_ORIGIN`, `CHOOSING_DATE`, `AWAITING_PAYMENT`) to manage multi-step commands.
3. **The `/search` Wizard**: Build an interactive flow prompting for Source -> Dest -> Date using ReplyKeyboards.
4. **Inline Keyboard Route Selection**: Render search results as Inline Buttons so users can click a specific train to view details.
5. **Mini-App Deep Linking**: Add a "🖥️ Open in App" inline button that launches the React frontend with context (e.g., `?from=NDLS&to=BCT`).
6. **Location Attachment Parser**: Allow users to share their Telegram Location attachment to automatically set their "Origin" station.
7. **Contact Sharing Authentication**: Use Telegram's "Share Contact" button to instantly create an account and map their phone number.
8. **Redis Session Storage**: Store the user's conversation state and temporary search data in Redis so the bot survives server restarts.
9. **Natural Language Query Endpoint**: Connect the bot to the Phase 4 LLM logic (e.g., user types "Next train to Mumbai", bot parses it).
10. **Automated PNR Subscription (`/track`)**: Users send `/track 1234567890` and the bot adds them to a cron job for status updates.
11. **Push Notification Broadcaster**: A centralized function to push delay alerts, booking confirmations, and SOS responses to specific `chat_id`s.
12. **QR Code Image Generator**: Send the UPI Payment QR code as a compressed Photo attachment directly in the chat.
13. **PDF Ticket Delivery**: Send the generated E-Ticket document with a custom caption and thumbnail.
14. **Live Location Tracking Responder**: If a user shares "Live Location", calculate distance to destination and reply with ETA.
15. **Multilingual Command Support**: Allow aliases like `/khojo` for `/search`.
16. **User Context Memory**: "Remember" the user's last searched station and suggest it as a Quick Reply.
17. **Admin Broadcast Command (`/announce`)**: Allow admins to message all users (e.g., "System maintenance at 2 AM").
18. **Inline Query Mode (`@botname`)**: Allow users to type `@routemasterbot NDLS BCT` in *any* chat to instantly share a train schedule with friends.
19. **Help & Tutorial Command (`/start`)**: A beautifully formatted onboarding message with GIFs/Videos explaining how to use the bot.
20. **Rate Limiting & Anti-Spam**: Ignore users who send >5 messages per second to prevent webhook flooding.
21. **Exception Handling & Graceful Fails**: Catch all API errors and reply with a polite "System busy" message rather than dying silently.
22. **Payment Success Webhook Receiver**: When Phase 7 completes a payment, instantly trigger a "Payment Received ✅" message in the chat.
23. **Formatting & Parse Mode**: Ensure all bot responses use `ParseMode.HTML` or `MarkdownV2` for bolding train names and times.
24. **Callback Query Router**: Map all inline button clicks (e.g., `callback_data="book_12628"`) to their specific execution functions.
25. **Deploy Webhook to Production**: Bind the Telegram bot to the specific production URL (`https://api.routemaster.com/telegram/webhook`).

---

## 🛠️ Execution & Verification Methodology

When implementing the above roadmap, I will strictly adhere to the following execution loop to ensure zero regressions and verifiable success.

**Example Implementation Loop:**

> ✦ **Implementing: Phase 7, Suggestion #1 (Dynamic UPI URI Generator)**
> 
> *   **Action**: I will create `backend/utils/payments.py` containing a `generate_upi_intent` function that accepts `amount` and `tx_id`. I will also create an endpoint `/api/payments/qr` to serve this.
> *   **Code Execution**: *[Executes tool: write_file]*
> *   **Verification Plan**: I will create a test script to call the endpoint and verify the string strictly matches the NPCI UPI format (`upi://pay?pa=...`).
> *   **Test Execution**: *[Executes tool: run_shell_command]*
> 
> 🟢 **Status: Suggestion #1 Completed.**
> 
> I have now implemented the dynamic UPI generator. The verification script confirms the URI is perfectly formatted and ready for QR rendering. The system is resilient to missing parameters.

This methodical approach guarantees that every single one of the 150 tasks is mathematically verified, leaving no room for "silent failures" in production.
