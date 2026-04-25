from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from database.session import get_db, get_transit_db
from services.search_service import SearchService
from dependencies import get_route_engine
from utils.geo_utils import get_state_from_ip
from utils.responses import v3_response, success_response
import json
import asyncio
import logging

from core.nexus.search.interceptor import nexus_interceptor
from core.nexus.search.gate import nexus_latency_gate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["Routing & Discovery"])

@router.get("/engines")
async def list_engines():
    """Lists all available routing engines."""
    engines = [
        {"id": "HubTier0", "name": "Backbone (Hub-to-Hub)", "tier": 0},
        {"id": "Turbo", "name": "Turbo (Direct SQL)", "tier": 1},
        {"id": "UltraTurbo", "name": "UltraTurbo (Vectorized)", "tier": 1},
        {"id": "TBR", "name": "TBR (Trip-Based Router)", "tier": 2},
        {"id": "FastPath", "name": "FastPath (2-Transfer BFS)", "tier": 2},
        {"id": "RAPTOR", "name": "RAPTOR (Discovery)", "tier": 3}
    ]
    return success_response(data={"engines": engines})

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
    engine: Optional[list[str]] = Query(None),
    discovery: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Primary production endpoint for route search.
    """
    client_ip = request.headers.get("x-forwarded-for") or (request.client.host if request.client else "127.0.0.1")
    if "," in client_ip: client_ip = client_ip.split(",")[0]
    geo_state = get_state_from_ip(client_ip)

    # Surge Protection
    try:
        from api.v2.admin import get_surge_status
        surge = await get_surge_status(db)
        if surge.get("is_surge"):
            await asyncio.sleep(1.0)
            logger.info(f"SEARCH_SURGE_THROTTLE | {client_ip} | Intensity: {surge.get('surge_intensity')}")
    except: pass

    # Nexus Security Interceptor
    decision = await nexus_interceptor.intercept(request, source, destination)
    if not decision.allowed:
        logger.warning(f"SEARCH_INTERCEPT | {source}->{destination} | {decision.code}")
        return v3_response(status="HALT", success=False, message=decision.message, data={"code": decision.code})

    # Nexus Latency Gate (Cache)
    if not request.query_params.get("bypass_cache"):
        cached = await nexus_latency_gate.get_cached_search(source, destination, date)
        if cached:
            return v3_response(status="ACTIVE", data={"journeys": cached}, message="L1/L2 Cache Hit")

    search_svc = SearchService(db)
    try:
        from core.metrics import jit_metrics
        adaptive_timeout = jit_metrics.get_adaptive_timeout(base_timeout=60.0)
        
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
                request=request,
                permitted_engines=engine,
                discovery_only=discovery
            ),
            timeout=adaptive_timeout
        )
        return success_response(data=result)
    except asyncio.TimeoutError:
        logger.error(f"SEARCH_V2_TIMEOUT | {source}->{destination}")
        raise HTTPException(status_code=504, detail="Search timed out")
    except Exception as e:
        logger.error(f"SEARCH_V2_ERR | {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search failed")

@router.get("/stream")
async def streaming_search(
    request: Request,
    source: str,
    destination: str,
    date: str,
    budget: Optional[str] = None,
    engine: Optional[list[str]] = Query(None),
    discovery: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Enhanced SSE endpoint."""
    search_svc = SearchService(db)
    from core.metrics import jit_metrics
    
    chunk_size = 3
    if jit_metrics.event_loop_latency_ms > 50 or jit_metrics.cpu_usage_percent > 80:
        chunk_size = 10
    elif jit_metrics.event_loop_latency_ms > 20:
        chunk_size = 5

    async def event_generator():
        try:
            async for chunk in search_svc.search_routes_stream(
                source, destination, date, budget, 
                chunk_size=chunk_size, 
                permitted_engines=engine, 
                discovery_only=discovery
            ):
                if await request.is_disconnected():
                    logger.info(f"STREAM_ABORT | {source}->{destination}")
                    break
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"STREAM_ERR | {e}")
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
        finally:
            logger.info(f"STREAM_CLOSE | {source}->{destination}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/re-rank")
async def re_rank_search(
    session_id: str = Query(...),
    persona: str = Query(...),
    quota: str = Query("GN"),
    db: Session = Depends(get_db)
):
    """Fast re-ranking of results."""
    search_svc = SearchService(db)
    result = await search_svc.re_rank_routes(session_id, persona, quota=quota)
    return success_response(data=result)

@router.get("/explain")
async def explain_routing(
    source: str, 
    destination: str, 
    date: str,
    db: Session = Depends(get_db)
):
    """Diagnostic endpoint to explain zero results."""
    search_svc = SearchService(db)
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
    except:
        dt = datetime.now()
    result = await search_svc.explain_zero_results(source, destination, dt)

