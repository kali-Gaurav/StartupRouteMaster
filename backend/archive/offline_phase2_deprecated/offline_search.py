"""
Offline Route Search API Endpoints

Fast routes using railway_manager.db only.
No external APIs or real-time data.
Route summaries (LOCKED) + full details (UNLOCKED) pattern.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from datetime import datetime, time
from typing import Optional, Dict
import json

from database import get_db
from core.route_engine.offline_engine import (
    OfflineRouteEngine,
    RouteSearchResponse,
    DetailedJourney,
)
from utils.limiter import limiter

router = APIRouter(prefix="/api/offline", tags=["offline-search"])
logger = logging.getLogger(__name__)

# Global offline engine instance (initialized once at startup)
_offline_engine = None


def get_offline_engine() -> OfflineRouteEngine:
    """Get or initialize offline engine."""
    global _offline_engine
    if _offline_engine is None:
        logger.info("Initializing OfflineRouteEngine...")
        _offline_engine = OfflineRouteEngine()
    return _offline_engine


@router.post("/search", response_model=dict)
@limiter.limit("10/minute")
async def search_routes_offline(
    request: Request,
    source_station_code: str,
    destination_station_code: str,
    travel_date: str,  # "YYYY-MM-DD"
    departure_time: Optional[str] = "10:00",  # "HH:MM"
    passengers: Optional[int] = 1,
    max_transfers: Optional[int] = 2,
    db: Session = Depends(get_db)
):
    """
    Search for routes using offline mode (railway_manager.db only).

    Returns route summaries in LOCKED state (click unlock for details).

    Example:
    ```
    POST /api/offline/search
    {
        "source_station_code": "NDLS",
        "destination_station_code": "CSMT",
        "travel_date": "2026-03-01",
        "departure_time": "10:00",
        "passengers": 2,
        "max_transfers": 2
    }
    ```

    Response:
    ```
    {
        "status": "VERIFIED_OFFLINE",
        "mode": "OFFLINE",
        "database": "railway_manager.db",
        "routes": [
            {
                "id": "route_001",
                "from_stop_code": "NDLS",
                "to_stop_code": "CSMT",
                "summary_text": "NDLS 10:00 → CSMT 10:00 (next day)",
                "total_duration_hours": 24,
                "transfers_count": 1,
                "fare_min": 1500,
                "fare_max": 2500,
                "status": "LOCKED",
                "unlock_token": "xxxxxx"
            },
            ...
        ],
        "count": 5,
        "search_time_ms": 4.2
    }
    ```
    """
    try:
        # Parse inputs
        try:
            travel_date_obj = datetime.strptime(travel_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="travel_date must be YYYY-MM-DD format"
            )

        try:
            dep_time_obj = datetime.strptime(departure_time, "%H:%M").time()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="departure_time must be HH:MM format"
            )

        # Get offline engine
        engine = get_offline_engine()

        # Execute search
        logger.info(
            f"Offline search: {source_station_code} → {destination_station_code} "
            f"on {travel_date} at {departure_time}"
        )

        response = await engine.search_routes(
            source_station_code=source_station_code,
            destination_station_code=destination_station_code,
            travel_date=travel_date_obj,
            departure_time=dep_time_obj,
            passengers=passengers,
            max_transfers=max_transfers,
        )

        # Convert to dict for JSON response
        return {
            "status": response.status,
            "mode": response.mode,
            "database": response.database,
            "timestamp": response.timestamp,
            "source_station": response.source_station,
            "destination_station": response.destination_station,
            "travel_date": response.travel_date,
            "departure_time": response.departure_time,
            "routes": [
                {
                    "id": route.route_id,
                    "from_stop_code": route.from_stop_code,
                    "to_stop_code": route.to_stop_code,
                    "from_stop_name": route.from_stop_name,
                    "to_stop_name": route.to_stop_name,
                    "departure_time": route.departure_time.isoformat(),
                    "arrival_time": route.arrival_time.isoformat(),
                    "summary_text": route.summary_text,
                    "total_duration_hours": route.total_duration_hours,
                    "total_duration_minutes": route.total_duration_minutes,
                    "transfers_count": route.transfers_count,
                    "fare_min": route.fare_min,
                    "fare_max": route.fare_max,
                    "segments_count": route.segments_count,
                    "status": route.status,
                    "unlock_token": route.unlock_token,
                    "reliability_score": route.reliability_score,
                }
                for route in response.routes
            ],
            "count": response.count,
            "search_time_ms": response.search_time_ms,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Offline search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.post("/routes/{route_id}/unlock", response_model=dict)
@limiter.limit("10/minute")
async def unlock_route_details(
    route_id: str,
    unlock_token: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Unlock full journey details for a specific route.

    Called when user clicks "Unlock Details" button.
    Performs complete verification of all segments and transfers.

    Example:
    ```
    POST /api/offline/routes/route_001/unlock
    {
        "unlock_token": "xxxxxx"
    }
    ```

    Response:
    ```
    {
        "status": "VERIFIED_OFFLINE",
        "route_id": "route_001",
        "segments": [
            {
                "segment_id": "seg_001",
                "from_stop_code": "NDLS",
                "to_stop_code": "AGC",
                "train_number": "IR101",
                "train_name": "Rajdhani Express",
                "departure_time": "10:00",
                "arrival_time": "13:30",
                "duration_minutes": 210,
                "coaches": ["A1", "A2", "B1"],
                "class_availability": {
                    "AC_1": {"seats": 5, "fare": 2500},
                    "AC_2": {"seats": 12, "fare": 1800}
                },
                "fare_min": 1800,
                "fare_max": 2500,
                "distance_km": 235.5
            },
            ...
        ],
        "transfers": [
            {
                "from_arrival_time": "13:30",
                "from_arrival_station": "AGC",
                "to_departure_time": "16:00",
                "to_departure_station": "AGC",
                "waiting_time_minutes": 150,
                "risk_level": "SAFE",
                "walking_time_minutes": 5,
                "transfer_distance_km": 0.5,
                "notes": "Comfortable transfer time"
            }
        ],
        "total_fare": 4300,
        "total_duration_minutes": 1440,
        "total_transfers": 1,
        "route_reliability": 0.98,
        "verified_at": "2026-02-20T14:30:00Z",
        "verification_details": {
            "all_segments_verified": true,
            "all_transfers_feasible": true,
            "seats_available": true,
            "fares_matched": true
        }
    }
    ```
    """
    try:
        logger.info(f"Unlocking route {route_id}")

        # Get offline engine
        engine = get_offline_engine()

        # Execute unlock
        journey = await engine.verify_and_unlock_route(route_id, unlock_token)

        if journey.status == "ERROR":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Route not found or unlock token invalid"
            )

        # Format response
        return {
            "status": journey.status,
            "route_id": journey.route_id,
            "segments": [
                {
                    "segment_id": seg.segment_id,
                    "from_stop_code": seg.from_stop_code,
                    "from_stop_name": seg.from_stop_name,
                    "to_stop_code": seg.to_stop_code,
                    "to_stop_name": seg.to_stop_name,
                    "train_number": seg.train_number,
                    "train_name": seg.train_name,
                    "departure_time": seg.departure_time.isoformat(),
                    "arrival_time": seg.arrival_time.isoformat(),
                    "duration_minutes": seg.duration_minutes,
                    "coaches": seg.coaches,
                    "class_availability": seg.class_availability,
                    "fare_min": seg.fare_min,
                    "fare_max": seg.fare_max,
                    "distance_km": seg.distance_km,
                }
                for seg in journey.segments
            ],
            "transfers": [
                {
                    "from_arrival_time": t.from_arrival_time.isoformat(),
                    "from_arrival_station": t.from_arrival_station,
                    "to_departure_time": t.to_departure_time.isoformat(),
                    "to_departure_station": t.to_departure_station,
                    "waiting_time_minutes": t.waiting_time_minutes,
                    "risk_level": t.risk_level,
                    "walking_time_minutes": t.walking_time_minutes,
                    "transfer_distance_km": t.transfer_distance_km,
                    "notes": t.notes,
                }
                for t in journey.transfers
            ],
            "total_fare": journey.total_fare,
            "total_duration_minutes": journey.total_duration_minutes,
            "total_transfers": journey.total_transfers,
            "route_reliability": journey.route_reliability,
            "verified_at": journey.verified_at,
            "verification_details": journey.verification_details,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unlock failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unlock failed: {str(e)}"
        )


@router.get("/status", response_model=dict)
@limiter.limit("20/minute")
async def get_offline_status(request: Request):
    """
    Get status of offline system.

    Returns:
    ```
    {
        "mode": "OFFLINE",
        "status": "READY",
        "database": "railway_manager.db",
        "graph_snapshot": "loaded",
        "stations_cached": 5234,
        "trips_cached": 8932,
        "calendars_cached": 156,
        "cache_size_routes": 1250,
        "timestamp": "2026-02-20T14:30:00Z"
    }
    ```
    """
    try:
        engine = get_offline_engine()
        status_info = await engine.get_offline_status()
        return status_info

    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return {
            "mode": "OFFLINE",
            "status": "ERROR",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/health", response_model=dict)
async def offline_health_check():
    """
    Simple health check for offline system.

    Returns: {"status": "ok"} if running
    """
    try:
        engine = get_offline_engine()
        if engine.station_cache:
            return {"status": "ok", "message": "Offline engine ready"}
        else:
            return {"status": "warming_up", "message": "Loading caches"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "error", "message": str(e)}
