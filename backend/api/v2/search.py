from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from database.session import get_db, get_transit_db
from services.search_service import SearchService
from dependencies import get_route_engine
from utils.geo_utils import get_state_from_ip
import json
import asyncio
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["Routing & Discovery"])

@router.get("/unified")
async def unified_search(
    request: Request,
    source: str = Query(..., min_length=2),
    destination: str = Query(..., min_length=2),
    date: str = Query(..., description="YYYY-MM-DD"),
    budget: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=50),
    quota: str = "GN",
    db: Session = Depends(get_db)
):
    """
    Primary production endpoint for route search.
    Flow: Redis Cache -> Turbo (Direct) -> FastRouter -> RAPTOR.
    [40.2] Support for page/limit pagination.
    """
    # Subtask 5.2: Geo-location Capture
    client_ip = request.headers.get("x-forwarded-for") or request.client.host
    if "," in client_ip: client_ip = client_ip.split(",")[0]
    geo_state = get_state_from_ip(client_ip)

    # Task 27.2: Surge Protection Throttling
    try:
        from api.v2.admin import get_surge_status
        surge = await get_surge_status(db)
        if surge.get("is_surge"):
            # Introduce a protective delay for non-priority requests
            await asyncio.sleep(2.0)
            logger.info(f"Surge active (Level: {surge.get('surge_intensity')}). Throttling {client_ip}")
    except: pass

    search_svc = SearchService(db)
    result = await search_svc.search_routes(
        source=source,
        destination=destination,
        travel_date=date,
        budget_category=budget,
        page=page,
        limit=limit,
        quota=quota,
        client_ip=client_ip,
        geo_state=geo_state
    )
    return result

@router.get("/stream")
async def streaming_search(
    source: str,
    destination: str,
    date: str,
    budget: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Server-Sent Events (SSE) endpoint for streaming search results.
    """
    search_svc = SearchService(db)

    async def event_generator():
        async for chunk in search_svc.search_routes_stream(source, destination, date, budget):
            yield f"data: {json.dumps(chunk)}\n\n"
            await asyncio.sleep(0.01)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/explain")
async def explain_routing(
    source: str, 
    destination: str, 
    date: str,
    engine=Depends(get_route_engine)
):
    """
    Diagnostic endpoint to see engine-level details.
    """
    return {"message": "Explainer logic here"}
