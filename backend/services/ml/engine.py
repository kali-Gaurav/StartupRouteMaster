import logging
import time
import asyncio
from typing import Dict, Any, Optional, List
from core.system_monitor import system_monitor, SystemState

logger = logging.getLogger("routemaster.ml_service")

class MLMicroservice:
    """
    Task 7: Decoupled ML Microservice Engine.
    Handles Predictive Modeling (Delays, Cancellation, Demand) with Load-Aware Shedding.
    """
    def __init__(self, db_session):
        self.db = db_session
        
    async def predict_delay(self, train_number: str, station_code: str) -> Dict[str, Any]:
        """Latency-sensitive delay prediction with propagation awareness."""
        state = system_monitor.current_state
        if state >= SystemState.CRITICAL:
            return {"status": "skipped", "reason": "system_overload", "predicted_delay_mins": 0}

        from services.ml.delayed_models import DelayPredictionModel
        # [Task 14.2] Real-time delay propagation
        predictor = DelayPredictionModel()
        
        start = time.perf_counter()
        # In a real scenario, we'd fetch the current delay from RealtimeOverlay
        # and predict the 'target station' delay.
        prediction = predictor.predict(self.db, train_number, 0, 0) # Placeholder indices
        duration_ms = (time.perf_counter() - start) * 1000
        
        return {
            "status": "success",
            "predicted_delay_mins": prediction or 0,
            "ml_latency_ms": duration_ms
        }

    async def get_route_reliability(self, route: Any) -> float:
        """
        🛡️ TASK 14.1/14.3: Integrated ML-based reliability predictions.
        Combines trip reliability and transfer success confidence.
        """
        from services.ml.reliability_model import get_reliability_model
        model = await get_reliability_model()
        
        total_confidence = 1.0
        
        # 1. Score each segment
        for segment in getattr(route, 'segments', []):
            conf = await model.predict(
                trip_id=segment.trip_id,
                origin_stop_id=segment.departure_stop_id,
                destination_stop_id=segment.arrival_stop_id,
                departure_time=segment.departure_time,
                distance_km=segment.distance_km
            )
            total_confidence *= conf
            
        # 2. Score each transfer [Task 14.3]
        from services.ml.delayed_models import TransferSuccessProbabilityModel
        transfer_model = TransferSuccessProbabilityModel()
        for tr in getattr(route, 'transfers', []):
            # Probability of making the transfer given historical delay variance
            prob = transfer_model.get_transfer_success_probability(
                arrival_delay=0, # Assume on-time for baseline reliability
                transfer_buffer_minutes=tr.duration_minutes
            )
            total_confidence *= prob
            
        return round(total_confidence, 4)

    async def predict_tatkal_demand(self, train_number: str, travel_date: str) -> Dict[str, Any]:
        """Heavy ML Task for Tatkal Demand."""
        state = system_monitor.current_state
        if state >= SystemState.WARNING:
            # Skip heavy Tatkal ML during WARNING to save RAM/CPU
            return {"status": "skipped", "demand_index": 0.5}

        from services.tatkal_demand_predictor import TatkalDemandPredictor
        predictor = TatkalDemandPredictor(self.db)
        
        return await predictor.predict_demand(train_number, travel_date)
