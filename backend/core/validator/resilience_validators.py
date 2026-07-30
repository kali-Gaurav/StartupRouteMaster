"""
Resilience / Chaos-Failure Recovery Validators (RT-171 — RT-200)

Each method implements a single RT check. Methods are defensive and accept
simple primitives / small structs so they are easy to unit-test and to mock
in integration tests.
"""
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ResilienceValidator:
    """Validators for chaos, failure and recovery scenarios."""

    def __init__(self):
        # Tunable thresholds used by the checks
        self.acceptable_partial_graph_fraction = 0.75
        self.latency_spike_threshold_ms = 1000
        self.queue_overflow_threshold = 10000

    def validate_db_unavailable_during_query(self, db_available: bool, fallback_used: bool) -> bool:
        """RT-171: DB unavailable during query -> ensure fallback/circuit worked."""
        if db_available:
            return True
        # If DB is unavailable there must be a fallback
        return bool(fallback_used)

    def validate_cache_unavailable_fallback(self, cache_available: bool, fallback_used: bool) -> bool:
        """RT-172: Cache unavailable -> verify graceful fallback to DB or other store."""
        if cache_available:
            return True
        return bool(fallback_used)

    def validate_partial_graph_load(self, loaded_fraction: float) -> bool:
        """RT-173: Partial graph load should be >= acceptable threshold."""
        return loaded_fraction >= self.acceptable_partial_graph_fraction

    def validate_corrupted_realtime_feed(self, feed_integrity_ok: bool, recovery_applied: bool) -> bool:
        """RT-174: Corrupted realtime feed must trigger recovery or fail-safe."""
        if feed_integrity_ok:
            return True
        return bool(recovery_applied)

    def validate_network_latency_spikes(self, recent_latencies_ms: List[int], spike_threshold_ms: Optional[int] = None) -> bool:
        """RT-175: Detect large latency spikes in recent samples."""
        if not recent_latencies_ms:
            return True
        thresh = spike_threshold_ms or self.latency_spike_threshold_ms
        return all(l <= thresh for l in recent_latencies_ms)

    def validate_service_restart_mid_query(self, restart_detected: bool, retry_successful: bool) -> bool:
        """RT-176: Service restart during query must be retried successfully or fail gracefully."""
        if not restart_detected:
            return True
        return bool(retry_successful)

    def validate_node_crash_recovery(self, node_down: bool, recovered: bool) -> bool:
        """RT-177: Node crash should recover (auto-restart/replace) within SLA."""
        if not node_down:
            return True
        return bool(recovered)

    def validate_retry_logic_correctness(self, retry_policy: Dict[str, Any], observed_retries: int) -> bool:
        """RT-178: Retry logic should respect policy caps and backoff."""
        max_retries = int(retry_policy.get('max_retries', 3))
        return observed_retries <= max_retries

    def validate_circuit_breaker_activation(self, cb_state: str, failure_rate: float, cb_threshold: float = 0.5) -> bool:
        """RT-179: Circuit breaker must activate when failure rate exceeds threshold."""
        if failure_rate >= cb_threshold:
            return cb_state in ('open', 'half-open')
        return cb_state == 'closed'

    def validate_graceful_degradation(self, degraded_mode: bool, partial_results_allowed: bool) -> bool:
        """RT-180: System should enter graceful degradation and still return safe results."""
        if not degraded_mode:
            return True
        return bool(partial_results_allowed)

    def validate_memory_exhaustion_handling(self, memory_percent: float, oom_handled: bool) -> bool:
        """RT-181: Memory exhaustion should trigger OOM handlers / eviction."""
        if memory_percent < 95.0:
            return True
        return bool(oom_handled)

    def validate_disk_full_scenario(self, free_bytes: int, cleanup_triggered: bool) -> bool:
        """RT-182: Disk full must trigger cleanup or graceful failure."""
        if free_bytes > 1024 * 1024 * 100:  # >100MB
            return True
        return bool(cleanup_triggered)

    def validate_config_corruption_recovery(self, config_ok: bool, restored_from_backup: bool) -> bool:
        """RT-183: Corrupt config should be detected and restored from backup."""
        if config_ok:
            return True
        return bool(restored_from_backup)

    def validate_dependency_timeout_fallback(self, dependency_timed_out: bool, fallback_invoked: bool) -> bool:
        """RT-184: Timeouts in dependencies must trigger fallback logic."""
        if not dependency_timed_out:
            return True
        return bool(fallback_invoked)

    def validate_rolling_deployment_safety(self, failures_during_rollout: int, rollback_performed: bool) -> bool:
        """RT-185: Rolling deployment should rollback on unacceptable failure rate."""
        if failures_during_rollout == 0:
            return True
        return bool(rollback_performed)

    def validate_backward_compatibility_after_deploy(self, api_breaking_changes: bool, compatibility_tests_passed: bool) -> bool:
        """RT-186: Backward compatibility must be preserved or flagged by tests."""
        if not api_breaking_changes:
            return True
        return bool(compatibility_tests_passed)

    def validate_feature_flag_toggle_safety(self, flag_changes: Dict[str, bool], canary_ok: bool) -> bool:
        """RT-187: Feature-flag toggles must be safe and canary validated."""
        if not flag_changes:
            return True
        return bool(canary_ok)

    def validate_queue_overflow_handling(self, queue_depth: int, discard_policy_applied: bool) -> bool:
        """RT-188: Queue overflow must trigger backpressure or discard policy."""
        if queue_depth < self.queue_overflow_threshold:
            return True
        return bool(discard_policy_applied)

    def validate_deadlock_prevention(self, deadlock_detected: bool, mitigation_applied: bool) -> bool:
        """RT-189: Deadlocks must be detected and mitigated."""
        if not deadlock_detected:
            return True
        return bool(mitigation_applied)

    def validate_partial_result_fallback(self, partial_result_served: bool, fallback_valid: bool) -> bool:
        """RT-190: Partial results must be validated before serving."""
        if not partial_result_served:
            return True
        return bool(fallback_valid)

    def validate_monitoring_alert_trigger(self, expected_alerts: List[str], alerts_fired: List[str]) -> bool:
        """RT-191: Critical alerts must be fired for severe incidents."""
        return set(expected_alerts).issubset(set(alerts_fired))

    def validate_log_integrity_during_crash(self, logs_intact: bool, missing_entries: int) -> bool:
        """RT-192: Logs should survive crashes; missing entries should be minimal."""
        if logs_intact:
            return True
        return missing_entries <= 5

    def validate_cache_rebuild_after_failure(self, rebuild_started: bool, rebuild_successful: bool) -> bool:
        """RT-193: Cache rebuild must start and complete after failure."""
        if not rebuild_started:
            return False
        return bool(rebuild_successful)

    def validate_duplicate_message_handling(self, deduped: bool, duplicates_seen: int) -> bool:
        """RT-194: Duplicate messages must be deduplicated or idempotent."""
        if duplicates_seen == 0:
            return True
        return bool(deduped)

    def validate_idempotent_retry_correctness(self, idempotent: bool, side_effects_observed: bool) -> bool:
        """RT-195: Retries to idempotent endpoints must not cause side-effects."""
        if idempotent:
            return not bool(side_effects_observed)
        return True

    def validate_distributed_lock_failure(self, lock_acquired: bool, failover_ok: bool) -> bool:
        """RT-196: Distributed lock failures should trigger failover safely."""
        if lock_acquired:
            return True
        return bool(failover_ok)

    def validate_leader_election_recovery(self, leader_stable: bool, election_attempts: int) -> bool:
        """RT-197: Leader election should converge quickly and produce a stable leader."""
        if leader_stable:
            return True
        return election_attempts <= 3

    def validate_event_replay_correctness(self, replayed: int, matched: int) -> bool:
        """RT-198: Replayed events should match original events count within tolerance."""
        if replayed == 0:
            return True
        return matched == replayed

    def validate_transaction_rollback_safety(self, rollback_successful: bool) -> bool:
        """RT-199: Failed transactions must rollback fully."""
        return bool(rollback_successful)

    def validate_disaster_recovery_restore(self, backup_restored: bool, consistency_ok: bool) -> bool:
        """RT-200: Disaster recovery restore must complete and be consistent."""
        return bool(backup_restored and consistency_ok)
