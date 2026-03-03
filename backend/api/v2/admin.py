from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from typing import Dict, List, Any
from services.multi_layer_cache import multi_layer_cache
from dependencies import get_route_engine, get_db
from datetime import datetime
from sqlalchemy.orm import Session
import time
import asyncio
import json
import logging

logger = logging.getLogger(__name__)
start_time = time.time()

router = APIRouter(prefix="/admin", tags=["System Administration"])

@router.post("/cache/clear")
async def clear_cache():
    """Clear all Redis cache layers."""
    await multi_layer_cache.initialize()
    if not multi_layer_cache.redis:
        raise HTTPException(status_code=500, detail="Redis not connected")
    
    await multi_layer_cache.redis.flushall()
    return {"message": "Redis cache cleared successfully"}

@router.post("/graph/rebuild")
async def rebuild_graph(engine=Depends(get_route_engine)):
    """Force a fresh build of the memory-resident graph snapshot."""
    await engine.rebuild_snapshot(datetime.now())
    return {"message": "Graph rebuild triggered", "timestamp": datetime.now()}

@router.get("/system/health")
async def get_system_health():
    """Aggregate CPU, RAM, and DB disk usage (TODO #12)."""
    import psutil
    import os
    
    def get_dir_size(path):
        total = 0
        try:
            if not os.path.exists(path): return 0
            for entry in os.scandir(path):
                if entry.is_file(): total += entry.stat().size
                elif entry.is_dir(): total += get_dir_size(entry.path)
        except: pass
        return total

    return {
        "cpu_usage_percent": psutil.cpu_percent(),
        "memory_info": psutil.virtual_memory()._asdict(),
        "db_storage_bytes": get_dir_size("backend/database"),
        "uptime_seconds": time.time() - start_time
    }

@router.get("/cache/stats")
async def get_cache_stats():
    """Visualize Redis hit/miss ratios (TODO #13)."""
    await multi_layer_cache.initialize()
    # Simple aggregation from metrics
    return {
        "infrastructure": multi_layer_cache.metrics['infrastructure_cache'].__dict__,
        "query": multi_layer_cache.metrics['query_cache'].__dict__,
        "availability": multi_layer_cache.metrics['availability_cache'].__dict__
    }

@router.get("/etl/status")
async def get_etl_status(db: Session = Depends(get_db)):
    """Show the latest ETLMetadata runs and sync progress (TODO #16)."""
    from database.models import ETLMetadata
    runs = db.query(ETLMetadata).order_by(ETLMetadata.updated_at.desc()).limit(10).all()
    return runs

@router.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    """
    Push real-time system metrics to dashboard via WebSocket (Suggestion #1).
    """
    await websocket.accept()
    import psutil
    try:
        while True:
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory().percent
            
            p50, p99 = 0, 0
            try:
                await multi_layer_cache.initialize()
                if multi_layer_cache.redis:
                    curr_min = int(time.time() // 60)
                    # Fetch last 2 minutes of latencies
                    keys = [f"metrics:latency:{m}" for m in range(curr_min-1, curr_min+1)]
                    all_latencies = []
                    for k in keys:
                        vals = await multi_layer_cache.redis.zrange(k, 0, -1, withscores=True)
                        all_latencies.extend([float(s) for _, s in vals])
                    
                    if all_latencies:
                        all_latencies.sort()
                        p50 = all_latencies[len(all_latencies)//2]
                        p99 = all_latencies[int(len(all_latencies)*0.99)]
            except Exception as e:
                logger.error(f"WS Metric Error: {e}")

            await websocket.send_json({
                "cpu": cpu,
                "mem": mem,
                "p50": round(p50, 2),
                "p99": round(p99, 2),
                "timestamp": datetime.utcnow().isoformat()
            })
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        logger.info("Metrics WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
