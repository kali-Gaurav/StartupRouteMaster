# Telegram System Design

## Purpose

Design a fully integrated Telegram channel for RouteMaster that mirrors the website experience, supports booking and notification workflows, and becomes a first-class travel assistant for users.

This document is the design phase. It defines architecture, data flow, user journeys, and implementation tasks before any tests are executed.

---

## 1. Goals

- Enable users to link their RouteMaster account with Telegram securely.
- Allow users to perform core travel operations from Telegram:
  - search routes
  - view bookings
  - check PNR/status
  - cancel or manage tickets
  - trigger SOS/emergency workflow
  - receive PDF ticket delivery
- Keep website and Telegram workflows synchronized.
- Use the same backend services and data model rather than creating a separate Telegram-only silo.
- Ensure production-grade resilience with retries, circuit breakers, and monitoring.
- Keep the design extensible for Telegram Mini-App and future voice/attachment handling.

---

## 2. Current System Summary

### Existing Telegram components

- `backend/services/telegram_dispatcher.py`
  - sends Telegram messages
  - uses `Config.TELEGRAM_BOT_TOKEN`
  - has circuit breaker and metrics support

- `backend/api/telegram_bot.py`
  - Telegram webhook endpoint at `/telegram/webhook`
  - links accounts with `/telegram/link-token` and `/telegram/link`
  - handles `/start`, `/help`, and default NLP-based messages
  - uses `command_handler` to dispatch commands

- `backend/api/auth.py`
  - supports Telegram auth via `init_data`
  - creates user accounts with synthetic emails like `tg_<id>@safesafar.app`

- `backend/database/models.py`
  - `User` contains `telegram_id`, `telegram_link_token`, `telegram_link_expiry`

- `backend/utils/nlp_router.py`
  - intent recognition for search, PNR, SOS, help, etc.

### Observed gaps

- No full command set for `/search`, `/pnr`, `/cancel`, `/bookings`, `/dashboard`.
- `link_telegram` endpoint is a stub.
- Web and Telegram flows are not fully synchronized.
- No callback query handling.
- PNR / booking retrieval is limited.
- No explicit account mapping table or multi-telegram support.
- Tests are currently not aligned with the current webhook implementation.

---

## 3. Proposed Architecture

### High-level architecture

```
┌───────────────┐         ┌───────────────┐
│ Telegram User │  <----> │  Telegram Bot │
└───────┬───────┘         └───────┬───────┘
                             │ Webhook / API
                             ▼
             ┌────────────────────────────────┐
             │       RouteMaster Backend       │
             │                                │
             │  ┌──────┐   ┌───────────┐      │
             │  │ Auth │   │  Telegram  │      │
             │  │      │   │ Dispatcher │      │
             │  └──────┘   └──────┬────┘      │
             │                  │           │
             │  ┌───────────────▼───────────┐ │
             │  │   Business Services       │ │
             │  │  (Search, Booking, PNR,   │ │
             │  │   SOS, Notifications)     │ │
             │  └───────────────┬──────────┘ │
             │                  │            │
             │  ┌───────────────▼──────────┐ │
             │  │   Database / Persistent   │ │
             │  │   Model / User Sessions   │ │
             │  └──────────────────────────┘ │
             └────────────────────────────────┘
```

### Component breakdown

1. **Telegram Webhook Handler** (`backend/api/telegram_bot.py`)
   - Validate webhook secret header
   - Parse `Update` objects: message, callback_query
   - Dispatch to command handler / callback processor asynchronously

2. **Command Router / Handler** (`backend/services/command_handlers/command_handler.py`)
   - Map explicit commands (`/start`, `/help`, `/search`, `/pnr`, `/bookings`, `/cancel`, `/sos`, `/dashboard`)
   - Fallback to NLP intent routing for natural language
   - Support async handler registration and chaining

3. **Dispatcher** (`backend/services/telegram_dispatcher.py`)
   - Generic `send_message`, `send_document`, `answer_callback_query`
   - Keyboard generation for `default`, `journey`, `help`, `booking`
   - Circuit breaker, retry, metrics

4. **NLP Intent Router** (`backend/utils/nlp_router.py`)
   - Recognize search routes, PNR, canceled, SOS, help, dashboard, telegram linking
   - Extract `source`, `destination`, `pnr`, date entities

5. **Account Linking / Auth**
   - One-time token generation via web settings (`/telegram/link-token`)
   - `/start <token>` deep link to confirm Telegram account
   - `auth/telegram` for Telegram login widget on web
   - Support `User.telegram_id` mapping and prevent duplicates

6. **Search / Booking / PNR Services**
   - Reuse website search endpoints and booking services
   - Build Telegram-specific summaries and menu prompts
   - Use same `SearchService`, `BookingService`, `User` models

7. **SOS / Emergency Flow**
   - `/sos` triggers admin notifications and optionally an emergency broadcast
   - Use existing safety/alert pipelines
   - Maintain audit trail in user model and/or emergency contacts

8. **Monitoring & Health**
   - Telegram webhook health endpoint
   - Dispatcher metrics, success rate, circuit state
   - Log webhook and link token events

---

## 4. Data Model

### User fields

- `telegram_id: str` — linked Telegram chat ID
- `telegram_link_token: str` — one-time token for web-to-bot linking
- `telegram_link_expiry: datetime` — expiry for link codes
- `preferences: JSON` — journey active / notification preferences
- `telegram_enabled` (optional extension) — boolean flag

### Optional extension: Telegram account mapping table

Instead of only `User.telegram_id`, consider:

- `TelegramAccount`
  - `id`
  - `user_id`
  - `telegram_id`
  - `linked_at`
  - `active`
  - `source` (`web`, `miniapp`, `bot`)

This supports multiple Telegram handles per user and cleaner security.

---

## 5. User Journeys

### 5.1 Account Linking

1. User visits the website -> Telegram settings
2. Clicks `Generate Telegram code`
3. Website returns one-time code
4. User opens Telegram bot and sends `/start <code>`
5. Bot verifies code, links `telegram_id` to `User`
6. Bot replies with welcome and menu

### 5.2 Search trains from Telegram

1. User sends `/search Mumbai to Delhi tomorrow`
2. Bot parses route and date
3. Bot calls `SearchService` with same engine used by website
4. Bot returns top 3 candidate journeys
5. User can follow up with `/bookings` or next steps

### 5.3 Booking lookup

1. User sends `/bookings` or natural text `my tickets`
2. Bot checks linked user
3. Bot returns recent bookings with PNR summary
4. User can send `/pnr 1234567890` for details

### 5.4 PNR status

1. User sends `/pnr 1234567890`
2. Bot resolves booking and returns journey status
3. If booking not found, bot recommends dashboard link

### 5.5 SOS flow

1. User sends `/sos` or `help me`
2. Bot confirms receipt and sends admin alert
3. Bot optionally pushes an emergency event into the RouteMaster safety pipeline

### 5.6 Dashboard handoff

- `/dashboard` returns a secure web link to dashboard
- Optionally include `telegram_deep_link` state in URL

---

## 6. API & Bot Command Surface

### Telegram bot commands

- `/start [token]`
- `/help`
- `/search <route>`
- `/bookings`
- `/pnr <number>`
- `/cancel`
- `/sos`
- `/dashboard`

### Web API endpoints

- `GET /telegram/link-token` — generate account linking code
- `POST /telegram/link` — persist Telegram ID for current logged-in user
- `POST /telegram/webhook` — Telegram bot webhook receiver
- `POST /auth/telegram` — Telegram login widget auth

---

## 7. Implementation Phases

### Phase 1: Design and alignment
- Finalize command set and flows
- Define exact data mappings and model updates
- Confirm webhook security strategy
- Choose whether to keep current `User.telegram_id` or add mapping table

### Phase 2: Core implementation
- Harden `backend/api/telegram_bot.py`
  - webhook security
  - callback query support
  - full command handlers
- Expand `backend/services/telegram_dispatcher.py`
  - generic `send_message`
  - `send_document`
  - action keyboards
- Reuse existing search / booking services
- Add link-token web endpoint
- Ensure Telegram auth uses same user identity store

### Phase 3: UX and experience
- Add friendly text prompts and keyboard flows
- Add fallback / clarification messages
- Add account not linked guidance
- Add dashboard open actions and safe URLs

### Phase 4: Testing and validation
- Unit tests for webhook, commands, link flow
- Integration tests for search, PNR, SOS
- Webhook security validation tests
- End-to-end flow through real or mocked `SearchService`

### Phase 5: Monitoring and production readiness
- Health endpoints
- Dispatcher metrics
- Circuit breaker alerts
- Admin notification path for SOS and failures
- Deployment config for `TELEGRAM_WEBHOOK_SECRET`

---

## 8. Atomic Task Breakdown

1. Audit current Telegram files and identify exact integration gaps
2. Define a new Telegram bot command sheet
3. Add webhook security header validation
4. Add callback query handling to Telegram bot
5. Expand default NLP handler for `/search`, `/pnr`, `/bookings`, `/cancel`, `/sos`
6. Add link-token generation endpoint
7. Implement `/link` endpoint logic and duplicate-ID protection
8. Add generic message dispatcher support in `telegram_dispatcher.py`
9. Create bot keyboards for default/journey/help/booking context
10. Add account linking user guidance text
11. Wire search results to `SearchService` and render summary cards
12. Wire PNR lookup and booking summary generation
13. Wire SOS to admin alert path
14. Add tests for webhook, commands, linking, and search flows
15. Add monitoring points and health metrics

---

## 9. Next Step

Proceed to implement the design in code after this document is reviewed and approved.

When ready, the first code step should be:
- update `backend/api/telegram_bot.py` to support the full command set and webhook security
- update `backend/services/telegram_dispatcher.py` to send generic Telegram messages and callback query responses
- add tests in `backend/tests/test_telegram_api.py` for the new command and linking flows
