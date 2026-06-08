# Epic 6: Multi-tier Cache Warmup Strategies

This epic focuses on making the cache "proactive" rather than "reactive." By implementing intelligent warmup strategies, we ensure that high-value data is already in RAM or Redis before it is ever requested, reducing p99 latency to sub-millisecond levels.

## The 15 High-Priority Subtasks

1. **Subtask 6.1: Event Sourcing for Warmup:** Implement a "Cache Miss Logger" that records missing keys to a queue, allowing the system to learn which routes are trending and need pre-warming.
2. **Subtask 6.2: Static Pre-caching (Top 100):** Build a boot-time worker that pulls the top 100 most frequent station-to-station pairs from the DB and pre-populates the cache.
3. **Subtask 6.3: Hierarchical Warmup Sequence:** Design a hydration flow where data moves from L3 (Disk Snapshots) -> L2 (Redis) -> L1 (Local RAM) in a tiered priority.
4. **Subtask 6.4: LZ4 Compression for Warmup:** Use ultra-fast LZ4 compression for large route payloads during the L2 injection phase to save bandwidth and memory.
5. **Subtask 6.5: Stale-While-Revalidate JIT:** Modify the cache getter to serve expired data instantly while triggering an asynchronous JIT refresh in the background.
6. **Subtask 6.6: Distributed Lock Coordination:** Use Redis-based locks to ensure only one pod/worker performs a heavy warmup for a specific route at a time.
7. **Subtask 6.7: Delta-Update Invalidation:** Instead of flushing an entire route, implement a "patch" mechanism that updates only affected segments when a train delay occurs.
8. **Subtask 6.8: User-Specific Predictive Caching:** Hook into the Auth flow to pre-warm a user's recently viewed or "favorite" routes into L1 cache immediately after login.
9. **Subtask 6.9: Cache Repair Worker:** An autonomous background process that scans for "Zombie" (partial or malformed) cache entries and rebuilds them.
10. **Subtask 6.10: Memory-Aware LRU Eviction:** Replace simple count-based eviction with a byte-size aware policy to prevent RAM exhaustion from few massive objects.
11. **Subtask 6.12: Load-Aware Warmup Throttling:** Integrate with `ShadowWarmer` to pause background warmup cycles if system CPU or Memory load exceeds 75%.
12. **Subtask 6.13: Cross-Worker L1 Mirroring:** Use Redis Pub/Sub to broadcast critical L1 cache updates to all other Uvicorn workers for instant global synchronization.
13. **Subtask 6.14: Cache Integrity Fingerprinting:** Append a CRC32 or MD5 hash to cache values to ensure that warmed data isn't corrupted during transit or storage.
14. **Subtask 6.11: Bulk Pipeline Insertion:** Implement high-speed Redis pipelining for the initial boot-time warmup to handle 1000+ keys in one round-trip.
15. **Subtask 6.15: Warmup Telemetry:** Add `cache_warmup_hits` and `prewarm_latency` metrics to the `jit_metrics` Prometheus report.

---

### Implementation Strategy
We will begin by upgrading the `MultiLayerCache` to support these tiered warmup sequences and then implement the **Top 100 Static Pre-cacher**.
