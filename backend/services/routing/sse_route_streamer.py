"""
SSE Progressive Route Delivery Service

Implements Server-Sent Events for streaming route results progressively.
First route delivered in < 500ms, transfer routes stream as found.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Set
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from backend.services.route_engine import RouteEngine, Journey, RouteSegment
from backend.services.routing.delay_aware import DelayAwareRoutingService

# Import security middleware
from backend.api.middleware.security import (
    validate_station_code,
    validate_travel_date,
    get_current_user,
    generate_secure_connection_id,
    log_audit_event
)

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """SSE event types for route streaming"""
    ROUTE_FOUND = "route_found"
    SEARCH_PROGRESS = "search_progress"
    SEARCH_COMPLETE = "search_complete"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


@dataclass
class StreamedRoute:
    """A route being streamed to the client"""
    journey: Journey
    event_type: EventType = EventType.ROUTE_FOUND
    sequence: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamConfig:
    """Configuration for route streaming"""
    include_direct_routes: bool = True
    include_transfer_routes: bool = True
    max_routes: int = 10
    stream_timeout_seconds: int = 30
    heartbeat_interval_seconds: int = 30
    direct_route_priority: bool = True  # Stream direct routes first


class RouteStreamManager:
    """
    Manages SSE streaming of route search results.
    
    Features:
    - Progressive delivery of routes as they're found
    - Direct routes prioritized and streamed first
    - Heartbeat to maintain connection
    - Connection resilience with automatic reconnection support
    """
    
    def __init__(self, route_engine: RouteEngine):
        self.route_engine = route_engine
        self.delay_router = DelayAwareRoutingService()
        self._active_streams: Dict[str, Set[str]] = {}  # connection_id -> event_types
        self._stream_counters: Dict[str, int] = {}
    
    async def stream_routes(
        self,
        source: str,
        destination: str,
        travel_date: str,
        config: StreamConfig,
        connection_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream routes progressively to the client.
        
        Args:
            source: Source station code
            destination: Destination station code
            travel_date: Travel date in YYYY-MM-DD format
            config: Streaming configuration
            connection_id: Unique connection identifier
            
        Yields:
            SSE events with route data or status updates
        """
        self._active_streams[connection_id] = set()
        self._stream_counters[connection_id] = 0
        
        try:
            # Send initial connection confirmation
            yield self._create_event(
                event_type=EventType.SEARCH_PROGRESS,
                data={
                    "status": "started",
                    "message": "Route search initiated",
                    "connection_id": connection_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            routes_found = []
            direct_routes = []
            transfer_routes = []
            
            # Phase 1: Search and stream direct routes first (if enabled)
            if config.include_direct_routes:
                direct_routes = await self._search_direct_routes_streaming(
                    source, destination, travel_date, config, connection_id
                )
                for route in direct_routes:
                    routes_found.append(route)
                    yield self._create_event(
                        event_type=EventType.ROUTE_FOUND,
                        data=self._serialize_route(route, len(routes_found))
                    )
            
            # Phase 2: Search and stream transfer routes (if enabled)
            if config.include_transfer_routes and len(routes_found) < config.max_routes:
                remaining_slots = config.max_routes - len(routes_found)
                transfer_routes = await self._search_transfer_routes_streaming(
                    source, destination, travel_date, config, connection_id,
                    already_found=len(routes_found)
                )
                for route in transfer_routes[:remaining_slots]:
                    routes_found.append(route)
                    yield self._create_event(
                        event_type=EventType.ROUTE_FOUND,
                        data=self._serialize_route(route, len(routes_found))
                    )
            
            # Send completion event
            yield self._create_event(
                event_type=EventType.SEARCH_COMPLETE,
                data={
                    "status": "complete",
                    "total_routes": len(routes_found),
                    "direct_routes": len(direct_routes),
                    "transfer_routes": len(transfer_routes),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
        except asyncio.CancelledError:
            logger.info(f"Stream cancelled for connection {connection_id}")
            yield self._create_event(
                event_type=EventType.ERROR,
                data={
                    "status": "cancelled",
                    "message": "Search was cancelled by client"
                }
            )
        except Exception as e:
            logger.error(f"Error streaming routes for {connection_id}: {e}")
            yield self._create_event(
                event_type=EventType.ERROR,
                data={
                    "status": "error",
                    "message": str(e),
                    "error_type": type(e).__name__
                }
            )
        finally:
            # Cleanup
            if connection_id in self._active_streams:
                del self._active_streams[connection_id]
            if connection_id in self._stream_counters:
                del self._stream_counters[connection_id]
    
    async def _search_direct_routes_streaming(
        self,
        source: str,
        destination: str,
        travel_date: str,
        config: StreamConfig,
        connection_id: str
    ) -> List[Journey]:
        """
        Search direct routes with streaming updates.
        Direct routes should be found and streamed quickly (< 500ms target).
        """
        try:
            # Use delay-aware router for real-time information
            direct_routes = await self.delay_router.search_direct_routes(
                source=source,
                destination=destination,
                travel_date=travel_date
            )
            
            # Sort by quality score for best routes first
            direct_routes.sort(
                key=lambda j: self.route_engine._calculate_route_quality_score(j),
                reverse=True
            )
            
            return direct_routes[:config.max_routes]
            
        except Exception as e:
            logger.error(f"Error searching direct routes: {e}")
            return []
    
    async def _search_transfer_routes_streaming(
        self,
        source: str,
        destination: str,
        travel_date: str,
        config: StreamConfig,
        connection_id: str,
        already_found: int = 0
    ) -> List[Journey]:
        """
        Search transfer routes with streaming updates.
        Stream each route as it's found to improve perceived performance.
        """
        try:
            # Use RAPTOR algorithm for multi-hop routes
            transfer_routes = await self.route_engine._raptor_search(
                source=source,
                destination=destination,
                travel_date=travel_date,
                max_transfers=2
            )
            
            # Filter out routes that are too similar to already found routes
            unique_routes = self._filter_unique_routes(
                transfer_routes, 
                already_found
            )
            
            # Sort by quality score
            unique_routes.sort(
                key=lambda j: self.route_engine._calculate_route_quality_score(j),
                reverse=True
            )
            
            return unique_routes
            
        except Exception as e:
            logger.error(f"Error searching transfer routes: {e}")
            return []
    
    def _filter_unique_routes(
        self,
        routes: List[Journey],
        min_unique_score_diff: int = 30
    ) -> List[Journey]:
        """
        Filter routes to ensure uniqueness.
        Remove routes that are too similar in terms of train combinations.
        """
        if not routes:
            return []
        
        unique_routes = []
        seen_train_combos = set()
        
        for route in routes:
            # Create a signature based on train numbers
            train_combo = tuple(
                segment.train_number for segment in route.segments
            )
            
            if train_combo not in seen_train_combos:
                seen_train_combos.add(train_combo)
                unique_routes.append(route)
        
        return unique_routes
    
    def _serialize_route(self, route: Journey, sequence: int) -> Dict[str, Any]:
        """Serialize a journey for SSE transmission"""
        return {
            "sequence": sequence,
            "train_count": len(route.segments),
            "total_duration_minutes": route.total_duration_minutes,
            "departure_time": route.departure_time.isoformat() if route.departure_time else None,
            "arrival_time": route.arrival_time.isoformat() if route.arrival_time else None,
            "transfers": len(route.segments) - 1,
            "segments": [
                {
                    "train_number": seg.train_number,
                    "train_name": seg.train_name,
                    "from_station": seg.from_station,
                    "to_station": seg.to_station,
                    "departure_time": seg.departure_time.isoformat() if seg.departure_time else None,
                    "arrival_time": seg.arrival_time.isoformat() if seg.arrival_time else None,
                    "duration_minutes": seg.duration_minutes,
                    "classes": seg.available_classes if seg.available_classes else []
                }
                for seg in route.segments
            ],
            "quality_score": self.route_engine._calculate_route_quality_score(route),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _create_event(
        self,
        event_type: EventType,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create an SSE event dictionary"""
        return {
            "event": event_type.value,
            "data": json.dumps(data),
            "id": f"{datetime.utcnow().timestamp()}"
        }
    
    async def heartbeat(self, connection_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Send periodic heartbeat to keep connection alive"""
        while connection_id in self._active_streams:
            yield self._create_event(
                event_type=EventType.HEARTBEAT,
                data={
                    "timestamp": datetime.utcnow().isoformat(),
                    "connection_id": connection_id
                }
            )
            await asyncio.sleep(30)  # Heartbeat every 30 seconds


# FastAPI Router for SSE endpoints
sse_router = APIRouter(prefix="/routes", tags=["Route Streaming"])


@sse_router.get("/search/stream")
async def stream_route_search(
    request: Request,
    source: str,
    destination: str,
    travel_date: str,
    max_routes: int = 10,
    include_transfers: bool = True,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    SSE endpoint for progressive route search.
    
    Streams routes as they're found, starting with direct routes.
    
    Query Parameters:
    - source: Source station code (e.g., 'NDLS')
    - destination: Destination station code (e.g., 'BCT')
    - travel_date: Travel date in YYYY-MM-DD format
    - max_routes: Maximum number of routes to return (default: 10)
    - include_transfers: Include routes with transfers (default: True)
    
    Event Types:
    - route_found: A new route has been found
    - search_progress: Status update on search progress
    - search_complete: All routes have been found
    - error: An error occurred during search
    - heartbeat: Keep-alive signal
    
    Authentication: Required (JWT Bearer token)
    """
    # Validate inputs
    validate_station_code(source, "source")
    validate_station_code(destination, "destination")
    validate_travel_date(travel_date)
    
    # Validate max_routes
    if max_routes < 1 or max_routes > 50:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "VALIDATION_ERROR",
                "message": "max_routes must be between 1 and 50"
            }
        )
    
    # Create stream configuration
    config = StreamConfig(
        include_direct_routes=True,
        include_transfer_routes=include_transfers,
        max_routes=max_routes,
        stream_timeout_seconds=30
    )
    
    # Generate secure connection ID
    connection_id = generate_secure_connection_id(
        f"{source.upper()}-{destination.upper()}"
    )
    
    # Get route engine instances
    route_engine = RouteEngine()
    delay_router = DelayAwareRouter()
    stream_manager = RouteStreamManager(route_engine, delay_router)
    
    # Log audit event
    log_audit_event(
        request,
        "route_search_stream",
        {
            "source": source.upper(),
            "destination": destination.upper(),
            "travel_date": travel_date,
            "max_routes": max_routes,
            "connection_id": connection_id
        }
    )
    
    # Create streaming response
    async def event_generator():
        try:
            async for event in stream_manager.stream_routes(
                source=source.upper(),
                destination=destination.upper(),
                travel_date=travel_date,
                config=config,
                connection_id=connection_id
            ):
                # Check if client disconnected
                if await request.is_disconnected():
                    break
                yield event
            
            # Send heartbeat until connection closes
            async for heartbeat in stream_manager.heartbeat(connection_id):
                if await request.is_disconnected():
                    break
                yield heartbeat
        except Exception as e:
            # Log error and yield error event
            logger.error(f"SSE stream error for {connection_id}: {e}")
            yield {
                "event": "error",
                "data": json.dumps({
                    "status": "error",
                    "message": "An error occurred during search"
                })
            }
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


# Legacy REST endpoint for non-SSE clients
@sse_router.get("/search")
async def search_routes_legacy(
    source: str,
    destination: str,
    travel_date: str,
    max_routes: int = 10
):
    """
    Legacy REST endpoint for route search.
    Use SSE endpoint for better performance and progressive delivery.
    """
    route_engine = RouteEngine()
    delay_router = DelayAwareRouter()
    stream_manager = RouteStreamManager(route_engine, delay_router)
    
    config = StreamConfig(
        include_direct_routes=True,
        include_transfer_routes=True,
        max_routes=max_routes
    )
    
    # Collect all routes synchronously
    routes = []
    async for event in stream_manager.stream_routes(
        source=source,
        destination=destination,
        travel_date=travel_date,
        config=config,
        connection_id=f"rest-{datetime.utcnow().timestamp()}"
    ):
        if event["event"] == "route_found":
            routes.append(json.loads(event["data"]))
    
    return {
        "source": source,
        "destination": destination,
        "travel_date": travel_date,
        "routes": routes,
        "total_routes": len(routes)
    }