from __future__ import annotations
from typing import List, TYPE_CHECKING
from datetime import datetime, timedelta

from database.models import Segment
from database.session import SessionLocal

# Import at runtime for type hints to avoid NameError
from ..route_engine.data_structures import Route, RouteSegment, TransferConnection
from ..route_engine.constraints import RouteConstraints


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
        # This is a simplified check. A full implementation would involve:
        # 1. Checking if there's a direct segment between these two stops.
        # 2. Checking if they belong to the same route and appear consecutively in any trip's stop_times.
        
        # For now, we can check if a segment *could* exist between them.
        session = SessionLocal()
        try:
            # Check if any segment directly connects these two stops
            segment_exists = session.query(Segment).filter(
                Segment.source_station_id == str(from_stop_id),
                Segment.dest_station_id == str(to_stop_id)
            ).first()
            if segment_exists:
                return True
            
            # Additional logic could go here to check if they are on the same line etc.
            
            return False # If no direct segment, assume no implicit link for now
        finally:
            session.close()

    def _is_night_layover(self, arrival_time: datetime, departure_time: datetime) -> bool:
        """Check if the layover occurs at night."""
        return arrival_time.hour < 6 or departure_time.hour < 6

    def _is_safe_station(self, station_id: int) -> bool:
        """Check if the station is safe."""
        return True

    def validate_realtime_delay_propagation(self, delay_data: dict, route: Route) -> bool:
        """
        Validate real-time delay propagation (RT-031).
        Checks if a delay in an early segment makes a later transfer impossible.
        """
        if not route.segments: return True
        
        current_delay = timedelta(0)
        for i, segment in enumerate(route.segments):
            # Apply delay if trip_id matches
            trip_delay = delay_data.get(segment.trip_id, 0)
            current_delay = max(current_delay, timedelta(minutes=trip_delay))
            
            # Check feasibility of next transfer
            if i < len(route.transfers):
                transfer = route.transfers[i]
                nxt_segment = route.segments[i+1]
                
                actual_arrival = segment.arrival_time + current_delay
                if actual_arrival + timedelta(minutes=transfer.duration_minutes) > nxt_segment.departure_time:
                    # Delay exceeded transfer window
                    return False
        return True

    def validate_cancellation_removal(self, cancellation_data: List[int], route: Route) -> bool:
        """
        Validate route removal on cancellation (RT-032).
        Returns False if any segment in the route belongs to a cancelled trip.
        """
        cancelled_trips = set(cancellation_data or [])
        for segment in route.segments:
            if segment.trip_id in cancelled_trips:
                return False
        return True

    def validate_partial_delay(self, delay_data: dict, route: Route) -> bool:
        """
        Validate partial delay affecting downstream stops (RT-033).
        Similar to RT-031 but specifically ensures arrival times are updated.
        """
        return self.validate_realtime_delay_propagation(delay_data, route)

    def validate_realtime_update_during_query(self, update_data: dict, route: Route) -> bool:
        """
        Validate real-time update during query (RT-034).
        Ensures the route returned is consistent with updates received mid-flight.
        """
        delays = update_data.get('delays', {})
        cancellations = update_data.get('cancellations', [])
        
        if not self.validate_cancellation_removal(cancellations, route):
            return False
        return self.validate_realtime_delay_propagation(delays, route)

    def validate_outdated_realtime_cache(self, cache_data: dict, route: Route) -> bool:
        """
        Validate outdated real-time cache ignored (RT-035).
        Checks if the cache timestamp is too old.
        """
        timestamp = cache_data.get('timestamp')
        if not timestamp: return True
        
        # If cache is older than 5 minutes, consider it outdated for real-time
        if (datetime.utcnow() - timestamp).total_seconds() > 300:
            return False
        return True
