
import os
import time
import logging
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Request, HTTPException, Depends
from shared.config import Config
from shared.logging import setup_logging
from shared.models.search import SearchRequest, SearchResponse
import httpx

# Shared imports setup
import sys
from pathlib import Path
shared_path = str(Path(__file__).resolve().parent.parent)
if shared_path not in sys.path:
    sys.path.append(shared_path)

setup_logging("search-service")
logger = logging.getLogger("search-service")

app = FastAPI(title="RouteMaster Search Service")

client = httpx.AsyncClient(timeout=30.0)

@app.on_event("shutdown")
async def shutdown():
    await client.aclose()

@app.get("/health")
async def health():
    return {"status": "ok", "service": "search"}

@app.post("/api/v2/search/unified", response_model=SearchResponse)
async def unified_search(request: SearchRequest):
    logger.info(f"Searching: {request.source} -> {request.destination} on {request.travel_date}")
    
    start_time = time.perf_counter()
    
    # 1. Parallel Calls to Route Service & ML Service
    try:
        # For prototype, we call Route Service
        # In full version, this would be an internal engine call or distributed search
        route_res = await client.post(
            f"{Config.ROUTE_SERVICE_URL}/api/v1/internal/find-routes",
            json=request.dict()
        )
        route_data = route_res.json()
        
        # 2. Score & Refine with ML
        # ml_res = await client.post(...)
        
        duration = (time.perf_counter() - start_time) * 1000
        logger.info(f"Search completed in {duration:.2f}ms")
        
        return SearchResponse(
            routes=route_data.get("routes", []),
            pagination=route_data.get("pagination"),
            metadata={"duration_ms": duration}
        )
    except Exception as e:
        logger.error(f"Search Service Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Search Error")
