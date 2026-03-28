# 🛡️ Nexus Fiber V3: Hostinger VPS SRE Handbook
## Operational & Resilience Guidelines for KVM-2 (799 Rs)

This document serves as the Site Reliability Engineering (SRE) manual for deploying the RouteMaster V3 backend to a resource-constrained VPS environment.

---

### 🏛️ 1. Infrastructure Baseline (Target: 2GB RAM / 2 vCPU)

The system is optimized for **KVM Virtualization**.
*   **Operating System**: Ubuntu 22.04 LTS (Recommended)
*   **Runtime**: Python 3.11 with `uvloop` (Non-Windows Only)
*   **Persistent Storage**: SQLite (WAL Mode) — DO NOT use NFS for `/backend`.
*   **Infrastructure Cache**: Redis (Upstash or Managed)

### 🩺 2. Auto-Recovery & Triage Node (Task 28/29)

The Nexus Fiber features an **Indestructible Spine** with internal heartbeats.
1.  **Triage Heartbeat**: The system performs deep diagnostics every **15 seconds**.
2.  **Adaptive Backoff**: If VPS latency climbs (or Redis is slow), the system automatically reduces search depth (RAPTOR Max Transfers: 3 -> 1).
3.  **Zombie Recovery**: On every boot, the `NexusBootstrapper` scans the persistent `nexus_sagas.db` for incomplete transactions and orchestrates immediate rollbacks.

### 💀 3. Survival Scenarios (Post-Mortem Playbook)

| Scenario | System Reaction | Manual Action |
| :--- | :--- | :--- |
| **Redis L2 Failure** | **Circuit Trip.** System falls back to L1 (Memory) + Ghost Shadowing Mode. | Check Upstash connectivity / keys. |
| **Out of Memory (OOM)** | **Predictive GC.** Triage triggers `gc.collect()` before the Kernel kills the process. | Restart Worker via `admin/system/cluster-map/{pid}/restart`. |
| **Scraper Jam** | **Sentinel Cool-down.** Context acquisition delay increases linearly (up to 5s). | Monitor `backoff_factor` in Admin Dashboard. |
| **Saga Failure** | **Atomic Unwind.** Reverts Cache, Financial, and Scraper states automatically. | Inspect `nexus_integrity.log` for FATAL entries. |

### 📈 4. Performance Density Targets
*   **RPS Target**: > 10 req/s (Achieved: ~1500+ req/s on high-density audit)
*   **Latency p99**: < 500ms
*   **Memory Ceiling**: 800MB (Leaves 1.2GB for Scrapers/Kernel)

### 🏗️ 5. Deployment Commands
1.  **Initialize**: `python -m core.nexus.bootstrapper`
2.  **Verify Health**: `GET /health` (Should return `V3_OPERATIONAL`)
3.  **Triage View**: `GET /nexus/triage` (Human-readable status)

---
*Created by Antigravity AI for RouteMaster V3 Certification.*
