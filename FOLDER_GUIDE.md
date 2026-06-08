# RouteMaster Project Folder Guide (Optimized Structure)

This guide documents the modularized directory structure of the RouteMaster backend. All services, APIs, and core logic have been organized into logical namespaces to reduce root-level sprawl and improve maintainability.

## 📁 /backend
The main FastAPI backend application.

### 📁 /api
REST API endpoints organized by domain.
- **admin/**: Reconciliation, refunds, and administrative tools.
- **auth/**: Authentication, user management, and credential vault.
- **bookings/**: PNR status, reservation routes, and booking lifecycle.
- **communication/**: Chatbot (WS/REST), Telegram bot, and interactive responses.
- **intelligence/**: Revenue management, redistribution, and knowledge graph APIs.
- **payments/**: Payment gateways (Razorpay), webhooks, and bank integrations.
- **safety/**: SOS, Sathi safety engine, and voice triage.
- **search/**: Integrated and unified search, route discovery, and station info.
- **system/**: Health checks, task management, and system integration.
- **v2/ /v3/**: Versioned API iterations.

### 📁 /core
The high-performance routing engine and system infrastructure.
- **data_utils/**: Data structures, segment details, and shared utilities.
- **engines/**: Unified routing engines (RAPTOR/Turbo), state machines, and planners.
- **infrastructure/**: Redis, metrics, monitoring, scaling, and resource management.
- **integration/**: FCM, microservice clients, and third-party providers.
- **resilience/**: Circuit breakers, retry logic, rate limiting, and WAF.
- **routing/**: Lower-level routing graph and algorithm implementations.
- **ml_models/**: Serialized machine learning models.

### 📁 /services
Business logic services used by the API and Core.
- **analytics/**: Telemetry, behavior tracking, and performance monitoring.
- **auth/**: Identity services, KYC, and session management.
- **booking/**: High-level booking orchestration and verification.
- **cache/**: Multi-layer caching and pre-warming services.
- **communication/**: Alerts, notifications, and websocket management.
- **data/**: Syncing, snapshots, and knowledge graph persistence.
- **finance/**: Payments, refunds, settlements, and commissions.
- **intelligence/**: NLP, feedback loops, and interactive bot logic.
- **inventory/**: Advanced seat allocation and inventory management.
- **ml/**: Demand forecasting, delay prediction, and yield engines.
- **planning/**: Travel planning API and journey reconstruction.
- **pricing/**: Unified pricing orchestrator and dynamic yield engines.
- **safety/**: SOS alerts, Sathi integration, and emergency dispatch.
- **search/**: Hybrid search and pre-warming orchestration.
- **telegram/**: Telegram bot dispatcher and conversation engine.

## 📁 /tools
Scripts for development, diagnostics, and deployment.
- **diagnostics/**: Redis testing, system audits, and performance profiling.

## 📁 /doc
Documentation and archival materials.
- **archive/**: Deprecated files and historical logs.
- **design/**: UI/UX mockups and design systems.

---
*Note: This structure was established on 2026-05-04 to address service sprawl and improve architectural clarity.*
