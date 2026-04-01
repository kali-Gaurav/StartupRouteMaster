# Operation Resilient Pulse: Production Hardening Roadmap

## 1. Architectural Gaps & Root Cause Analysis

| Component | Status | Identified Vulnerability | Root Cause |
| :--- | :--- | :--- | :--- |
| **Search Engine** | ⚠️ DEGRADED | 5-10 minute "Cold Boot" lag on VPS restarts. | Built graphs are never proactively saved to Disk/R2; only on explicit triggers. |
| **Auth System** | ❌ UNSTABLE | Random 500 errors during concurrent searches. | `SharedAuthManager` lacks retry logic for SQLite/PG locks during write-heavy search build. |
| **Middleware** | ⚠️ RISKY | System crashes due to OOM before shedding begins. | Load-shedding threshold set to 99% RAM; VPS OS (Linux) kills process at 95-98%. |
| **Data Sync** | ⚠️ PARTIAL | Potential state drift between Local and R2. | R2 sync is linear and can block event-loop startup if R2 latency is high. |

---

## 2. Implementation Strategy (GSD Workflows)

### Phase 1: Persistence & Boot Speed (G1, G2)
- **Action**: Modify `backend/core/route_engine/builder.py` to auto-trigger snapshot saving.
- **Action**: Decouple `R2SyncService` from the main startup sequence into a "Ghost Hydration" task.

### Phase 2: Transaction Resilience (G3)
- **Action**: Audit `SharedAuthManager` and `PaymentService`. 
- **Action**: Apply `with_db_retry` decorator to all methods containing `db.commit()`.

### Phase 3: Sentinel Security & Shedding (G4)
- **Action**: Refactor `NexusIOGate` to shed load at 90% RAM and 85% CPU.
- **Action**: Implement "Graceful Degradation" headers for the frontend to show "High Load" UI.

---

## 3. Verification Protocol

- [ ] **Search Verification**: Clear snapshots, start server, verify snapshot appears in `database/snapshots/` within 5 mins.
- [ ] **Auth Stress Test**: Run 50 concurrent search requests and 5 concurrent login requests.
- [ ] **OOM Simulation**: Use `nexus_chaos.apply_trap("ram_exhaustion")` to verify 503 response.
- [ ] **R2 Integrity**: Verify `transit_graph.db` on R2 matches local hash after change.

---

## 4. VPS Readiness Checklist (Hostinger KVM 2 / Railway)

- [x] **RAM Profile**: < 1.2GB Idle (Current: ~800MB)
- [x] **Storage Profile**: < 5GB Total (Current: ~2GB)
- [ ] **Concurrency**: Support 50 RPS (Search) + 5 RPS (Write)
- [ ] **Uptime**: 99.9% resilience against Redis/Supabase outages.
