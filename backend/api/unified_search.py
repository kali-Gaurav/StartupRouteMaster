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
from services.multi_layer_cache import multi_layer_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v2/search", tags=["unified"])

@router.post("/unified", response_model=UnifiedSearchResponse)
async def unified_search_endpoint(request: Request, req: UnifiedSearchRequest, db: Session = Depends(get_db)):
    """
    Unified Multi-Modal Search Endpoint (Train + future modes).
    Optimized with Parallel Execution, Pareto-Ranking, and Redis Caching.
    """
    start_time = time.perf_counter()
    
    # 1. Check Multi-Layer Cache (L1 Memory + L2 Redis)
    cache_key = f"unified_v2:{req.source.upper()}:{req.destination.upper()}:{req.date}:{req.preferences}"
    try:
        data = await multi_layer_cache.get(cache_key)
        if data:
            logger.info(f"CACHE HIT for unified search: {cache_key}")
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

    # 3. Store in Multi-Layer Cache (5 Minute TTL)
    try:
        await multi_layer_cache.put(cache_key, response.model_dump() if hasattr(response, 'model_dump') else response.dict(), ttl=300)
    except Exception as e:
        logger.warning(f"Failed to cache unified results: {e}")

    return response
