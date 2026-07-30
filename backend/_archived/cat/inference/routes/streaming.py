"""
Streaming endpoints for the CAT inference service.
Provides Server-Sent Events (SSE) for real-time prediction streaming.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import AsyncGenerator, Dict, Any, Optional
from enum import Enum

from fastapi import APIRouter, Request, HTTPException, Depends, Query
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, Field

from ..config import get_inference_settings
from ..service import (
    get_model,
    get_collector,
    get_preprocessor,
    get_cache,
    verify_api_key,
    check_rate_limit,
    _audit_logger
)
from ...models.schemas import AvailabilityPrediction

logger = logging.getLogger(__name__)

# Create streaming router
streaming_router = APIRouter(prefix="/predict", tags=["Streaming"])

# Get settings for configuration
_settings = get_inference_settings()


class StreamEventType(str, Enum):
    """SSE event types for prediction streaming"""
    PREDICTION = "prediction"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    COMPLETE = "complete"
    CONNECTED = "connected"


class StreamConfig(BaseModel):
    """Configuration for prediction streaming"""
    interval_seconds: int = Field(default=60, ge=10, le=3600, description="Interval between predictions in seconds")
    duration_seconds: int = Field(default=3600, ge=60, le=86400, description="Total streaming duration in seconds")
    include_heartbeat: bool = Field(default=True, description="Include heartbeat events")
    heartbeat_interval_seconds: int = Field(default=30, ge=10, le=300, description="Heartbeat interval")


class StreamConnectionInfo(BaseModel):
    """Information about a streaming connection"""
    connection_id: str
    location_id: str
    start_time: datetime
    interval_seconds: int
    duration_seconds: int


async def generate_predictions_stream(
    location_id: str,
    start_time: datetime,
    interval_seconds: int,
    duration_seconds: int,
    request: Request,
    connection_id: str
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Generator function for streaming predictions with proper disconnection handling.
    
    Args:
        location_id: Location ID to predict
        start_time: Start time for predictions
        interval_seconds: Interval between predictions
        duration_seconds: Total duration to stream
        request: FastAPI request object for disconnection detection
        connection_id: Unique connection identifier
        
    Yields:
        SSE events with prediction data or status updates
    """
    model = await get_model()
    collector = await get_collector()
    preprocessor = get_preprocessor()
    cache = get_cache()
    
    start_timestamp = datetime.utcnow()
    current_time = start_time
    prediction_count = 0
    
    logger.info(
        f"Starting prediction stream for location={location_id}, "
        f"interval={interval_seconds}s, duration={duration_seconds}s, connection_id={connection_id}"
    )
    
    try:
        # Send connection confirmation
        yield {
            "event": StreamEventType.CONNECTED.value,
            "data": json.dumps({
                "connection_id": connection_id,
                "location_id": location_id,
                "start_time": start_timestamp.isoformat(),
                "interval_seconds": interval_seconds,
                "duration_seconds": duration_seconds,
                "message": "Prediction stream connected"
            })
        }
        
        stream_end_time = start_timestamp + timedelta(seconds=duration_seconds)
        heartbeat_interval = 30  # seconds
        
        while datetime.utcnow() < stream_end_time:
            # Check if client disconnected
            try:
                if await request.is_disconnected():
                    logger.info(f"Client disconnected: connection_id={connection_id}")
                    break
            except Exception as e:
                logger.warning(f"Error checking disconnection: {e}")
                # Continue streaming if we can't check disconnection
            
            try:
                # Check cache first
                cached = cache.get(location_id, current_time)
                
                if cached:
                    # Audit log: cached response
                    _audit_logger.log_prediction_response(
                        location_id=location_id,
                        prediction_time=current_time,
                        probability=cached.probability,
                        confidence_lower=cached.confidence_interval[0],
                        confidence_upper=cached.confidence_interval[1]
                    )
                    
                    yield {
                        "event": StreamEventType.PREDICTION.value,
                        "data": cached.model_dump_json()
                    }
                    prediction_count += 1
                else:
                    # Fetch contextual data
                    contextual_data = await collector.fetch_contextual_data(
                        location_id=location_id,
                        prediction_time=current_time,
                        context_hours=24
                    )
                    
                    # Preprocess
                    if contextual_data.historical_availability.records:
                        pred_time = contextual_data.historical_availability.records[-1].timestamp
                    else:
                        pred_time = current_time
                    
                    (
                        event_emb, weather_emb,
                        historical_seq, temporal_enc
                    ) = preprocessor.preprocess(
                        contextual_data.event_calendar,
                        contextual_data.weather,
                        contextual_data.historical_availability,
                        pred_time
                    )
                    
                    model_input = preprocessor.create_model_input(
                        event_emb, weather_emb, historical_seq, temporal_enc
                    )
                    
                    # Generate prediction
                    import torch
                    with torch.no_grad():
                        output = model(model_input.unsqueeze(0))
                    
                    prediction = AvailabilityPrediction(
                        probability=output["probability"].item(),
                        confidence_interval=(
                            output["confidence_lower"].item(),
                            output["confidence_upper"].item()
                        ),
                        contributing_factors=output.get("contributing_factors", []),
                        location_id=location_id,
                        prediction_time=current_time.isoformat(),
                        model_version="1.0.0"
                    )
                    
                    # Cache prediction
                    cache.set(location_id, current_time, prediction)
                    prediction_count += 1
                    
                    # Audit log: response sent
                    _audit_logger.log_prediction_response(
                        location_id=location_id,
                        prediction_time=current_time,
                        probability=prediction.probability,
                        confidence_lower=prediction.confidence_interval[0],
                        confidence_upper=prediction.confidence_interval[1]
                    )
                    
                    yield {
                        "event": StreamEventType.PREDICTION.value,
                        "data": prediction.model_dump_json()
                    }
                
            except asyncio.CancelledError:
                logger.info(f"Stream cancelled: connection_id={connection_id}")
                break
            except Exception as e:
                logger.error(f"Prediction error in stream: {e}")
                
                # Audit log: error
                _audit_logger.log_prediction_error(
                    location_id=location_id,
                    prediction_time=current_time,
                    error_type="streaming_error",
                    error_message=str(e)
                )
                
                yield {
                    "event": StreamEventType.ERROR.value,
                    "data": json.dumps({
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat()
                    })
                }
            
            # Wait for next interval
            await asyncio.sleep(interval_seconds)
            current_time = current_time + timedelta(seconds=interval_seconds)
        
        # Send completion event
        yield {
            "event": StreamEventType.COMPLETE.value,
            "data": json.dumps({
                "connection_id": connection_id,
                "total_predictions": prediction_count,
                "duration_seconds": (datetime.utcnow() - start_timestamp).total_seconds(),
                "end_time": datetime.utcnow().isoformat(),
                "message": "Prediction stream completed"
            })
        }
        
    except asyncio.CancelledError:
        logger.info(f"Stream cancelled (outer): connection_id={connection_id}")
        yield {
            "event": StreamEventType.ERROR.value,
            "data": json.dumps({
                "error": "Stream was cancelled",
                "timestamp": datetime.utcnow().isoformat()
            })
        }
    except Exception as e:
        logger.error(f"Unexpected error in stream: {e}")
        yield {
            "event": StreamEventType.ERROR.value,
            "data": json.dumps({
                "error": "Internal server error",
                "timestamp": datetime.utcnow().isoformat()
            })
        }
    finally:
        logger.info(
            f"Stream ended: connection_id={connection_id}, "
            f"predictions={prediction_count}"
        )


@streaming_router.get("/stream")
async def stream_availability_predictions(
    request: Request,
    location_id: str = Query(..., description="Location ID to predict"),
    start_time: datetime = Query(..., description="Start time for predictions"),
    interval_seconds: int = Query(
        default=60,
        ge=10,
        le=3600,
        description="Interval between predictions in seconds"
    ),
    duration_seconds: int = Query(
        default=3600,
        ge=60,
        le=86400,
        description="Total duration to stream in seconds"
    ),
    x_api_key: str = Depends(verify_api_key)
):
    """
    Stream availability predictions using Server-Sent Events (SSE).
    
    Generates predictions at configured intervals for real-time updates.
    Supports graceful client disconnection handling.
    
    Event Types:
    - connected: Initial connection confirmation
    - prediction: New prediction result
    - heartbeat: Keep-alive signal (optional)
    - error: Error occurred during prediction
    - complete: Stream completed or duration ended
    
    Args:
        request: FastAPI request object for disconnection detection
        location_id: Location ID to predict
        start_time: Start time for predictions
        interval_seconds: Interval between predictions (default: 60s, range: 10-3600s)
        duration_seconds: Total duration to stream (default: 3600s, range: 60-86400s)
        x_api_key: API key for authentication
        
    Returns:
        SSE event stream with predictions
    """
    import uuid
    
    # Generate unique connection ID
    connection_id = str(uuid.uuid4())
    
    # Audit log: stream request received
    _audit_logger.log_prediction_request(
        location_id=location_id,
        prediction_time=start_time,
        context_hours=24,
        client_id=x_api_key or "anonymous"
    )
    
    # Check rate limit
    check_rate_limit(x_api_key or "default")
    
    logger.info(
        f"New prediction stream: location={location_id}, "
        f"start_time={start_time}, interval={interval_seconds}s, "
        f"duration={duration_seconds}s, connection_id={connection_id}"
    )
    
    # Create event generator
    async def event_generator():
        async for event in generate_predictions_stream(
            location_id=location_id,
            start_time=start_time,
            interval_seconds=interval_seconds,
            duration_seconds=duration_seconds,
            request=request,
            connection_id=connection_id
        ):
            yield event
    
    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@streaming_router.get("/stream/batch")
async def stream_multiple_locations(
    request: Request,
    location_ids: str = Query(..., description="Comma-separated list of location IDs"),
    start_time: datetime = Query(..., description="Start time for predictions"),
    interval_seconds: int = Query(default=60, ge=10, le=3600, description="Interval between predictions"),
    duration_seconds: int = Query(default=3600, ge=60, le=86400, description="Total duration to stream"),
    x_api_key: str = Depends(verify_api_key)
):
    """
    Stream predictions for multiple locations using SSE.
    
    Yields predictions for each location at configured intervals.
    
    Args:
        request: FastAPI request object
        location_ids: Comma-separated location IDs
        start_time: Start time for predictions
        interval_seconds: Interval between predictions
        duration_seconds: Total duration to stream
        x_api_key: API key for authentication
        
    Returns:
        SSE event stream with predictions for all locations
    """
    import uuid
    
    # Parse location IDs
    location_list = [loc.strip() for loc in location_ids.split(",")]
    
    if len(location_list) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 locations per stream"
        )
    
    connection_id = str(uuid.uuid4())
    
    # Audit log
    _audit_logger.log_prediction_request(
        location_id=location_ids,
        prediction_time=start_time,
        context_hours=24,
        client_id=x_api_key or "anonymous"
    )
    
    check_rate_limit(x_api_key or "default")
    
    async def multi_location_generator():
        """Generator that streams predictions for multiple locations."""
        model = await get_model()
        collector = await get_collector()
        preprocessor = get_preprocessor()
        cache = get_cache()
        
        start_timestamp = datetime.utcnow()
        stream_end_time = start_timestamp + timedelta(seconds=duration_seconds)
        
        # Send connection confirmation
        yield {
            "event": StreamEventType.CONNECTED.value,
            "data": json.dumps({
                "connection_id": connection_id,
                "location_ids": location_list,
                "start_time": start_timestamp.isoformat(),
                "interval_seconds": interval_seconds,
                "duration_seconds": duration_seconds,
                "message": f"Multi-location stream connected for {len(location_list)} locations"
            })
        }
        
        current_time = start_time
        prediction_count = 0
        
        while datetime.utcnow() < stream_end_time:
            # Check disconnection
            try:
                if await request.is_disconnected():
                    logger.info(f"Multi-location stream disconnected: {connection_id}")
                    break
            except Exception:
                pass
            
            for loc_id in location_list:
                try:
                    cached = cache.get(loc_id, current_time)
                    
                    if cached:
                        yield {
                            "event": StreamEventType.PREDICTION.value,
                            "data": json.dumps({
                                "location_id": loc_id,
                                "prediction": cached.model_dump()
                            })
                        }
                        prediction_count += 1
                    else:
                        # Generate prediction
                        contextual_data = await collector.fetch_contextual_data(
                            location_id=loc_id,
                            prediction_time=current_time,
                            context_hours=24
                        )
                        
                        if contextual_data.historical_availability.records:
                            pred_time = contextual_data.historical_availability.records[-1].timestamp
                        else:
                            pred_time = current_time
                        
                        (
                            event_emb, weather_emb,
                            historical_seq, temporal_enc
                        ) = preprocessor.preprocess(
                            contextual_data.event_calendar,
                            contextual_data.weather,
                            contextual_data.historical_availability,
                            pred_time
                        )
                        
                        model_input = preprocessor.create_model_input(
                            event_emb, weather_emb, historical_seq, temporal_enc
                        )
                        
                        import torch
                        with torch.no_grad():
                            output = model(model_input.unsqueeze(0))
                        
                        prediction = AvailabilityPrediction(
                            probability=output["probability"].item(),
                            confidence_interval=(
                                output["confidence_lower"].item(),
                                output["confidence_upper"].item()
                            ),
                            contributing_factors=output.get("contributing_factors", []),
                            location_id=loc_id,
                            prediction_time=current_time.isoformat(),
                            model_version="1.0.0"
                        )
                        
                        cache.set(loc_id, current_time, prediction)
                        prediction_count += 1
                        
                        yield {
                            "event": StreamEventType.PREDICTION.value,
                            "data": json.dumps({
                                "location_id": loc_id,
                                "prediction": prediction.model_dump()
                            })
                        }
                        
                except Exception as e:
                    logger.error(f"Error predicting for {loc_id}: {e}")
                    yield {
                        "event": StreamEventType.ERROR.value,
                        "data": json.dumps({
                            "location_id": loc_id,
                            "error": str(e)
                        })
                    }
            
            await asyncio.sleep(interval_seconds)
            current_time = current_time + timedelta(seconds=interval_seconds)
        
        # Completion
        yield {
            "event": StreamEventType.COMPLETE.value,
            "data": json.dumps({
                "connection_id": connection_id,
                "total_predictions": prediction_count,
                "locations": location_list,
                "end_time": datetime.utcnow().isoformat()
            })
        }
    
    return EventSourceResponse(
        multi_location_generator(),
        media_type="text/event-stream"
    )


@streaming_router.get("/stream/health")
async def stream_health_status(
    request: Request,
    x_api_key: str = Depends(verify_api_key)
):
    """
    Stream health status updates using SSE.
    
    Provides periodic health check updates for monitoring.
    
    Args:
        request: FastAPI request object
        x_api_key: API key for authentication
        
    Returns:
        SSE event stream with health status updates
    """
    import uuid
    
    connection_id = str(uuid.uuid4())
    
    async def health_generator():
        """Generator for health status updates."""
        yield {
            "event": StreamEventType.CONNECTED.value,
            "data": json.dumps({
                "connection_id": connection_id,
                "message": "Health stream connected",
                "timestamp": datetime.utcnow().isoformat()
            })
        }
        
        while True:
            try:
                if await request.is_disconnected():
                    break
            except Exception:
                pass
            
            try:
                model = await get_model()
                model_loaded = model is not None and hasattr(model, 'transformer')
                
                yield {
                    "event": StreamEventType.HEARTBEAT.value,
                    "data": json.dumps({
                        "status": "healthy" if model_loaded else "degraded",
                        "model_loaded": model_loaded,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                }
            except Exception as e:
                yield {
                    "event": StreamEventType.ERROR.value,
                    "data": json.dumps({
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat()
                    })
                }
            
            await asyncio.sleep(30)
    
    return EventSourceResponse(
        health_generator(),
        media_type="text/event-stream"
    )