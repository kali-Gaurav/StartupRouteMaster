# MASTER_SYSTEM_EVOLUTION_ROADMAP.md - RouteMaster 2.0 (Elite & Lean)

This roadmap focuses on **Maximum Performance, Minimal Bloat, and Deep Core Utility**. Every subtask is designed to make the system faster, more reliable, and surgically precise for railway travel and safety.

---

## Task 1: Ultra-Responsive & Clean Chatbot UI
*Objective: Zero-lag, high-density, "No-Fluff" interface.*
1.1  **Virtualized Message Rendering**: Render only visible bubbles; keeps UI instant even with massive history.
1.2  **One-Tap History Selection**: Predictive source/destination buttons from recent searches.
1.3  **Frictionless Response Focus**: Auto-scroll to the *start* of AI replies for immediate reading.
1.4  **Multi-Row Grid Actions**: Fixed 2-column layout for core commands (No horizontal scrolling).
1.5  **Hardware-Accelerated UI**: 60fps transitions using CSS GPU transforms for mobile fluidity.
1.6  **Skeleton Loading States**: Prevents layout shifts during data fetch.
1.7  **Neon Connection Telemetry**: Minimalist status indicator for WebSocket health.
1.8  **Clean Markdown Logic**: High-contrast, readable text formatting for train details.
1.9  **Tactical Error Feedback**: Immediate, non-blocking red-glow alerts for failed inputs.
1.10 **Intersection Observer Sync**: Smart scrolling that pauses if user is manually reading history.
1.11 **Haptic Feedback (Mobile)**: Discrete vibration for critical alerts (SOS/Booking).
1.12 **Dark Mode Native Sync**: Zero-flicker theme switching.
1.13 **Adaptive Bubble Density**: Tighter spacing for system logs; comfortable for AI chat.
1.14 **Custom Minimal Scrollbar**: Hidden UI with high-performance touch inertia.
1.15 **Instant Close Origin**: Widget collapses back to the trigger button for visual continuity.
1.16 **Input Field Auto-Focus**: Keyboard opens instantly on chatbot activation.
1.17 **Draft Persistence**: Remembers typed but unsent text if widget is closed.
1.18 **Clear History Protocol**: One-tap local and remote session wipe.
1.19 **High-Contrast Bot Avatar**: Distinct visual identifier for AI vs User.
1.20 **Performance Profiler**: Client-side monitoring for frame-rate bottlenecks.

---

## Task 2: High-Speed NLP & Deep Intent Routing
*Objective: <100ms command parsing with surgical accuracy.*
2.1  **Regex-First Triage**: Instant local parsing for PNR, SOS, and Search (10ms latency).
2.2  **Hybrid Intent Fallback**: OpenRouter LLM only for complex queries; keeps system fast.
2.3  **Confidence Throttling**: Rejects vague commands early to avoid AI hallucination.
2.4  **Stateful Context Caching**: Redis-backed session memory for sequential commands.
2.5  **Fuzzy Station Resolver**: Ultra-fast Levenshtein distance matching for typos.
2.6  **Atomic Entity Extraction**: Pulls Date, Train #, and Class in one pass.
2.7  **Direct API Routing**: Skips AI chatter and goes straight to data for "PNR [Number]".
2.8  **Silent Intent Correction**: Automatically fixes common station spelling errors.
2.9  **LLM Latency Caching**: Store common AI responses in Redis.
2.10 **Priority SOS Parsing**: Danger-keywords trigger immediate backend emergency protocols.
2.11 **User Station Weighting**: Prioritizes local/frequent stations in search results.
2.12 **Hinglish Support**: Deep parsing for common Hindi-English travel slang.
2.13 **Time-Relative Parsing**: Resolves "Next Monday" to precise UTC.
2.14 **Intent-to-UI Event Bus**: JSON signals to trigger specific frontend modals.
2.15 **Abuse Rate Limiter**: Prevents bot-spamming of heavy search intents.
2.16 **Neural-Net Warmup**: Keeps inference engines active for instant response.
2.17 **Sentiment-Based Triage**: Detects emergency panic for faster SOS response.
2.18 **Contextual Suggestion Logic**: Shows "PNR Status" button *only* after a booking.
2.19 **Offline Intent Buffer**: Queues commands if network drops.
2.20 **Action Verification**: Confirms high-impact intents (e.g., Cancel) via bot prompt.

---

## Task 3: Unified Telegram Synergy
*Objective: Mirror the web experience on Telegram with zero friction.*
3.1  **Web-Telegram Bridge**: Secure one-time-password (OTP) for account linking.
3.2  **Keyboard Mirroring**: Telegram Suggestion Buttons mirror the web's Grid Actions.
3.3  **Inline Query Search**: Search trains in any Telegram chat via `@RouteMasterBot`.
3.4  **Asynchronous Webhook**: 200ms acknowledgement; background task processing.
3.5  **Live PNR Push**: Real-time Telegram notifications for status changes.
3.6  **Telegram SOS Trigger**: `/sos` command activates full safety protocols.
3.7  **Direct Ticket Delivery**: Sends E-Ticket PDFs directly to Telegram chat.
3.8  **Shared Chat State**: Continue web-app conversations on Telegram instantly.
3.9  **Telegram Mini-App**: Opens the RouteMaster Dashboard inside Telegram.
3.10 **Voice Message NLP**: Same intent engine handles Telegram voice notes.
3.11 **Notification Toggling**: Granular control of Telegram alerts.
3.12 **Group Travel Support**: Add bot to groups for collaborative searching.
3.13 **Bot Analytics**: Track command frequency and engagement.
3.14 **Silent Notification mode**: For non-critical updates.
3.15 **Markdown V2 Support**: Clean rendering of web tables in Telegram.
3.16 **Auto-Reply Keyboards**: Persistent menu for My Bookings/SOS.
3.17 **Secure Link Handling**: Telegram links open deep-routed web app pages.
3.18 **Bot API Rate-Limit Handling**: Prevents crash during mass alerts.
3.19 **Command Auto-Complete**: Hints for /start, /sos, /pnr.
3.20 **Telegram-to-Web Handover**: Seamless transition for payment completion.

---

## Task 4: High-Reliability SOS & Emergency Protocol
*Objective: Unbreakable, life-saving telemetry.*
4.1  **External Floating SOS**: Dedicated, non-obstructed emergency trigger.
4.2  **Silent Telemetry Mode**: Secretly sends location to contacts without UI noise.
4.3  **Geofencing Alerts**: Detects if user is off-track or at an unknown station.
4.4  **Low-Battery Protocol**: Forces GPS updates before device power-off.
4.5  **Multi-Channel Kin Alerts**: SMS, Email, and Telegram notifications in parallel.
4.6  **Railway Police Uplink**: Automated incident reporting to official APIs.
4.7  **Guardian Mode**: 15-min check-in timer; auto-SOS if not canceled.
4.8  **SOS Persistence**: Alert remains active across page refreshes/tab close.
4.9  **Offline SOS Buffer**: Stores location pings; syncs instantly on 4G restore.
4.10 **Emergency PII Packet**: Includes Blood Group/Medical Info in SOS.
4.11 **Quick-Action "Safe" Button**: One-tap notification that danger has passed.
4.12 **Accidental Trigger Delay**: 3-second visual countdown with haptic feedback.
4.13 **Audio Siren Protocol**: High-decibel siren for local device identification.
4.14 **Forensic Signal Audit**: Logs cell signal strength during incident.
4.15 **PIN-Locked Deactivation**: Prevents unauthorized SOS cancellation.
4.16 **Visual Distress Signal**: Flashes screen/torch using Web APIs.
4.17 **GPS Variance Handling**: Flags "Uncertain Location" if GPS accuracy is low.
4.18 **SOS Status Page**: Clean dashboard for incident tracking.
4.19 **Background Recording**: Captures 30s of environmental audio during SOS.
4.20 **SOS System Audit**: Periodic silent health-check of the emergency backend.

---

## Task 5: Deep Performance & Data Optimization
*Objective: Data delivery at the speed of thought.*
5.1  **Redis Search Caching**: <50ms lookup for common routes.
5.2  **Supabase Realtime**: Zero-latency PNR updates pushed to UI.
5.3  **Delta Data Sync**: Only transmits what changed (Saves data on 3G).
5.4  **Optimistic UI updates**: Shows actions as successful before DB confirms.
5.5  **Database Pooling**: High-concurrency support for FastAPI.
5.6  **Redis Pub/Sub**: Syncs chatbot messages across all backend nodes.
5.7  **Encrypted Local Storage**: Securely caches session and PII.
5.8  **Cache Warmup Logic**: Pre-loads popular stations into RAM.
5.9  **Brotli Compression**: Shrinks JSON payloads for faster transmission.
5.10 **Background Workers**: Fetches data even when the tab is inactive.
5.11 **Stale-Data Invalidation**: Refreshes fares only when Scraper detects change.
5.12 **Memory Leak Guard**: Client-side cleanup of old message objects.
5.13 **Atomic Redis Counters**: For real-time active user tracking.
5.14 **CDN Edge Hosting**: UI assets served from nearest physical location.
5.15 **Circuit Breaker**: Skips slow DB calls to prevent UI hang.
5.16 **SQL Index Audit**: Optimizes all search and booking queries.
5.17 **Batch-Writes to DB**: Consolidates multiple logs into one transaction.
5.18 **Offline PWA Mirror**: Access tickets and SOS history without internet.
5.19 **API Request Signing**: Prevents unauthorized API access.
5.20 **Connection Throttling**: Protects backend from DDoS search requests.

---

## Task 6: Proactive AI & Assistance (Required Only)
*Objective: Actionable alerts, not useless chatter.*
6.1  **Predictive Delay Notifications**: Alerting 2hrs before departure.
6.2  **PNR Expiry Reminders**: 4hrs before journey status check.
6.3  **Smart Nudges**: "Open Dashboard" prompt after first booking.
6.4  **Fare Drop Alerts**: For previously searched routes.
6.5  **Night-Travel Guardian**: Proactive SOS prompt for late-night journeys.
6.6  **Download Invoices**: Automatic button after payment success.
6.7  **Refund Tracking**: Real-time status of returned money.
6.8  **Journey Insights**: Summary of distance/time in Dashboard.
6.9  **Battery-Save Mode**: Proactive prompt when device hits 15%.
6.10 **Next-Step Prediction**: Logic-based action buttons (Search -> Book).
6.11 **Station Platform Alerts**: Displayed automatically upon arrival.
6.12 **AI "Diksha" Consistency**: Professional and precise bot persona.
6.13 **User Class Preference**: Remembers SL/3A/2A choices.
6.14 **Proactive SOS Verification**: Checks "Are you safe?" if train stops.
6.15 **Telegram Delay Sync**: Pushes critical alerts to phone instantly.
6.16 **Smart Telegram Nudges**: If web notifications are missed.
6.17 **Historical Search Memory**: Auto-populates search fields.
6.18 **PNR Status Highlights**: Summarizes long status history.
6.19 **Active Journey Sidebar**: Real-time status in main UI shell.
6.20 **ML Intent Self-Correction**: Learns from user "Clarify" feedback.

---

## Task 7: Essential Interaction & Core Accessibility
*Objective: High-speed input and data extraction.*
7.1  **Web Speech API**: Fast voice-to-text for hands-free searching.
7.2  **Critical TTS**: Audio alerts for SOS and PNR updates.
7.3  **PNR OCR Extraction**: Status from ticket screenshots (Clean & Fast).
7.4  **In-Chat Maps**: Lightweight Leaflet integration for live tracking.
7.5  **Audio Confirmation Tones**: Discrete SFX for system success/error.
7.6  **Multimedia Result Cards**: Clean image/icon support for trains.
7.7  **Voice Command Shortcuts**: "Check my last PNR" support.
7.8  **Low-Bandwidth Mode**: Drops images/icons on slow connections.
7.9  **Keyboard Accessibility**: Full Tab/Enter support for all bot actions.
7.10 **Screen-Reader Optimization**: WCAG 2.1 compliant labels.
7.11 **Fast Image Preview**: Optimized ticket view in chatbot.
7.12 **Voice Sensitivity Control**: For noisy station environments.
7.13 **Unified Action Dispatcher**: One function handles Web/Voice/Button.
7.14 **Interactive Charts (Lean)**: Simple SVG journey analytics.
7.15 **Multimedia Seat Map**: Visual confirmation of berth position.
7.16 **Voice-Based Navigation**: "Open SOS" vocal command.
7.17 **Encrypted Multimedia Logs**: Secure storage for SOS recordings.
7.18 **Bug Screenshot Upload**: Direct feedback via chatbot.
7.19 **Multi-Lingual UI**: English/Hindi toggle for core actions.
7.20 **Input Method Switching**: Seamless toggle between Voice and Text.

---

## Task 8: Global State & Navigation Logic
*Objective: Zero-friction transitions.*
8.1  **Zustand Global Store**: Synced state across Chat and Pages.
8.2  **Deep Linking Support**: Navigation via URL params (e.g., ?pnr=...).
8.3  **SOS Route Guard**: Prevents accidental exit during emergency.
8.4  **State Hydration**: Restores chat and intent after refresh.
8.5  **Cross-Tab Sync**: Message updates appear in all open tabs.
8.6  **Slide Micro-Transitions**: Smooth navigation between Dashboard/SOS.
8.7  **Intelligent Back-Button**: Closes chatbot widget first.
8.8  **Filter Persistence**: Keeps search criteria active across pages.
8.9  **Unified Loading Overlay**: Stark-grade system boot animation.
8.10 **Active Sidebar Context**: Reflects current journey/SOS status.
8.11 **Shared Session Context**: Consistent AI memory across app.
8.12 **Global Action Dispatcher**: Centralized intent handling.
8.13 **Layout Persistence**: Remembers widget expanded/collapsed state.
8.14 **Modal Manager**: Unified system for SOS/PNR alerts.
8.15 **State Sanitization**: Protects PII from logs/analytics.
8.16 **Automatic Session Timeout**: Clears state after inactivity.
8.17 **Nav-Analytics**: Tracks which features are actually used.
8.18 **Undo/Redo Actions**: For history clearing or filter changes.
8.19 **Hot-Reload Support**: Stable state during dev updates.
8.20 **Performance Profiler**: Monitors state update lag.

---

## Task 9: Security & PII Protection
*Objective: Unbreakable privacy.*
9.1  **JWT Token Rotation**: Secure, auto-refreshing sessions.
9.2  **Log Redaction**: Automatic masking of PNRs and Phones.
9.3  **Vault Encryption**: Secure storage for sensitive fields.
9.4  **CORS/CSP Policy**: Prevents XSS and Clickjacking.
9.5  **2FA for High-Risk**: Required for ticket cancellation.
9.6  **Secure WS Handshake**: Authenticated Chatbot connections.
9.10 **Bot Authentication**: Validates Telegram IDs via Phone.
9.11 **Secure File Scanning**: Malware checks for ticket uploads.
9.12 **RBAC**: Different permissions for User vs Admin.
9.13 **Audit Logging**: Tracks all access to SOS/Booking data.
9.14 **Environment Isolation**: No secrets in the codebase.
9.15 **TLS 1.3 Enforcement**: Modern encryption for all traffic.
9.16 **Brute Force Protection**: IP lockouts after failures.
9.17 **DB Snapshot Encryption**: Secure Supabase backups.
9.18 **Fingerprint Binding**: Tokens bound to specific devices.
9.19 **Security Headers Audit**: A+ security rating.
9.20 **Third-Party Sandboxing**: Isolates trackers from core data.

---

## Task 10: Final Audit & Validation
*Objective: 100% Operational Readiness.*
10.1 **E2E Latency Audit**: Verify <1s response for all intents.
10.2 **WS Concurrency Test**: 10,000 parallel chat connections.
10.3 **Scraper Load Test**: Ensures ETL stability under load.
10.4 **Memory Leak Audit**: 24hr chatbot stress test.
10.5 **Telegram Stress Test**: 1,000 msg/sec handling.
10.6 **Airplane Mode Test**: Offline SOS and Chat buffer check.
10.7 **Cross-Browser Check**: Chrome/Safari/Firefox/Mobile.
10.8 **Lighthouse Audit**: 95+ score for all metrics.
10.9 **Core Web Vitals**: FID/LCP within Stark ranges.
10.10 **Intent Weight A/B Test**: Optimizing regex vs AI accuracy.
10.11 **SOS Delivery Audit**: SMS/Email/Telegram reliability check.
10.12 **Backend Resource Audit**: CPU/RAM monitoring during peak.
10.13 **SQL Optimization Review**: Indices and query speed check.
10.14 **ETL Consistency Audit**: Redis vs DB parity check.
10.15 **Accessibility Audit**: Screen-reader and Tab-navigation check.
10.16 **Network Throttling Test**: Functionality on 2G/3G speeds.
10.17 **Atomic Transaction Audit**: No partial booking writes.
10.18 **Penetration Test**: Automated SQLi/XSS vulnerability scan.
10.19 **Final Feedback Loop**: Beta-user validation.
10.20 **Production Freeze**: Deployment to Railway/Vercel.

---
*Roadmap Version: 2.6 (Elite & Lean) | Status: Approved for Implementation*
