"""
Route Engine Router - API endpoints for route engine functionality.
Includes location registry endpoint for discovering available locations.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from backend.services.route_engine import route_engine, Journey, RouteSegment

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/routes",
    tags=["route-engine"]
)


class LocationInfo(BaseModel):
    """Information about a location/station."""
    location_id: str
    name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: bool = True
    last_updated: datetime


class LocationListResponse(BaseModel):
    """Response for location list."""
    locations: List[LocationInfo]
    total_count: int
    last_updated: datetime


@router.get("/locations", response_model=LocationListResponse)
async def list_locations(
    active_only: bool = Query(True, description="Filter to active locations only"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of locations to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """
    List all available locations/stations.
    
    Returns information about locations that can be used as source or destination
    for route searches. Locations are cached with periodic refresh.
    """
    try:
        # Get locations from route engine
        locations = await route_engine.get_available_locations(
            active_only=active_only,
            limit=limit,
            offset=offset
        )
        
        return LocationListResponse(
            locations=locations,
            total_count=len(locations),
            last_updated=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Failed to get locations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get locations: {e}")


@router.get("/locations/{location_id}")
async def get_location(
    location_id: str
):
    """
    Get information about a specific location/station.
    
    Args:
        location_id: Location identifier
        
    Returns:
        Location information
    """
    try:
        location = await route_engine.get_location_info(location_id)
        
        if location is None:
            raise HTTPException(status_code=404, detail=f"Location {location_id} not found")
        
        return location
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get location {location_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get location: {e}")


# Add methods to RouteEngine for location management
async def get_available_locations(
    self,
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0
) -> List[LocationInfo]:
    """
    Get list of available locations/stations.
    
    Args:
        active_only: Filter to active locations only
        limit: Maximum number of locations to return
        offset: Offset for pagination
        
    Returns:
        List of LocationInfo objects
    """
    try:
        from database.session import get_db
        db = next(get_db())
        
        # Query distinct stations from routes
        from sqlalchemy import func
        
        # Get source stations
        source_stations = db.query(
            Route.source_code.label("location_id"),
            Route.source_name.label("name"),
            func.max(Route.latitude).label("latitude"),
            func.max(Route.longitude).label("longitude")
        ).group_by(Route.source_code, Route.source_name)
        
        # Get destination stations
        dest_stations = db.query(
            Route.dest_code.label("location_id"),
            Route.dest_name.label("name"),
            func.max(Route.latitude).label("latitude"),
            func.max(Route.longitude).label("longitude")
        ).group_by(Route.dest_code, Route.dest_name)
        
        # Combine and deduplicate
        from sqlalchemy import union_all
        
        all_stations = union_all(
            source_stations,
            dest_stations
        ).subquery()
        
        # Query combined stations
        stations = db.query(
            all_stations.c.location_id,
            all_stations.c.name,
            all_stations.c.latitude,
            all_stations.c.longitude
        ).distinct().order_by(all_stations.c.location_id)
        
        # Apply pagination
        stations = stations.offset(offset).limit(limit).all()
        
        locations = []
        for station in stations:
            locations.append(LocationInfo(
                location_id=station.location_id,
                name=station.name or station.location_id,
                latitude=station.latitude,
                longitude=station.longitude,
                is_active=True,
                last_updated=datetime.utcnow()
            ))
        
        return locations
        
    except Exception as e:
        logger.error(f"Error getting locations: {e}")
        # Fallback to hardcoded locations if database query fails
        return _get_fallback_locations(limit, offset)


async def get_location_info(
    self,
    location_id: str
) -> Optional[LocationInfo]:
    """
    Get information about a specific location.
    
    Args:
        location_id: Location identifier
        
    Returns:
        LocationInfo or None if not found
    """
    try:
        from database.session import get_db
        db = next(get_db())
        
        # Try to find as source station
        route = db.query(Route).filter(
            Route.source_code == location_id
        ).first()
        
        if route:
            return LocationInfo(
                location_id=route.source_code,
                name=route.source_name,
                latitude=route.latitude,
                longitude=route.longitude,
                is_active=True,
                last_updated=datetime.utcnow()
            )
        
        # Try to find as destination station
        route = db.query(Route).filter(
            Route.dest_code == location_id
        ).first()
        
        if route:
            return LocationInfo(
                location_id=route.dest_code,
                name=route.dest_name,
                latitude=route.latitude,
                longitude=route.longitude,
                is_active=True,
                last_updated=datetime.utcnow()
            )
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting location {location_id}: {e}")
        return None


def _get_fallback_locations(
    limit: int = 100,
    offset: int = 0
) -> List[LocationInfo]:
    """Get fallback locations when database is unavailable."""
    # Common Indian railway stations
    fallback_locations = [
        {"code": "NDLS", "name": "New Delhi", "lat": 28.6448, "lon": 77.0669},
        {"code": "BCT", "name": "Mumbai CST", "lat": 18.9684, "lon": 72.8336},
        {"code": "MAS", "name": "Chennai Central", "lat": 13.0878, "lon": 80.2785},
        {"code": "HWH", "name": "Howrah Junction", "lat": 22.5890, "lon": 88.2642},
        {"code": "SC", "name": "Secunderabad", "lat": 17.4333, "lon": 78.4667},
        {"code": "LKO", "name": "Lucknow", "lat": 26.8467, "lon": 80.9467},
        {"code": "JP", "name": "Jaipur", "lat": 26.9124, "lon": 75.7873},
        {"code": "AGC", "name": "Agra Cantt", "lat": 27.1639, "lon": 78.0081},
        {"code": "GKP", "name": "Gorakhpur", "lat": 26.7606, "lon": 83.3683},
        {"code": "PNBE", "name": "Patna", "lat": 25.5941, "lon": 85.1376},
        {"code": "BBS", "name": "Bhubaneswar", "lat": 20.2961, "lon": 85.8245},
        {"code": "BNC", "name": "Bangalore Cantt", "lat": 12.9249, "lon": 77.5780},
        {"code": "KOV", "name": "Kochi", "lat": 9.9312, "lon": 76.2673},
        {"code": "AMD", "name": "Ahmedabad", "lat": 23.0678, "lon": 72.6297},
        {"code": "SUR", "name": "Surat", "lat": 21.1833, "lon": 72.8333},
    ]
    
    # Apply pagination
    paginated = fallback_locations[offset:offset + limit]
    
    locations = []
    for loc in paginated:
        locations.append(LocationInfo(
            location_id=loc["code"],
            name=loc["name"],
            latitude=loc["lat"],
            longitude=loc["lon"],
            is_active=True,
            last_updated=datetime.utcnow()
        ))
    
    return locations


def _get_fallback_locations(
    limit: int = 100,
    offset: int = 0
) -> List[LocationInfo]:
    """Get fallback locations when database is unavailable."""
    # Common Indian railway stations
    fallback_locations = [
        {"code": "NDLS", "name": "New Delhi", "lat": 28.6448, "lon": 77.0669},
        {"code": "BCT", "name": "Mumbai CST", "lat": 18.9684, "lon": 72.8336},
        {"code": "MAS", "name": "Chennai Central", "lat": 13.0878, "lon": 80.2785},
        {"code": "HWH", "name": "Howrah Junction", "lat": 22.5890, "lon": 88.2642},
        {"code": "SC", "name": "Secunderabad", "lat": 17.4333, "lon": 78.4667},
        {"code": "LKO", "name": "Lucknow", "lat": 26.8467, "lon": 80.9467},
        {"code": "JP", "name": "Jaipur", "lat": 26.9124, "lon": 75.7873},
        {"code": "AGC", "name": "Agra Cantt", "lat": 27.1639, "lon": 78.0081},
        {"code": "GKP", "name": "Gorakhpur", "lat": 26.7606, "lon": 83.3683},
        {"code": "PNBE", "name": "Patna", "lat": 25.5941, "lon": 85.1376},
        {"code": "BBS", "name": "Bhubaneswar", "lat": 20.2961, "lon": 85.8245},
        {"code": "BNC", "name": "Bangalore Cantt", "lat": 12.9249, "lon": 77.5780},
        {"code": "KOV", "name": "Kochi", "lat": 9.9312, "lon": 76.2673},
        {"code": "AMD", "name": "Ahmedabad", "lat": 23.0678, "lon": 72.6297},
        {"code": "SUR", "name": "Surat", "lat": 21.1833, "lon": 72.8333},
    ]
    
    # Apply pagination
    paginated = fallback_locations[offset:offset + limit]
    
    locations = []
    for loc in paginated:
        locations.append(LocationInfo(
            location_id=loc["code"],
            name=loc["name"],
            latitude=loc["lat"],
            longitude=loc["lon"],
            is_active=True,
            last_updated=datetime.utcnow()
        ))
    
    return locations


def _get_fallback_location(
    location_id: str
) -> Optional[LocationInfo]:
    """Get fallback location info when database is unavailable."""
    # Common Indian railway stations
    fallback_locations = {
        "NDLS": {"name": "New Delhi", "lat": 28.6448, "lon": 77.0669},
        "BCT": {"name": "Mumbai CST", "lat": 18.9684, "lon": 72.8336},
        "MAS": {"name": "Chennai Central", "lat": 13.0878, "lon": 80.2785},
        "HWH": {"name": "Howrah Junction", "lat": 22.5890, "lon": 88.2642},
        "SC": {"name": "Secunderabad", "lat": 17.4333, "lon": 78.4667},
        "LKO": {"name": "Lucknow", "lat": 26.8467, "lon": 80.9467},
        "JP": {"name": "Jaipur", "lat": 26.9124, "lon": 75.7873},
        "AGC": {"name": "Agra Cantt", "lat": 27.1639, "lon": 78.0081},
        "GKP": {"name": "Gorakhpur", "lat": 26.7606, "lon": 83.3683},
        "PNBE": {"name": "Patna", "lat": 25.5941, "lon": 85.1376},
        "BBS": {"name": "Bhubaneswar", "lat": 20.2961, "lon": 85.8245},
        "BNC": {"name": "Bangalore Cantt", "lat": 12.9249, "lon": 77.5780},
        "KOV": {"name": "Kochi", "lat": 9.9312, "lon": 76.2673},
        "AMD": {"name": "Ahmedabad", "lat": 23.0678, "lon": 72.6297},
        "SUR": {"name": "Surat", "lat": 21.1833, "lon": 72.8333},
    }
    
    if location_id in fallback_locations:
        loc = fallback_locations[location_id]
        return LocationInfo(
            location_id=location_id,
            name=loc["name"],
            latitude=loc["lat"],
            longitude=loc["lon"],
            is_active=True,
            last_updated=datetime.utcnow()
        )
    
    return None


# Monkey-patch methods to RouteEngine
import types
route_engine.get_available_locations = types.MethodType(get_available_locations, route_engine)
route_engine.get_location_info = types.MethodType(get_location_info, route_engine)
route_engine._get_fallback_locations = types.MethodType(_get_fallback_locations, route_engine)
route_engine._get_fallback_location = types.MethodType(_get_fallback_location, route_engine)