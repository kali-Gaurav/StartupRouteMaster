import time
import logging
import json
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from database import get_db
from schemas.unified_search import UnifiedSearchRequest, UnifiedSearchResponse
from core.unified_planner import UnifiedPlanner
from adapters.train_adapter import TrainAdapter
from services.search_service import SearchService
from core.redis import async_redis_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v2/search", tags=["unified"])

@router.post("/unified", response_model=UnifiedSearchResponse)
async def unified_search_endpoint(request: Request, req: UnifiedSearchRequest, db: Session = Depends(get_db)):
    """
    Unified Multi-Modal Search Endpoint (Train + future modes).
    Optimized with Parallel Execution, Pareto-Ranking, and Redis Caching.
    """
    start_time = time.perf_counter()
    
    # 1. Check Redis Cache (Topic 7)
    cache_key = f"unified_v2:{req.source.upper()}:{req.destination.upper()}:{req.date}:{req.preferences}"
    try:
        cached_data = await async_redis_client.get(cache_key)
        if cached_data:
            logger.info(f"CACHE HIT for unified search: {cache_key}")
            data = json.loads(cached_data)
            data["latency_ms"] = (time.perf_counter() - start_time) * 1000
            return data
    except Exception as e:
        logger.warning(f"Cache lookup failed: {e}")

    # 2. Orchestrate Engines
    search_service = SearchService(db)
    train_adapter = TrainAdapter(search_service)
    
    # In Phase 2, we only have Trains active. Bus/Flight added via adapters list.
    planner = UnifiedPlanner(adapters=[train_adapter])
    
    results = await planner.plan(req)
    
    response = UnifiedSearchResponse(
        status="success",
        options=results,
        latency_ms=(time.perf_counter() - start_time) * 1000
    )

    # 3. Store in Cache (5 Minute TTL)
    try:
        # Pydantic v2 use .model_dump_json()
        await async_redis_client.setex(cache_key, 300, response.model_dump_json() if hasattr(response, 'model_dump_json') else response.json())
    except Exception as e:
        logger.warning(f"Failed to cache unified results: {e}")

    return response
