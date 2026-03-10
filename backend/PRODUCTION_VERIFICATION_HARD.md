# RouteMaster V2 Production Readiness - EPIC HARD VERIFICATION

## Epic 1: Core System & Network Resilience
### Task 1.1: Backend/Frontend Online-Offline State Sync
- [ ] Subtask 1.1.1: [HARD] Simulated 50% packet loss during state transition.
- [ ] Subtask 1.1.2: [HARD] Verify 'Background Polling' recovery when app is minimized.
- [ ] Subtask 1.1.3: [HARD] Frontend 'Offline' banner persistence across page reloads.
- [ ] Subtask 1.1.4: [HARD] Atomic update of LocalStorage when backend returns 503.
- [ ] Subtask 1.1.5: [HARD] Latency-induced 'Slow Connection' UI trigger (RTT > 2000ms).

### Task 1.2: API Client Retry Logic & Jitter
- [ ] Subtask 1.2.1: [HARD] Verify 3-retry sequence with exponential backoff.
- [ ] Subtask 1.2.2: [HARD] Confirm 'Random Jitter' to prevent thundering herd.
- [ ] Subtask 1.2.3: [HARD] Test retry behavior on 502/504 vs 400 (No retry on 400).
- [ ] Subtask 1.2.4: [HARD] WebSocket failover when primary API is throttled.

### Task 1.3: Database & Cache Stress (500+ CCU)
- [ ] Subtask 1.3.1: [HARD] 1000 concurrent SQL queries via connection pool.
- [ ] Subtask 1.3.2: [HARD] Redis memory eviction policy consistency.
- [ ] Subtask 1.3.3: [HARD] Deadlock detection under heavy write load (SOS triggers).

### Task 1.4: Rate Limiting & Shielding
- [ ] Subtask 1.4.1: [HARD] IP-based blocking bypass attempts (X-Forwarded-For spoofing).
- [ ] Subtask 1.4.2: [HARD] User-based budget tracking (Token bucket).
- [ ] Subtask 1.4.3: [HARD] Global 'Panic Switch' (Kill all non-essential traffic).

## Epic 2: Authentication & Session Integrity
### Task 2.1: JWT Rotation & RTR
- [ ] Subtask 2.1.1: [HARD] Token theft simulation (old refresh token use).
- [ ] Subtask 2.1.2: [HARD] Refresh token revocation propagation (latency < 1s).
- [ ] Subtask 2.1.3: [HARD] Auto-logout when Supabase session heartbeats fail.

### Task 2.2: RBAC & Data Isolation
- [ ] Subtask 2.2.1: [HARD] Accessing /admin/ via 'user' token - strict 403.
- [ ] Subtask 2.2.2: [HARD] SQL Row-Level Security bypass attempts.
- [ ] Subtask 2.2.3: [HARD] PII Masking in Debug logs for non-PII roles.

## Epic 3: Route Engine (Task 3)
### Task 3.1: RAPTOR Loops & MCT
- [ ] Subtask 3.1.1: [HARD] Infinite transfer loop detection (A -> B -> A).
- [ ] Subtask 3.1.2: [HARD] Multi-day masking for 48h+ journeys.
- [ ] Subtask 3.1.3: [HARD] Impossible Transfer rejection (Arrival 10:00 -> Departure 10:01).

## Epic 4: Live Data & Tracking (Task 4)
### Task 4.1: Concurrency & Stale Data
- [ ] Subtask 4.1.1: [HARD] 10,000 live updates/sec processing latency.
- [ ] Subtask 4.1.2: [HARD] Interpolation accuracy when GPS is missing for 5 stations.
- [ ] Subtask 4.1.3: [HARD] Crossover 12AM handling for late-night trains.
