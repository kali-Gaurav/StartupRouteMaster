"""
Graph Mutation Service - API Layer for Real-Time Updates

Provides REST API endpoints for:
- Applying real-time train updates (delays, cancellations)
- Querying train states
- Managing graph mutations
- Integration with external data sources (NTES, GPS, etc.)
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import logging

from .train_state_service import (
    train_state_store,
    graph_mutation_engine,
    initialize_graph_mutation,
    TrainState
)
from .route_engine import OptimizedRAPTOR
from .config import Config

logger = logging.getLogger(__name__)

# Pydantic models for API
class DelayUpdateRequest(BaseModel):
    trip_id: int = Field(..., description="Trip ID to apply delay to")
    delay_minutes: int = Field(..., description="Delay in minutes")
    reason: Optional[str] = Field(None, description="Reason for delay")

class CancellationUpdateRequest(BaseModel):
    trip_id: int = Field(..., description="Trip ID to cancel")
    cancelled_stations: Optional[List[int]] = Field(None, description="List of cancelled stop IDs")

class LocationUpdateRequest(BaseModel):
    trip_id: int = Field(..., description="Trip ID")
    current_station_id: int = Field(..., description="Current station ID")
    next_station_id: Optional[int] = Field(None, description="Next station ID")

class OccupancyUpdateRequest(BaseModel):
    trip_id: int = Field(..., description="Trip ID")
    occupancy_rate: float = Field(..., ge=0.0, le=1.0, description="Occupancy rate (0.0-1.0)")

class BulkUpdateRequest(BaseModel):
    updates: List[Dict[str, Any]] = Field(..., description="List of updates to apply")

class TrainStateResponse(BaseModel):
    trip_id: int
    train_number: str
    current_station_id: Optional[int]
    next_station_id: Optional[int]
    delay_minutes: int
    status: str
    platform_number: Optional[str]
    last_updated: datetime
    estimated_arrival: Optional[datetime]
    estimated_departure: Optional[datetime]
    occupancy_rate: float
    cancelled_stations: List[int]

# API Router
router = APIRouter(prefix="/api/v1/graph-mutation", tags=["graph-mutation"])

# Global variables
_route_engine: Optional[OptimizedRAPTOR] = None

async def initialize_service(route_engine: OptimizedRAPTOR):
    """Initialize the graph mutation service"""
    global _route_engine
    _route_engine = route_engine
    await initialize_graph_mutation(route_engine)
    logger.info("Graph mutation service initialized")

# API Endpoints
@router.post("/delay", response_model=Dict[str, str])
async def apply_delay(update: DelayUpdateRequest, background_tasks: BackgroundTasks):
    """Apply delay to a train"""
    try:
        await train_state_store.apply_delay(
            update.trip_id,
            update.delay_minutes,
            update.reason or "Unknown"
        )

        # Apply to route engine in background
        background_tasks.add_task(_apply_delay_to_graph, update.trip_id, update.delay_minutes)

        return {"status": "success", "message": f"Delay of {update.delay_minutes}min applied to trip {update.trip_id}"}

    except Exception as e:
        logger.error(f"Error applying delay: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cancel", response_model=Dict[str, str])
async def cancel_train(update: CancellationUpdateRequest, background_tasks: BackgroundTasks):
    """Cancel a train"""
    try:
        await train_state_store.cancel_train(update.trip_id, update.cancelled_stations)

        # Apply to route engine in background
        background_tasks.add_task(_apply_cancellation_to_graph, update.trip_id, update.cancelled_stations)

        return {"status": "success", "message": f"Train {update.trip_id} cancelled"}

    except Exception as e:
        logger.error(f"Error cancelling train: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/location", response_model=Dict[str, str])
async def update_location(update: LocationUpdateRequest):
    """Update train location"""
    try:
        await train_state_store.update_location(
            update.trip_id,
            update.current_station_id,
            update.next_station_id
        )

        return {"status": "success", "message": f"Location updated for trip {update.trip_id}"}

    except Exception as e:
        logger.error(f"Error updating location: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/occupancy", response_model=Dict[str, str])
async def update_occupancy(update: OccupancyUpdateRequest, background_tasks: BackgroundTasks):
    """Update train occupancy"""
    try:
        # Update state store
        state = await train_state_store.get_train_state(update.trip_id)
        if state:
            state.occupancy_rate = update.occupancy_rate
            state.last_updated = datetime.utcnow()
            await train_state_store.update_train_state(state)

        # Apply to route engine in background
        background_tasks.add_task(_apply_occupancy_to_graph, update.trip_id, update.occupancy_rate)

        return {"status": "success", "message": f"Occupancy updated for trip {update.trip_id}"}

    except Exception as e:
        logger.error(f"Error updating occupancy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/bulk-update", response_model=Dict[str, str])
async def bulk_update(request: BulkUpdateRequest, background_tasks: BackgroundTasks):
    """Apply multiple updates in bulk"""
    try:
        processed_updates = 0

        for update in request.updates:
            update_type = update.get('type')

            if update_type == 'delay':
                await train_state_store.apply_delay(
                    update['trip_id'],
                    update['delay_minutes'],
                    update.get('reason', 'Bulk update')
                )
                background_tasks.add_task(_apply_delay_to_graph, update['trip_id'], update['delay_minutes'])

            elif update_type == 'cancellation':
                await train_state_store.cancel_train(
                    update['trip_id'],
                    update.get('cancelled_stations')
                )
                background_tasks.add_task(_apply_cancellation_to_graph, update['trip_id'], update.get('cancelled_stations'))

            elif update_type == 'location':
                await train_state_store.update_location(
                    update['trip_id'],
                    update['current_station_id'],
                    update.get('next_station_id')
                )

            elif update_type == 'occupancy':
                state = await train_state_store.get_train_state(update['trip_id'])
                if state:
                    state.occupancy_rate = update['occupancy_rate']
                    state.last_updated = datetime.utcnow()
                    await train_state_store.update_train_state(state)
                background_tasks.add_task(_apply_occupancy_to_graph, update['trip_id'], update['occupancy_rate'])

            processed_updates += 1

        return {"status": "success", "message": f"Processed {processed_updates} updates"}

    except Exception as e:
        logger.error(f"Error in bulk update: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/train/{trip_id}", response_model=TrainStateResponse)
async def get_train_state(trip_id: int):
    """Get current state of a train"""
    try:
        state = await train_state_store.get_train_state(trip_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Train state not found for trip {trip_id}")

        return TrainStateResponse(
            trip_id=state.trip_id,
            train_number=state.train_number,
            current_station_id=state.current_station_id,
            next_station_id=state.next_station_id,
            delay_minutes=state.delay_minutes,
            status=state.status,
            platform_number=state.platform_number,
            last_updated=state.last_updated,
            estimated_arrival=state.estimated_arrival,
            estimated_departure=state.estimated_departure,
            occupancy_rate=state.occupancy_rate,
            cancelled_stations=state.cancelled_stations
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting train state: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/active-trains", response_model=List[TrainStateResponse])
async def get_active_trains():
    """Get all active trains"""
    try:
        states = await train_state_store.get_all_active_trains()

        return [
            TrainStateResponse(
                trip_id=state.trip_id,
                train_number=state.train_number,
                current_station_id=state.current_station_id,
                next_station_id=state.next_station_id,
                delay_minutes=state.delay_minutes,
                status=state.status,
                platform_number=state.platform_number,
                last_updated=state.last_updated,
                estimated_arrival=state.estimated_arrival,
                estimated_departure=state.estimated_departure,
                occupancy_rate=state.occupancy_rate,
                cancelled_stations=state.cancelled_stations
            )
            for state in states
        ]

    except Exception as e:
        logger.error(f"Error getting active trains: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/refresh-graph", response_model=Dict[str, str])
async def refresh_graph():
    """Force refresh of the routing graph with current train states"""
    try:
        if not _route_engine:
            raise HTTPException(status_code=500, detail="Route engine not initialized")

        # Get all active train states
        active_states = await train_state_store.get_all_active_trains()

        # Apply all updates to graph
        updates = []
        for state in active_states:
            if state.delay_minutes > 0:
                updates.append({
                    'type': 'delay',
                    'trip_id': state.trip_id,
                    'delay_minutes': state.delay_minutes
                })
            if state.status == 'cancelled':
                updates.append({
                    'type': 'cancellation',
                    'trip_id': state.trip_id,
                    'cancelled_stations': state.cancelled_stations
                })
            if state.occupancy_rate > 0:
                updates.append({
                    'type': 'occupancy',
                    'trip_id': state.trip_id,
                    'occupancy_rate': state.occupancy_rate
                })

        await _route_engine.apply_realtime_updates(updates)

        return {"status": "success", "message": f"Graph refreshed with {len(updates)} updates"}

    except Exception as e:
        logger.error(f"Error refreshing graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background task functions
async def _apply_delay_to_graph(trip_id: int, delay_minutes: int):
    """Apply delay to route engine graph"""
    try:
        if _route_engine:
            await _route_engine._apply_delay_update({
                'trip_id': trip_id,
                'delay_minutes': delay_minutes
            })
    except Exception as e:
        logger.error(f"Error applying delay to graph: {e}")

async def _apply_cancellation_to_graph(trip_id: int, cancelled_stations: Optional[List[int]]):
    """Apply cancellation to route engine graph"""
    try:
        if _route_engine:
            await _route_engine._apply_cancellation_update({
                'trip_id': trip_id,
                'cancelled_stations': cancelled_stations or []
            })
    except Exception as e:
        logger.error(f"Error applying cancellation to graph: {e}")

async def _apply_occupancy_to_graph(trip_id: int, occupancy_rate: float):
    """Apply occupancy update to route engine graph"""
    try:
        if _route_engine:
            await _route_engine._apply_occupancy_update({
                'trip_id': trip_id,
                'occupancy_rate': occupancy_rate
            })
    except Exception as e:
        logger.error(f"Error applying occupancy to graph: {e}")

# Integration with external data sources
class ExternalDataSource:
    """Base class for external data sources (NTES, GPS, etc.)"""

    async def fetch_updates(self) -> List[Dict[str, Any]]:
        """Fetch updates from external source"""
        raise NotImplementedError

    async def process_updates(self, updates: List[Dict[str, Any]]):
        """Process and apply updates"""
        for update in updates:
            await graph_mutation_engine.process_realtime_update(update)

class NTESDataSource(ExternalDataSource):
    """NTES (National Train Enquiry System) data source"""

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url

    async def fetch_updates(self) -> List[Dict[str, Any]]:
        """Fetch delay and cancellation updates from NTES"""
        # Implementation would call NTES API
        # For now, return empty list
        return []

class GPSDataSource(ExternalDataSource):
    """GPS tracking data source"""

    def __init__(self, api_endpoint: str):
        self.api_endpoint = api_endpoint

    async def fetch_updates(self) -> List[Dict[str, Any]]:
        """Fetch location updates from GPS"""
        # Implementation would call GPS API
        # For now, return empty list
        return []

# Global data sources
ntes_source = NTESDataSource(
    api_key=Config.NTES_API_KEY,
    base_url=Config.NTES_BASE_URL
)

gps_source = GPSDataSource(
    api_endpoint=Config.GPS_API_ENDPOINT
)

async def poll_external_sources():
    """Poll external data sources for updates"""
    while True:
        try:
            # Fetch from NTES
            ntes_updates = await ntes_source.fetch_updates()
            if ntes_updates:
                await ntes_source.process_updates(ntes_updates)

            # Fetch from GPS
            gps_updates = await gps_source.fetch_updates()
            if gps_updates:
                await gps_source.process_updates(gps_updates)

        except Exception as e:
            logger.error(f"Error polling external sources: {e}")

        # Poll every 30 seconds
        await asyncio.sleep(30)

# Startup function
async def start_background_services():
    """Start background services for real-time updates"""
    asyncio.create_task(poll_external_sources())
    logger.info("Graph mutation background services started")
