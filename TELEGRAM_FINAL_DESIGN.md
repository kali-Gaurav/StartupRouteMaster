# RouteMaster Telegram Bot: Final Professional Architecture

## 1. Core Workflow (The Lifecycle)
Every interaction follows a strictly defined, high-performance pipeline:
1.  **Ingress**: Webhook receives JSON -> `Bot.process_update`.
2.  **Context Recovery**: `UserSessionManager` pulls current state (Idle, Searching, Booking, etc.) from Redis.
3.  **Routing (Priority Order)**:
    *   **Priority 1: Flow Persistence**: If user is in a multi-step "Flow" (e.g., Profile Update), `FlowHandler` intercepting input.
    *   **Priority 2: Intent Classification**: NLP-based `IntentClassifier` detects command (e.g., "Find trains").
    *   **Priority 3: Callback Routing**: Handles button clicks.
4.  **Execution**: Logic-specific Handler (Search, PNR, SOS) executes task via `BookingService` or `UserService`.
5.  **Egress**: `TelegramDispatcher` sends formatted HTML/Markdown with interactive keyboards.

## 2. Key Components

### 🔄 Multi-Turn Conversation Engine (`FlowHandler`)
Allows for complex, multi-step interactions without the user needing to remember commands.
*   **Linear Flows**: Registration, Booking, Profile Update.
*   **Validation**: Every step has built-in regex or logic validation.
*   **State Recovery**: If the user leaves and returns, they are exactly where they left off.

### 🔔 Asynchronous Notification Manager
A decoupled system for background alerts:
*   **Real-time PNR Tracking**: Background workers detect status changes and push alerts to Telegram.
*   **SOS Propagation**: Critical alerts are broadcast to emergency contacts and the web dashboard.
*   **Payment Webhooks**: Confirms payments and sends tickets instantly via Telegram.

### 🔒 Unified Identity & Vault
*   **Cross-Platform Sync**: Users on the website can see their Telegram history.
*   **Vaulted PNRs**: Sensitive travel data is stored in a secure cryptographic vault, accessible via Telegram only to the owner.

## 3. Advanced Features (The "10X" System)
*   **AI Smart Reply**: Fallback system that uses NLP to suggest corrections if it doesn't understand a command.
*   **Dynamic UI**: Keyboards change dynamically based on the train's real-time status (e.g., "Track" button appears when the train is active).
*   **Localized Experience**: Multi-language support (Hindi/English) detected from Telegram settings.

## 4. Stability & Testing
*   **Redis Backing**: 100% persistent state; server restarts don't lose user progress.
*   **Circuit Breakers**: If the external Railway API is slow, the bot enters "Dev/Degraded Mode" to stay responsive.
*   **Audit Logging**: Every message and action is logged for security and optimization.
