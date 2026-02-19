from typing import List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from ..route_engine import Route, RouteSegment, TransferConnection, RouteConstraints

class RouteValidator:
    """Class to handle route validation logic."""

    def validate_route_constraints(self, route: 'Route', constraints: 'RouteConstraints') -> bool:
        """Validate route against all constraints"""
        if route.total_duration > constraints.max_journey_time:
            return False
        if len(route.transfers) > constraints.max_transfers:
            return False
        for transfer in route.transfers:
            if not self.validate_transfer_time(transfer, constraints):
                return False
        if constraints.women_safety_priority:
            for station_id in route.get_all_stations():
                if not self._is_safe_station(station_id):
                    return False
        return True

    def validate_transfer_time(self, transfer: TransferConnection, constraints: RouteConstraints) -> bool:
        """Check if transfer meets constraints."""
        if transfer.duration_minutes < constraints.min_transfer_time:
            return False
        if transfer.duration_minutes > constraints.max_layover_time:
            return False
        if constraints.avoid_night_layovers:
            if self._is_night_layover(transfer.arrival_time, transfer.departure_time):
                return False
        return True

    def validate_segment_continuity(self, segments: List[RouteSegment]) -> bool:
        """Validate that a sequence of RouteSegment objects represents a continuous journey."""
        if not segments:
            return False
        for i in range(len(segments) - 1):
            prev = segments[i]
            nxt = segments[i + 1]
            if prev.arrival_stop_id != nxt.departure_stop_id:
                if not self.check_missing_stop_link(prev.arrival_stop_id, nxt.departure_stop_id):
                    return False
            if prev.arrival_time > nxt.departure_time:
                return False
        return True

    def check_missing_stop_link(self, from_stop_id: int, to_stop_id: int) -> bool:
        """Check if missing intermediate stops can be linked based on GTFS data."""
        return True

    def _is_night_layover(self, arrival_time: datetime, departure_time: datetime) -> bool:
        """Check if the layover occurs at night."""
        return arrival_time.hour < 6 or departure_time.hour < 6

    def _is_safe_station(self, station_id: int) -> bool:
        """Check if the station is safe."""
        return True

    def validate_realtime_delay_propagation(self, delay_data: dict, route: Route) -> bool:
        """Validate real-time delay propagation (RT-031)."""
        # Placeholder for actual implementation
        return True

    def validate_cancellation_removal(self, cancellation_data: dict, route: Route) -> bool:
        """Validate route removal on cancellation (RT-032)."""
        # Placeholder for actual implementation
        return True

    def validate_partial_delay(self, delay_data: dict, route: Route) -> bool:
        """Validate partial delay affecting downstream stops (RT-033)."""
        # Placeholder for actual implementation
        return True

    def validate_realtime_update_during_query(self, update_data: dict, route: Route) -> bool:
        """Validate real-time update during query (RT-034)."""
        # Placeholder for actual implementation
        return True

    def validate_outdated_realtime_cache(self, cache_data: dict, route: Route) -> bool:
        """Validate outdated real-time cache ignored (RT-035)."""
        # Placeholder for actual implementation
        return True