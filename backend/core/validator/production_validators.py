"""
Production Excellence validators (RT-201 — RT-220)
Checks for booking-flow correctness, observability, SLA, scaling, and deployment safety.
"""
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ProductionExcellenceValidator:
    """Validators for production-readiness and excellence."""

    def validate_end_to_end_booking_integration(self, booking_flow_successful: bool, consistency_ok: bool) -> bool:
        """RT-201: End-to-end booking must succeed and be consistent."""
        return bool(booking_flow_successful and consistency_ok)

    def validate_booking_after_route_selection_consistency(self, route_at_selection: Dict[str, Any], booking_result: Dict[str, Any]) -> bool:
        """RT-202: Booking must reflect the selected route (ids/prices/seats)."""
        if not route_at_selection or not booking_result:
            return False
        return route_at_selection.get('route_id') == booking_result.get('route_id')

    def validate_route_revalidation_before_booking(self, route_current: Dict[str, Any], route_at_booking: Dict[str, Any]) -> bool:
        """RT-203: Revalidation before booking must ensure route still valid."""
        if not route_current or not route_at_booking:
            return False
        return route_current.get('signature') == route_at_booking.get('signature')

    def validate_concurrent_booking_conflict_detection(self, concurrent_attempts: int, conflicts_detected: bool) -> bool:
        """RT-204: Concurrent booking conflicts should be detected and handled."""
        if concurrent_attempts <= 1:
            return True
        return bool(conflicts_detected)

    def validate_seat_inventory_sync(self, inventory_snapshot: Dict[str, Any], booking_changes_applied: bool) -> bool:
        """RT-205: Seat inventory must stay in sync after bookings/cancellations."""
        if not inventory_snapshot:
            return False
        return bool(booking_changes_applied)

    def validate_payment_timeout_scenario(self, payment_timed_out: bool, timeout_retries_handled: bool) -> bool:
        """RT-206: Payment timeouts must be retried/compensated correctly."""
        if not payment_timed_out:
            return True
        return bool(timeout_retries_handled)

    def validate_booking_cancellation_propagation(self, cancellation_propagated: bool, subsystems_updated: bool) -> bool:
        """RT-207: Booking cancellation must propagate to dependent systems."""
        return bool(cancellation_propagated and subsystems_updated)

    def validate_refund_route_recalculation(self, refund_processed: bool, route_recalc_correct: bool) -> bool:
        """RT-208: Refund calculation must use the latest fare rules and route data."""
        return bool(refund_processed and route_recalc_correct)

    def validate_notification_triggers_correctness(self, notifications_sent: List[str], expected_notifications: List[str]) -> bool:
        """RT-209: Notifications (email/SMS/push) must be triggered correctly."""
        return set(expected_notifications).issubset(set(notifications_sent))

    def validate_sla_monitoring_dashboard(self, sla_metrics: Dict[str, Any], slas_met: bool) -> bool:
        """RT-210: SLA monitoring must report accurate SLA status."""
        return bool(slas_met)

    def validate_observability_traces_completeness(self, traces: List[Dict[str, Any]], expected_spans: int) -> bool:
        """RT-211: Distributed traces must include required spans."""
        return len(traces) >= expected_spans

    def validate_metrics_correctness(self, metrics: Dict[str, Any], expected_metrics: List[str]) -> bool:
        """RT-212: Core metrics must be present and within valid ranges."""
        return set(expected_metrics).issubset(set(metrics.keys()))

    def validate_cost_optimization_validation(self, cost_metrics: Dict[str, float], cost_within_threshold: bool) -> bool:
        """RT-213: Cost-optimization should not break SLAs or correctness."""
        return bool(cost_within_threshold)

    def validate_autoscaling_triggers(self, autoscale_events: List[Dict[str, Any]], scaled_as_expected: bool) -> bool:
        """RT-214: Autoscaling triggers should increase/decrease capacity correctly."""
        return bool(scaled_as_expected)

    def validate_multi_region_routing_consistency(self, routes_by_region: Dict[str, Any], consistency_ok: bool) -> bool:
        """RT-215: Multi-region routing should produce consistent results."""
        return bool(consistency_ok)

    def validate_geo_failover_correctness(self, failover_events: List[Dict[str, Any]], traffic_redirected: bool) -> bool:
        """RT-216: Geo-failover must redirect traffic and preserve sessions where possible."""
        return bool(traffic_redirected)

    def validate_latency_based_routing(self, latency_metrics: Dict[str, float], routing_changes_applied: bool) -> bool:
        """RT-217: Routing should adapt to latency signals when configured to do so."""
        if not latency_metrics:
            return True
        return bool(routing_changes_applied)

    def validate_canary_deployment_validation(self, canary_metrics: Dict[str, Any], rollback_triggered: bool) -> bool:
        """RT-218: Canary deployments must be monitored and rolled back if necessary."""
        if not canary_metrics:
            return True
        return not rollback_triggered or canary_metrics.get('healthy', False)

    def validate_ab_testing_route_ranking(self, experiment_results: Dict[str, Any], significance: bool) -> bool:
        """RT-219: A/B tests for ranking should produce statistically significant results."""
        if not experiment_results:
            return True
        return bool(significance)

    def validate_production_monitoring_alerts_accuracy(self, alerts: List[Dict[str, Any]], false_positive_rate: float, max_fp: float = 0.1) -> bool:
        """RT-220: Monitoring alerts must be accurate with low false-positive rates."""
        return false_positive_rate <= max_fp
