# 🛰️ RouteMaster Telegram System Specification

This document serves as the master technical specification for the RouteMaster Telegram ecosystem. It defines the architecture, backend integration patterns, and the strategic roadmap for achieving cross-platform parity with the RouteMaster web application.

---

## 1. System Philosophy & Value Proposition
The Telegram bot is not merely a companion app; it is a **high-availability interface** designed for:
- **Low-Latency Interactions**: Fast train searches and PNR checks even on 2G/3G networks.
- **Proactive Safety**: Direct SOS integration with real-time location telemetry.
- **Frictionless Engagement**: Natural Language Processing (NLP) allowing users to "talk" to the system.
- **Cross-Platform Continuity**: Seamless transition between the Web Dashboard and Telegram.

---

## 2. Technical Architecture

### 🔄 Data Flow Pipeline & Lifecycle
The bot operates on a strictly defined, high-performance execution pipeline:

1.  **Ingress (Update Logic)**: 
    *   **Updates**: The bot distinguishes between `Message` (text, location, contact) and `CallbackQuery` (button clicks).
    *   **FastAPI Ingress**: Land at `/webhooks/telegram` (Production) or long-polling (Dev).
2.  **Session Recovery**: `UserSessionManager` retrieves the current state (Idle, Searching, Booking, etc.) from **Redis**.
3.  **Intent Classification**:
    *   **Direct Command**: Starts with `/` (e.g., `/search`).
    *   **Natural Language**: Handled by the `IntentClassifier` (NLP) to extract source, destination, and dates.
    *   **Callback Routing**: If the update is a `CallbackQuery`, it is routed directly to the handler specified in the `callback_data` (e.g., `search_next_page`).
4.  **Logic Execution**: The `CommandRouter` dispatches the task to specific handlers (Search, Booking, SOS).
5.  **Backend Synergy**: Handlers invoke internal microservices via the `FastAPI Gateway`.
6.  **Egress (Dispatcher)**: Results are formatted into HTML/Markdown and sent back with **Dynamic Keyboards**.

### 🧩 Core Component Stack
| Component | Responsibility | Technology |
| :--- | :--- | :--- |
| **FlowHandler** | Manages multi-turn conversations (e.g., 5-step booking flow). | Python State Machine |
| **Notification Manager** | Pushes asynchronous alerts (PNR changes, SOS alerts). | Kafka + WebSockets |
| **Identity Vault** | Manages JWT-based linking between Web and Telegram. | Supabase Auth + JWT |
| **State Store** | Stores ephemeral conversation state and PNR snapshots. | Redis (Upstash) |
| **Keyboards** | Generates dynamic Inline & Reply keyboards based on context. | Python Keyboards Module |

---

## 3. Backend Interaction Matrix
The Telegram system acts as a specialized "View" layer for the backend services.

### 🔌 Service Integration
| Service | Telegram Interaction Pattern |
| :--- | :--- |
| **Search Service** | Bot sends `src`, `dst`, `date` -> Receives optimized train list with ML availability. |
| **Booking Service** | Bot initiates booking sequence -> Backend creates a `PENDING` record in Postgres. |
| **SOS Service** | Bot triggers `EMERGENCY` mode -> Streams live GPS coords to the Admin Dashboard. |
| **User Service** | Syncs `Karma` points, saved passengers, and wallet balance. |
| **PNR Tracker** | Background workers poll status -> Bot pushes "Status Changed" notification. |

### 🔒 Identity Linking Logic (The "Sync" Protocol)
To link a Telegram account with a Website profile:
1.  **Website**: Generates a short-lived link: `t.me/RouteMasterBot?start=link_TOKEN`.
2.  **Telegram**: User clicks, bot receives `/start link_TOKEN`.
3.  **Verification**: Bot calls `UserService.verify_link(TOKEN, telegram_id)`.
4.  **Persistence**: `User` table in Postgres is updated with `telegram_chat_id`.

---

## 4. Safety & SOS Architecture: "The Guardian"
The Telegram bot is the primary driver for the **RouteMaster Safety Engine**.

- **SOS Trigger**: Commands like `/sos` or phrases like "I am in danger" trigger immediate broadcast.
- **Real-time Telemetry**: The bot requests a "Live Location" share, which is then piped to:
  - Emergency Contacts (SMS/WhatsApp).
  - Local Authorities (via API integration).
  - The RouteMaster Global Emergency Map.
- **Anomaly Detection**: If the user's location remains static in a high-risk zone for >15 mins, the backend sends a "Check-in" prompt to the bot. If unanswered, an alert is escalated.

---

## 5. Strategic "10X" Roadmap

### A. Shadow Sync (Web ↔ Bot Parity)
- **Concept**: Bi-directional state mirroring.
- **Mechanism**: When a user selects a train on the web but doesn't book, the bot sends a message 10 minutes later: *"I see you liked the Shatabdi Express to Delhi. Want to book it now from here?"*

### B. Predictive Delay Routing (PDR)
- **Concept**: Proactive alternative routing.
- **Mechanism**: If a train is delayed >2 hours, the bot automatically calculates a **Cab + Bus** alternative and presents a "Swap My Trip" button.

### C. Community Fare-Lock
- **Concept**: Social price protection in Group Chats.
- **Mechanism**: In a Telegram Group, multiple users can "Vote" to lock a group fare. The backend uses multi-signature logic to hold the price for 24 hours.

---

## 6. Deployment & Operations

### Modes of Operation
- **Development**: Polling mode (`polling.py`) for easy local debugging without public URLs.
- **Production**: Webhook mode (`webhook.py`) deployed via Gunicorn/Uvicorn on Railway/VPS.

### Resilience Patterns
- **Circuit Breakers**: If the main Routing Engine is down, the bot enters "Static/Cached Mode" providing the last known schedule.
- **Rate Limiting**: Prevents API abuse via Telegram-side sliding window limits.
- **Logging**: All interactions are logged to **Loki** for real-time observability.

---

## 7. Telegram Mini App (TMA) Integration
The Mini App provides a rich, app-like experience within Telegram, replacing complex command-line flows with a modern GUI.

### 🏗️ TMA Architecture
- **Tech Stack**: React 18, Vite, Tailwind CSS, TanStack Query.
- **Authentication**: Uses `initData` verification on the backend to exchange for a secure JWT.
- **Navigation**: Synchronized with Telegram's native `BackButton` and `MainButton`.
- **Theme Sync**: Automatically adjusts colors to match the user's Telegram theme (Light/Dark).
- **Fullscreen Mode**: Activated on home page for an immersive "RouteMaster" experience.

### 📱 Key TMA Features
| Module | TMA Functionality |
| :--- | :--- |
| **Unified Search** | Dynamic station lookup and date selection with neural feedback. |
| **Entity Entry (Booking)** | Streamlined passenger management and instant booking synthesis. |
| **SafeGuard Node (SOS)** | One-tap distress signal with live telemetry broadcast. |
| **Live Vector (Tracking)** | Visual journey progress with station-by-station telemetry. |

---
*Created by RouteMaster Core Engineering Team | 2026*
