import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from ...database.models import Stop, TrainState
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
        # Pre-load static data if needed (e.g., average congestion per station)
        
    async def calculate_transfer_risk(self, transfer: TransferConnection, 
                                      previous_segment_trip_id: Optional[int],
                                      current_route: Route,
                                      constraints: RouteConstraints) -> float:
        """
        Calculates the probability of missing a specific transfer.
        Formula: P(miss) = sigmoid(delay_history + congestion + buffer_time)
        Returns a float between 0 (low risk) and 1 (high risk).
        """
        delay_factor = await self._get_delay_history_factor(previous_segment_trip_id, transfer.arrival_time)
        congestion_factor = self._get_congestion_factor(transfer.station_id, transfer.arrival_time)
        buffer_factor = self._get_buffer_time_factor(transfer, constraints)
        
        # Simple linear combination for now, to be replaced by a proper sigmoid/ML model (Phase 6)
        risk_score = (delay_factor * 0.4) + (congestion_factor * 0.3) + (buffer_factor * 0.3)
        
        # Clamp to [0, 1]
        return max(0.0, min(1.0, risk_score))

    async def _get_delay_history_factor(self, trip_id: Optional[int], arrival_time: datetime) -> float:
        """
        Estimates a delay factor based on historical data for a trip.
        (Step 3 — Historical Delay Data)
        """
        if not trip_id:
            # No previous trip info — use a low-but-nonzero default risk so transfers without history aren't treated as perfect
            return 0.1 # Base historical unreliability
            
        session = self.db_session_factory()
        try:
            # For simplicity, check live TrainState first
            train_state = session.query(TrainState).filter(TrainState.trip_id == trip_id).first()
            if train_state and train_state.delay_minutes > 0:
                # Immediate delay, higher risk
                return min(train_state.delay_minutes / 60.0, 1.0) # Max 1.0 for 60+ min delay

            # Placeholder for actual historical data lookup
            # In a real system, this would query aggregated historical delay data for this trip/segment
            # For now, return a low risk if no live delay
            return 0.1 # Base historical unreliability
        finally:
            session.close()

    def _get_congestion_factor(self, station_id: int, time_of_day: datetime) -> float:
        """
        Estimates a congestion factor for a station at a given time.
        (Step 2 — Station Congestion Score)
        """
        session = self.db_session_factory()
        try:
            stop = session.query(Stop).filter(Stop.id == station_id).first()
            if stop and stop.facilities_json:
                # Use facilities_json for some static congestion factor
                base_congestion = stop.facilities_json.get('average_congestion_factor', 0.2)
            else:
                base_congestion = 0.2

            # Adjust based on peak hours (placeholder)
            hour = time_of_day.hour
            if 7 <= hour <= 10 or 17 <= hour <= 20: # Peak hours
                return min(base_congestion * 1.5, 1.0)
            return base_congestion
        finally:
            session.close()

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
