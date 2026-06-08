# Epic 7: Smart Throttle & Degraded Mode JIT

This epic provides the "Survival Instincts" for RouteMaster V2. It ensures that under extreme CPU, Memory, or Database stress, the system doesn't crash but instead intelligently scales down features to maintain core availability.

## The 15 High-Priority Subtasks

1. **Subtask 7.1: Tiered Degradation State Machine:** Define 4 states: `HEALTHY`, `DEGRADED_ML` (disable ranking), `DEGRADED_GRAPH` (use cached routes only), and `MINIMAL` (health checks only).
2. **Subtask 7.2: Adaptive Load Shedder:** Implement a middleware that drops low-priority requests (e.g., stats, telemetry export) instantly when system load exceeds 85%.
3. **Subtask 7.3: Dynamic JIT Rate Limiting:** Automatically tighten API rate limits during heavy JIT initialization cycles to prevent concurrent request exhaustion.
4. **Subtask 7.4: Fallback Mock Generator:** Create high-speed heuristic fallbacks for search results when the Graph Engine is too slow or under extreme memory pressure.
5. **Subtask 7.5: Circuit Breaker Integration:** Link the Database Circuit Breaker (Subtask 4.4) to the global degradation state.
6. **Subtask 7.6: Client-Facing Degradation Headers:** Append `X-System-State: DEGRADED` to responses so the frontend can show simplified UIs or loading indicators.
7. **Subtask 7.7: Automated Recovery Protocol:** Implement an exponential backoff for "Scaling Up" back to `HEALTHY` mode once metrics stabilize.
8. **Subtask 7.8: Memory-Pressure Kill-Switch:** Instantly terminate all non-essential background workers (ETL, Scrapers) if RAM usage hits a critical 95% threshold.
9. **Subtask 7.9: Predictive Shedding:** Use the `intent_predictor` to drop "Curiosity Requests" (low confidence) while prioritizing "Booking Requests" (high confidence) during load.
10. **Subtask 7.10: Degraded Mode Cache Persistence:** Force the system to serve stale cache entries (ignoring TTL) if the primary data source JIT fails.
11. **Subtask 7.11: JIT Priority Preemption:** Allow a `CRITICAL` state request to "steal" a JIT lock from a lower priority background task.
12. **Subtask 7.12: Telemetry Sampling:** Reduce the rate of telemetry collection by 90% during degraded mode to save CPU/IO.
13. **Subtask 7.13: Global Degradation Flag:** Use Redis to synchronize the degradation state across all Uvicorn workers in a cluster.
14. **Subtask 7.14: Admin Force-Degrade Webhook:** Allow manual triggering of degraded modes for maintenance or emergency stability.
15. **Subtask 7.15: Survival Metrics:** Expose `seconds_in_degraded_mode` and `requests_shed_total` to the Prometheus report.

---

### Implementation Strategy
We will begin by building the **Degradation Manager** and the **Adaptive Load Shedder middleware**.
