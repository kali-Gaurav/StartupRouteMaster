"""
RouteMaster Agent Integration API Endpoints
===========================================

Provides REST APIs for autonomous RouteMaster Agent to:
1. Bulk insert train schedules (from IRCTC scraping)
2. Update real-time train state (delays, cancellations)
3. Report pricing optimization results
4. Log feedback for ML model retraining
5. Query current system state

These endpoints form the primary data ingestion pipeline
for the intelligent backend system.

Author: Backend Intelligence System
Date: 2026-02-17
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, date
from pydantic import BaseModel, Field

import asyncio
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from database import get_db
from database.models import (
    Trip, Stop, Route, StopTime, TrainState, 
    Disruption, RLFeedbackLog
)

from services.cache_service import cache_service
from services.event_producer import publish_event
# from services.graph_mutation_engine import GraphMutationEngine
from database.config import Config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/routemaster", tags=["routemaster-integration"])

# Graph mutation engine for real-time updates
# graph_mutation_engine = GraphMutationEngine()
graph_mutation_engine = None  # TODO: Initialize when GraphMutationEngine is available

# ============================================================================
# PYDANTIC MODELS - REQUEST/RESPONSE SCHEMAS
# ============================================================================

class StopTimeSchema(BaseModel):
    """Stop time within a trip."""
    stop_code: str = Field(..., description="Station code (e.g., NDLS)")
    arrival_time: str = Field(..., description="Arrival time HH:MM")
    departure_time: str = Field(..., description="Departure time HH:MM")
    sequence: int = Field(..., description="Stop sequence in trip")
    platform: Optional[str] = None


class TripDataSchema(BaseModel):
    """Trip/train schedule data from scraping."""
    train_number: str = Field(..., description="Train number (e.g., 12001)")
    train_name: str = Field(..., description="Train name")
    source_code: str = Field(..., description="Source station code")
    destination_code: str = Field(..., description="Destination station code")
    stops: List[StopTimeSchema] = Field(..., description="List of stops")
    total_seats: int = Field(..., ge=50, le=2000)
    route_type: str = Field("TRAIN", pattern="^TRAIN$")
    service_dates: List[str] = Field(..., description="Dates in YYYY-MM-DD")

def _process_bulk_insert_sync(trips: List[TripDataSchema], db: Session) -> tuple[int, int, List[Dict[str, str]]]:
    inserted_count = 0
    failed_count = 0
    errors = []
    
    for trip_data in trips:
        try:
            # Validate and insert trip
            inserted = _insert_trip_from_scrape(trip_data, db)
            if inserted:
                inserted_count += 1
            else:
                failed_count += 1
                errors.append({
                    "train": trip_data.train_number,
                    "error": "Failed to insert trip"
                })
        except Exception as e:
            failed_count += 1
            errors.append({
                "train": trip_data.train_number,
                "error": str(e)
            })
            logger.error(f"Insert failed for train {trip_data.train_number}: {e}")
    
    # Commit all insertions
    db.commit()
    return inserted_count, failed_count, errors

class BulkInsertTripsRequest(BaseModel):
    """Request to bulk insert trips."""
    source_system: str = Field(..., description="Source (e.g., 'irctc_scraper')")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    trips: List[TripDataSchema] = Field(..., min_items=1, max_items=1000)


class BulkInsertTripsResponse(BaseModel):
    """Response from bulk insert."""
    success: bool
    inserted_count: int
    failed_count: int
    errors: List[Dict[str, str]] = []
    cache_invalidated: bool
    message: str


class TrainStateUpdateRequest(BaseModel):
    """Real-time train state update."""
    train_number: str = Field(..., description="Train number")
    current_stop_code: Optional[str] = None
    next_stop_code: Optional[str] = None
    delay_minutes: int = Field(default=0, ge=0, le=1440)
    status: str = Field(
        default="on_time",
        pattern="^(on_time|delayed|cancelled|rescheduled|diverted)$"
    )
    platform_number: Optional[str] = None
    occupancy_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    estimated_arrival: Optional[str] = None  # ISO format
    estimated_departure: Optional[str] = None  # ISO format
    cancelled_stations: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TrainStateUpdateResponse(BaseModel):
    """Response from train state update."""
    success: bool
    train_number: str
    status_updated: bool
    graph_mutated: bool
    routes_affected: int
    notifications_sent: int
    message: str


class PricingUpdateRequest(BaseModel):
    """Pricing optimization from RouteMaster."""
    source_code: str
    destination_code: str
    date: date
    current_occupancy: float = Field(ge=0.0, le=1.0)
    predicted_demand: float = Field(ge=0.0, le=1.0)
    recommended_multiplier: float = Field(ge=0.8, le=2.5)
    reasoning: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PricingUpdateResponse(BaseModel):
    """Response from pricing update."""
    success: bool
    rule_id: Optional[str] = None
    previous_multiplier: Optional[float] = None
    new_multiplier: float
    estimated_revenue_impact: Optional[float] = None
    message: str


class RLFeedbackRequest(BaseModel):
    """RL model feedback/labeling."""
    user_id: Optional[str] = None
    action: str = Field(..., pattern="^(route_selected|route_rejected|booking_completed|booking_cancelled)$")
    context: Dict[str, Any] = Field(default_factory=dict)
    reward: float = Field(ge=-1.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RLFeedbackResponse(BaseModel):
    """Response from RL feedback."""
    success: bool
    feedback_id: str
    message: str


class SystemStateResponse(BaseModel):
    """Current system state."""
    active_trains: int
    cached_routes: int
    pending_bookings: int
    avg_occupancy: float
    ml_models_loaded: bool
    last_graph_mutation: Optional[datetime]
    status: str  # "healthy", "degraded", "unhealthy"


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post(
    "/bulk-insert-trips",
    response_model=BulkInsertTripsResponse,
    summary="Bulk insert train schedules from RouteMaster scraping"
)
async def bulk_insert_trips(
    request: BulkInsertTripsRequest,
    db: Session = Depends(get_db)
) -> BulkInsertTripsResponse:
    """
    Accept bulk trip/schedule data from RouteMaster Agent.
    
    Called periodically by agent after scraping IRCTC and partner sites.
    Supports Trains, Buses, Flights.
    """
    logger.info(f"Bulk insert: {len(request.trips)} trips from {request.source_system}")
    
    try:
        inserted_count, failed_count, errors = await asyncio.to_thread(
            _process_bulk_insert_sync, request.trips, db
        )
        
        # Invalidate route search cache
        cache_invalidated = False
        try:
            if cache_service and cache_service.redis:
                # Clear all route cache keys
                cache_service.redis.delete_pattern("routes:*")
                cache_invalidated = True
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {e}")
        
        # Publish event
        await publish_event(
            "trips_bulk_inserted",
            {
                "source": request.source_system,
                "inserted": inserted_count,
                "failed": failed_count
            }
        )
        
        message = f"Inserted {inserted_count} trips, {failed_count} failed"
        logger.info(message)
        
        return BulkInsertTripsResponse(
            success=failed_count == 0,
            inserted_count=inserted_count,
            failed_count=failed_count,
            errors=errors,
            cache_invalidated=cache_invalidated,
            message=message
        )
    
    except Exception as e:
        db.rollback()
        logger.error(f"Bulk insert failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/update-train-state",
    response_model=TrainStateUpdateResponse,
    summary="Update real-time train state (delays, cancellations)"
)
async def update_train_state(
    request: TrainStateUpdateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> TrainStateUpdateResponse:
    """
    Update real-time state of a train.
    
    Triggers:
    - Graph mutation for affected routes
    - Passenger notifications
    - Booking status updates
    """
    logger.info(f"Train state update: {request.train_number}, delay={request.delay_minutes}m")
    
    try:
        # Find trip(s) for this train
        trips = db.query(Trip).filter(
            Trip.trip_id.contains(request.train_number)
        ).all()
        
        if not trips:
            logger.warning(f"No trips found for train {request.train_number}")
            return TrainStateUpdateResponse(
                success=False,
                train_number=request.train_number,
                status_updated=False,
                graph_mutated=False,
                routes_affected=0,
                notifications_sent=0,
                message="Train not found in system"
            )
        
        # Update each trip
        status_updated = False
        routes_affected = 0
        
        for trip in trips:
            try:
                # Update trip state
                trip.delay_minutes = request.delay_minutes
                trip.status = request.status  # If this field exists
                
                # Handle cancellation
                if request.status == "cancelled":
                    trip.is_cancelled = True
                    cancelled_routes = db.query(Route).filter(
                        Route.trip_id == trip.id
                    ).count()
                    routes_affected += cancelled_routes
                
                db.add(trip)
                status_updated = True
            
            except Exception as e:
                logger.error(f"Trip update failed: {e}")
        
        db.commit()
        
        # Trigger graph mutation
        graph_mutated = False
        try:
            # Apply graph mutations for significant delays (using config threshold)
            if graph_mutation_engine and request.delay_minutes >= Config.GRAPH_MUTATION_DELAY_THRESHOLD_MINUTES:
                for trip in trips:
                    graph_mutation_engine.apply_delay_mutation(
                        trip.id,
                        request.delay_minutes
                    )
                graph_mutated = True
                logger.info(f"Graph mutation triggered for {len(trips)} trips with {request.delay_minutes}m delay")
            else:
                logger.debug(f"Delay {request.delay_minutes}m below threshold ({Config.GRAPH_MUTATION_DELAY_THRESHOLD_MINUTES}m), skipping graph mutation")
        except Exception as e:
            logger.warning(f"Graph mutation failed: {e}")
        
        # Queue notifications to affected passengers
        notifications_sent = 0
        background_tasks.add_task(
            _notify_affected_passengers,
            request.train_number,
            request.delay_minutes,
            request.status
        )
        notifications_sent = 1  # Queued
        
        # Publish event
        await publish_event(
            "train_state_updated",
            {
                "train_number": request.train_number,
                "delay_minutes": request.delay_minutes,
                "status": request.status,
                "routes_affected": routes_affected
            }
        )
        
        message = f"Updated train {request.train_number}: {request.status} (+{request.delay_minutes}m)"
        logger.info(message)
        
        return TrainStateUpdateResponse(
            success=True,
            train_number=request.train_number,
            status_updated=status_updated,
            graph_mutated=graph_mutated,
            routes_affected=routes_affected,
            notifications_sent=notifications_sent,
            message=message
        )
    
    except Exception as e:
        db.rollback()
        logger.error(f"Train state update failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/pricing-update",
    response_model=PricingUpdateResponse,
    summary="Update pricing from RouteMaster optimization"
)
async def pricing_update(
    request: PricingUpdateRequest,
    db: Session = Depends(get_db)
) -> PricingUpdateResponse:
    """
    Accept pricing recommendations from RouteMaster Agent.
    
    RouteMaster analyzes demand and suggests price multipliers.
    Stores in Redis so PriceCalculationService can fetch them.
    """
    logger.info(
        f"Pricing update: {request.source_code}-{request.destination_code} "
        f"multiplier={request.recommended_multiplier}"
    )
    
    try:
        if not cache_service or not cache_service.is_available():
            raise HTTPException(status_code=503, detail="Cache service unavailable. Cannot store pricing rules.")

        cache_key = f"pricing_rule:{request.source_code}:{request.destination_code}"
        
        # Get previous multiplier
        import json
        prev_data_str = cache_service.get(cache_key)
        prev_data = json.loads(prev_data_str) if prev_data_str else None
        previous_multiplier = prev_data.get('multiplier', 1.0) if prev_data else 1.0
        
        # Update pricing rule in cache (24 hours TTL)
        cache_service.set(cache_key, json.dumps({
            "multiplier": request.recommended_multiplier,
            "updated_at": request.timestamp.isoformat()
        }), ttl_seconds=86400)
        
        # Estimate revenue impact (simplified)
        revenue_impact = (request.recommended_multiplier - previous_multiplier) * 0.1
        
        # Publish event
        await publish_event(
            "pricing_updated",
            {
                "route": f"{request.source_code}-{request.destination_code}",
                "old_multiplier": previous_multiplier,
                "new_multiplier": request.recommended_multiplier,
                "reason": request.reasoning
            }
        )
        
        message = f"Pricing updated: {previous_multiplier:.2f}x → {request.recommended_multiplier:.2f}x"
        logger.info(message)
        
        return PricingUpdateResponse(
            success=True,
            rule_id=cache_key,
            previous_multiplier=previous_multiplier,
            new_multiplier=request.recommended_multiplier,
            estimated_revenue_impact=revenue_impact,
            message=message
        )
    
    except Exception as e:
        logger.error(f"Pricing update failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/rl-feedback",
    response_model=RLFeedbackResponse,
    summary="Log feedback for RL model retraining"
)
async def log_rl_feedback(
    request: RLFeedbackRequest,
    db: Session = Depends(get_db)
) -> RLFeedbackResponse:
    """
    Log user feedback for RL model retraining.
    
    Feedback is used to improve:
    - Route ranking predictor
    - Tatkal demand predictor
    - Dynamic pricing engine
    """
    try:
        # Log feedback record
        feedback_record = RLFeedbackLog(
            user_id=request.user_id,
            action=request.action,
            context_data=request.context,
            reward=request.reward,
            timestamp=request.timestamp
        )
        
        db.add(feedback_record)
        db.commit()
        
        feedback_id = str(feedback_record.id)
        
        logger.info(f"RL Feedback logged: action={request.action}, reward={request.reward}")
        
        # Publish to Kafka for async model retraining
        await publish_event(
            "rl_feedback_logged",
            {
                "feedback_id": feedback_id,
                "action": request.action,
                "reward": request.reward
            }
        )
        
        return RLFeedbackResponse(
            success=True,
            feedback_id=feedback_id,
            message="Feedback logged successfully"
        )
    
    except Exception as e:
        db.rollback()
        logger.error(f"RL feedback logging failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/system-state",
    response_model=SystemStateResponse,
    summary="Get current system state for monitoring"
)
async def get_system_state(
    db: Session = Depends(get_db)
) -> SystemStateResponse:
    """
    Return current system state for RouteMaster Agent monitoring.
    """
    try:
        # Count active trains
        active_trains = db.query(Trip).filter(
            Trip.status != 'cancelled'
        ).count()
        
        # Count cached routes
        cached_routes = 0
        try:
            if cache_service and cache_service.redis:
                cached_routes = cache_service.redis.dbsize()
        except:
            pass
        
        # Average occupancy (placeholder)
        avg_occupancy = 0.65
        
        # ML models loaded
        ml_models_loaded = True  # Placeholder
        
        status = "healthy"
        if avg_occupancy > 0.9:
            status = "degraded"
        
        return SystemStateResponse(
            active_trains=active_trains,
            cached_routes=cached_routes,
            pending_bookings=0,
            avg_occupancy=avg_occupancy,
            ml_models_loaded=ml_models_loaded,
            last_graph_mutation=datetime.utcnow(),
            status=status
        )
    
    except Exception as e:
        logger.error(f"System state query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _insert_trip_from_scrape(trip_data: TripDataSchema, db: Session) -> bool:
    """Insert trip data from scrape into database."""
    try:
        # TODO: Implement full trip insertion with stops, timing, etc.
        # This is a placeholder
        logger.info(f"Would insert trip: {trip_data.train_number}")
        return True
    except Exception as e:
        logger.error(f"Trip insertion error: {e}")
        return False


async def _notify_affected_passengers(
    train_number: str,
    delay_minutes: int,
    status: str
):
    """Notify passengers affected by train state change."""
    try:
        logger.info(f"Notifying passengers for train {train_number}")
        # TODO: Implement notification service
        # Send SMS/Email/Push notifications
    except Exception as e:
        logger.error(f"Notification failed: {e}")
