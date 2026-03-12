from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from database.session import get_db, get_transit_db
from services.search_service import SearchService
from dependencies import get_route_engine
from utils.geo_utils import get_state_from_ip
from utils.responses import SafeJSONResponse
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
    cursor: Optional[float] = Query(None, description="Score cursor for pagination"),
    quota: str = "GN",
    db: Session = Depends(get_db)
):
    """
    Primary production endpoint for route search.
    Flow: Redis Cache -> Turbo (Direct) -> FastRouter -> RAPTOR.
    [1.1] Support for cursor-based pagination.
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

    # [38.2] Payload Sanitization
    from utils.security import sanitize_string
    source = sanitize_string(source, length_limit=10)
    destination = sanitize_string(destination, length_limit=10)

    search_svc = SearchService(db)
    try:
        from core.metrics import jit_metrics
        adaptive_timeout = jit_metrics.get_adaptive_timeout(base_timeout=30.0)
        
        result = await asyncio.wait_for(
            search_svc.search_routes(
                source=source,
                destination=destination,
                travel_date=date,
                budget_category=budget,
                page=page,
                limit=limit,
                cursor=cursor,
                quota=quota,
                client_ip=client_ip,
                geo_state=geo_state,
                request=request # Pass request for disconnection detection
            ),
            timeout=adaptive_timeout # Subtask 1.3: Adaptive Timeout
        )
        return result
    except asyncio.TimeoutError:
        logger.error(f"Unified Search timed out for {source}->{destination}")
        return SafeJSONResponse(
            status_code=504,
            content={"error": True, "message": "Search processing timed out. Please try again later."}
        )

@router.get("/stream")
async def streaming_search(
    request: Request,
    source: str,
    destination: str,
    date: str,
    budget: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    [Subtask 1.6/1.13] Enhanced SSE endpoint with dynamic chunk sizing.
    """
    search_svc = SearchService(db)
    from core.metrics import jit_metrics
    
    # [1.13] Calculate optimal chunk size
    # Low Load: 1-2 items (fastest interactivity)
    # High Load: 5-10 items (best throughput/efficiency)
    chunk_size = 3
    if jit_metrics.event_loop_latency_ms > 50 or jit_metrics.cpu_usage_percent > 80:
        chunk_size = 10
    elif jit_metrics.event_loop_latency_ms > 20:
        chunk_size = 5

    async def event_generator():
        try:
            async for chunk in search_svc.search_routes_stream(source, destination, date, budget, chunk_size=chunk_size):
                # 1. Disconnection Check
                if await request.is_disconnected():
                    logger.info("🛑 Streaming aborted: Client disconnected.")
                    break
                
                # 2. Emit Data
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0.01)
                
        except Exception as e:
            logger.error(f"❌ Streaming Error: {e}", exc_info=True)
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
        finally:
            logger.info(f"Stream closed for {source}->{destination}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/re-rank")
async def re_rank_search(
    session_id: str = Query(...),
    persona: str = Query(..., description="budget, comfort, emergency, family"),
    quota: str = Query("GN", description="GN, TQ, PT"),
    db: Session = Depends(get_db)
):
    """
    [10.5] Fast re-ranking of existing session results.
    [18.3] Now supports quota-segmented pools.
    """
    search_svc = SearchService(db)
    result = await search_svc.re_rank_routes(session_id, persona, quota=quota)
    return result

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
