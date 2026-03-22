
import os
import time
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Request, HTTPException
from shared.config import Config
from shared.logging import setup_logging
from shared.models.routing import Route as RouteModel, RouteConstraints
from shared.models.search import SearchRequest

# Ensure app root is in sys.path to find core.*
import sys
from pathlib import Path
app_root = str(Path(__file__).resolve().parent)
if app_root not in sys.path:
    sys.path.append(app_root)

setup_logging("route-service")
logger = logging.getLogger("route-service")

app = FastAPI(title="RouteMaster Route Engine Service")

# Engine state
engine = None

@app.on_event("startup")
async def startup():
    global engine
    logger.info("⚡ Route Service: Initializing RAPTOR Engine...")
    try:
        from core.route_engine.raptor import OptimizedRAPTOR
        engine = OptimizedRAPTOR()
        # In a real microservice, we would pre-warm the graph here
        logger.info("✅ Route Service: RAPTOR Engine Ready.")
    except Exception as e:
        logger.error(f"❌ Route Service: Failed to initialize engine: {e}")

@app.get("/health")
async def health():
    return {
        "status": "ok" if engine else "initializing",
        "service": "route-engine",
        "timestamp": time.time()
    }

@app.post("/api/v1/internal/find-routes")
async def find_routes(request: SearchRequest):
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
        
    start_time = time.perf_counter()
    logger.info(f"Engine Search: {request.source} -> {request.destination} (Date: {request.travel_date})")
    
    try:
        from core.route_engine.constraints import RouteConstraints as EngineConstraints
        from core.data_structures import Persona as EnginePersona
        from utils.station_utils import resolve_stations
        from database.session import SessionTransit
        
        db = SessionTransit()
        source_stop, dest_stop = resolve_stations(db, request.source, request.destination)
        
        if not source_stop or not dest_stop:
            return {"routes": [], "error": "Stations not found"}

        constraints = EngineConstraints(
            max_results=request.limit,
            persona=EnginePersona(request.persona or "comfort"),
            quota=request.quota
        )
        
        # Call the actual RAPTOR engine
        routes = await engine.find_routes(
            source_stop_id=source_stop.id,
            dest_stop_id=dest_stop.id,
            departure_date=datetime.combine(request.travel_date, datetime.min.time()),
            constraints=constraints
        )
        
        duration = (time.perf_counter() - start_time) * 1000
        logger.info(f"Engine search completed in {duration:.2f}ms. Found {len(routes)} routes.")
        
        return {
            "routes": [r.to_dict() for r in routes],
            "pagination": {
                "total_results": len(routes),
                "current_page": request.page,
                "limit": request.limit,
                "has_next": False,
                "total_pages": 1
            },
            "engine_duration_ms": duration
        }
    except Exception as e:
        logger.error(f"Engine Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
