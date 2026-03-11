# ⚙️ TASK 1: ULTRA-TURBO DIRECT ENGINE (EXECUTION PLAN)

Following a deep audit of the current routing code, here are the 15 highly unique, hardcore subtasks required to finalize the Ultra-Turbo Tier 0 engine. These focus on extreme performance, memory safety, and deterministic yields.

### The 15 Deep Subtasks:
*   **[x] Subtask 1.1: Raw Pool Implementation:** (Done) Establish `aiosqlite` pool in `session.py`.
*   **[x] Subtask 1.2: Statement Cache Optimization:** (Done) Use static SQL templates with `json_each` parameter binding.
*   **[x] Subtask 1.3: Asynchronous Generator Streaming:** (Done) Refactor to `yield` with `fetchmany(50)` for constant memory.
*   **[x] Subtask 1.4: Cross-Reference Indexing:** (Done) Force `idx_stop_times_trip_id` on join via `INDEXED BY`.
*   **[x] Subtask 1.5: Atomic Alias Resolution:** (Done) Combine alias and cluster resolution into a single CTE query.
*   **[x] Subtask 1.6: Fare Scalar Normalization:** (Done) Use nonlinear piecewise SQL logic for realistic pricing.
*   **[x] Subtask 1.7: Pre-emptive Cancellation Pruning:** (Done) Use Python-side set lookups for O(1) cancellation pruning.
*   **[ ] Subtask 1.8: Memory-Bound Object Pooling:** Implement a simple `FastSegment` object pool to reuse objects and reduce GC (Garbage Collection) churn.
*   **[ ] Subtask 1.9: Bitwise Day-of-Run Consolidation:** Migrate the 7-column day check to a single `(1 << weekday) & run_mask` bitwise operation for 15% faster filtering.
*   **[ ] Subtask 1.10: Locality-Aware Sorting:** Push the `duration` sort into the SQL layer using `ORDER BY duration` to avoid Python-side sorting overhead.
*   **[ ] Subtask 1.11: Early-Exit Yield Trigger:** Implement a "Sufficient Yield" break; if 20 high-quality direct routes are found, stop the scanner to save CPU.
*   **[ ] Subtask 1.12: Null-Result Diagnostic Hook:** If yield is 0, capture the exact failing constraint (e.g., "no trains run on Wed") for user feedback.
*   **[ ] Subtask 1.13: Multi-Day Wrap Logic:** Handle trains departing at 23:50 and arriving next day correctly within the raw SQL duration math.
*   **[ ] Subtask 1.14: Connection Leak Guard:** Implement an `asyncio.Shield` protected cleanup handler for the raw connection pool.
*   **[ ] Subtask 1.15: Task 1 Hardcore Verification:** Create a test suite that asserts < 2ms latency for hub-to-hub and < 5MB RAM growth per 1000 routes.

---
**Status:** Subtask 1.1 is complete. Moving to **Subtask 1.2: Statement Cache Optimization**.
