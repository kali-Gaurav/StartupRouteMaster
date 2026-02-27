import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from database.models import Stop, TrainState


from .data_structures import TransferConnection, Route
from .constraints import RouteConstraints

logger = logging.getLogger(__name__)

class TransferIntelligenceManager:
    """
    Manages transfer intelligence, computing the probability of missing a connection.
    Implements Phase 4: Transfer Intelligence.
    """

    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory
        
    async def calculate_transfer_risk(self, transfer: TransferConnection, 
                                      previous_segment_trip_id: Optional[int],
                                      current_route: Route,
                                      constraints: RouteConstraints,
                                      graph: Any = None) -> float:
        """
        Calculates the probability of missing a specific transfer.
        Formula: P(miss) = sigmoid(delay_history + congestion + buffer_time)
        """
        delay_factor = self._get_delay_history_factor_optimized(previous_segment_trip_id, graph)
        congestion_factor = self._get_congestion_factor_optimized(transfer.station_id, transfer.arrival_time, graph)
        buffer_factor = self._get_buffer_time_factor(transfer, constraints)
        
        risk_score = (delay_factor * 0.4) + (congestion_factor * 0.3) + (buffer_factor * 0.3)
        return max(0.0, min(1.0, risk_score))

    def _get_delay_history_factor_optimized(self, trip_id: Optional[int], graph: Any) -> float:
        """Uses graph overlay for zero-DB-access delay lookup."""
        if not trip_id or not graph:
            return 0.1
        
        delay_mins = graph.overlay.get_trip_delay(trip_id)
        if delay_mins > 0:
            return min(delay_mins / 60.0, 1.0)
        return 0.1

    def _get_congestion_factor_optimized(self, station_id: int, time_of_day: datetime, graph: Any) -> float:
        """Uses graph stop_cache for zero-DB-access congestion lookup."""
        if not graph or station_id not in graph.stop_cache:
            base_congestion = 0.2
        else:
            stop = graph.stop_cache[station_id]
            # Handle both dict and object Stop types if necessary
            facilities = getattr(stop, 'facilities_json', {}) or {}
            base_congestion = facilities.get('average_congestion_factor', 0.2)

        hour = time_of_day.hour
        if 7 <= hour <= 10 or 17 <= hour <= 20:
            return min(base_congestion * 1.5, 1.0)
        return base_congestion

    def _get_buffer_time_factor(self, transfer: TransferConnection, constraints: RouteConstraints) -> float:
        """
        Calculates a factor based on buffer time between connections.
        Considers Station Walking Times (Step 1).
        """
        # Duration minutes already includes implied walking time if from Transfer table or default
        total_buffer_minutes = (transfer.departure_time - transfer.arrival_time).total_seconds() / 60
        
        # Factor in actual walking time (e.g. from Platform X to Platform Y)
        # This will require access to the Transfer model's walking_time_minutes field
        # For now, we will assume transfer.duration_minutes is the total required buffer.
        
        # Ideal buffer time: min_transfer_time + safety margin
        # Risk increases as total_buffer_minutes approaches min_transfer_time
        
        # Placeholder: If buffer is less than min_transfer, risk is high
        if total_buffer_minutes < constraints.min_transfer_time:
            return 1.0 # Very high risk

        # If buffer is barely enough, moderate risk
        if total_buffer_minutes < constraints.min_transfer_time + 10: # 10 min grace
            return 0.7

        # Otherwise low risk
        return 0.1
