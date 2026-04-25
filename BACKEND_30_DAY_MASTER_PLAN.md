# 🧠 Backend Master Plan: 30-Day Industrial Build-Out

This document outlines the focused, engineering-heavy roadmap to complete the **RouteMaster Backend System**. We are building a high-concurrency, resilient routing spine that rivals top-tier transit platforms while integrating unique safety and social empowerment features.

---

## 🏗️ Phase 1: Foundation & Data Ingestion (Days 1-7)
**Lead Agents**: Vanguard (Architecture), Guandao (Ingestion)

*   **Day 1: Connection Resiliency & Cache Layer. [COMPLETED]** Fixed Redis/Upstash authentication failures. Implemented a robust `ResilientRedisClient` with circuit breakers and fallback to L1 Memory Slabs. 3-Tier Routing Model (Basic, Pro, Elite) integrated into V3 API.
*   **Day 2: Database Schema Hardening & Sentinel S1 Rigor. [COMPLETED]** 
    *   *Rigor*: Finalized SQLAlchemy 2.0 migration with `AuditMixins` and `TimestampMixins`.
    *   *Rigor*: Implemented `IdentityS1.5` with Behavioral Entropy and Shadow Banning.
    *   *Rigor*: Deployed `Integrity 2.0` with Replay-Proof HMAC signing (Nonce + TTL).
    *   *Rigor*: Architected Partitioning Strategy (Range/Hash) for 1M+ scale.
*   **Day 3: Resilient Scraper Network.** Update `Guandao's` scraper logic to handle dynamic NTES/IRCTC changes. Implement proxy rotation and headless browser pooling in `scraper_sentinel.py`.
*   **Day 4: ETL Pipeline 2.0.** Optimize the `TurboETL` service to transform raw railway data into compressed binary graphs (`.pkl` and `.db`) in under 5 minutes.
*   **Day 5: Unified API Gateway.** Refine the `api/v3` router. Implement global rate limiting, CORS hardening, and a standard `ResponseSchema` across all endpoints.
*   **Day 6: Identity & Auth Service.** Secure the Supabase bridge. Implement zero-knowledge credential storage for users' IRCTC logins using AES-256 in the `CredentialVault`.
*   **Day 7: First Sprint Smoke Test.** Validate that `Guandao` can ingest 10,000 train schedules and `Vanguard` can serve them via a basic search endpoint.

---

## ⚡ Phase 2: Routing Core & Performance (Days 8-15)
**Lead Agents**: Ariadne (Graph Theory), Forge (Engineering)

*   **Day 8: RAPTOR v2 Implementation.** Optimize the Round-Based Public Transit Routing algorithm. Implement multi-modal transfer logic (Train + Walk + Auto-Rickshaw).
*   **Day 9: Turbo Cluster Pruning.** Implement `Forge's` hub-scoring algorithm to prune the search graph, reducing exploration nodes by 40% without losing optimality.
*   **Day 10: Search Budget Governor.** Implement the `SearchBudget` controller. Dynamically adjust `max_transfers` and `max_nodes` based on real-time VPS CPU/RAM pressure.
*   **Day 11: Real-time Telemetry Sync.** `Chronos` integration: Sync real-time train positions from the ingestion layer into the routing frontier for live arrival/departure weights.
*   **Day 12: Advanced Seat Availability Service.** Build a predictive availability model that uses historical data to estimate "Chance of Confirmation" for waitlisted tickets.
*   **Day 13: JIT Graph Loaders.** Implement lazy loading for transit graph segments. Only load the required regional nodes into memory during a search.
*   **Day 14: Latency Audit.** Profile the search pipeline. Target: Direct routes < 50ms, 2-Transfer routes < 300ms.
*   **Day 15: Deep Benchmarking.** Run 1000 concurrent searches on a 2vCPU VPS and verify the `Governor's` throttling accuracy.

---

## 🛡️ Phase 3: Safety, Finance & Social Logic (Days 16-23)
**Lead Agents**: Guardian (Safety), Settlement (Finance)

*   **Day 16: Women’s Safety Engine.** Implement the `SafetyScorer`. Weigh search results by platform visibility, station help-hub proximity, and historical safety metrics.
*   **Day 17: SOS & Dispatch Pipeline.** Build the `Aegis` SOS service. Implement sub-second alerts, real-time location streaming, and automated escalation to local responder nodes.
*   **Day 18: Project Sentinel Ledger.** Implement the double-entry `FinancialLedger` with cryptographic hash chains to ensure 100% audit integrity for all payments.
*   **Day 19: IRCTC Smart Redirect.** Build the logic to generate IRCTC deep links. Map the station codes, train numbers, and dates to the exact booking page landing URL.
*   **Day 20: Manpower & Agent Service.** Build the backend for the "Social Empowerment" goal. Implement agent registration, task assignment, and payout management for ground-level helpers.
*   **Day 21: Payment VPA Rotation.** Finalize the `MerchantVPAService`. Implement daily limit tracking and automated rotation to prevent account freezing.
*   **Day 22: Settlement & Refund Sagas.** Implement the `SagaPattern` for multi-step financial transactions to ensure no "limbo" funds during failures.
*   **Day 23: Audit & Compliance.** Implement `BailiffAgent` logic to auto-audit commissions and flag suspicious arbitrage or fraud.

---

## 🚀 Phase 4: Reliability, Scalability & VPS Hardening (Days 24-30)
**Lead Agents**: Vanguard (Architecture), Aegis (QA)

*   **Day 24: Background Worker Optimization.** Tune `Celery` and `Redis` for background tasks (ETL, Alerts, PNR Monitoring). Implement priority queues for SOS alerts.
*   **Day 25: VPS Hardening.** Implement CPU affinity pinning and swap-file optimization for low-RAM environments. Configure `Systemd` watchdogs for all microservices.
*   **Day 26: Chaos Engineering.** `Aegis` executes the "Blackout Test": Force-kill database/redis/API nodes and verify the system's `RecoveryService` restores state.
*   **Day 27: Telemetry & Monitoring.** Finalize the Prometheus/Grafana export layer. Implement custom metrics for "Search Yield" and "Safety Dispatch Latency".
*   **Day 28: API Versioning & Docs.** Lock the V3 API. Generate final Swagger/Redoc documentation. Implement automated client-side SDK generation.
*   **Day 29: Final Verification.** Run the `system_validator.py` across all 34 backend modules. Ensure 100% test coverage for safety and financial logic.
*   **Day 30: 🌍 Production Rollout.** Deploy the final Docker images. Execute the global switch to the V3 Spine.

---

## 💡 The "Build Using Agents" Method
To execute this plan, the developer (You) will use the `.md` agent profiles in `.github/agents/`:
1.  **Read the Agent Profile** to understand the specific skills required for the day's task.
2.  **Invoke the Agent** by asking it to execute a specific module build-out.
3.  **Validate** using `Aegis` protocols after each implementation.

This ensures the backend is built with professional architectural standards, not just scattered scripts.
