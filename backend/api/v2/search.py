from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from database.session import get_db, get_transit_db
from services.search_service import SearchService
from dependencies import get_route_engine
import json
import asyncio

router = APIRouter(prefix="/search", tags=["Routing & Discovery"])

@router.get("/unified")
async def unified_search(
    source: str = Query(..., min_length=2),
    destination: str = Query(..., min_length=2),
    date: str = Query(..., description="YYYY-MM-DD"),
    budget: Optional[str] = None,
    limit: int = 15,
    db: Session = Depends(get_db)
):
    """
    Primary production endpoint for route search.
    Flow: Redis Cache -> Turbo (Direct) -> FastRouter -> RAPTOR.
    Includes Result Fingerprinting (Upgrade Suggestion #2).
    """
    search_svc = SearchService(db)
    result = await search_svc.search_routes(
        source=source,
        destination=destination,
        travel_date=date,
        budget_category=budget,
        limit=limit
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
    Delivers journeys as found by different engines (Upgrade Suggestion #5).
    """
    search_svc = SearchService(db)

    async def event_generator():
        async for chunk in search_svc.search_routes_stream(source, destination, date, budget):
            # Format as SSE event
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
