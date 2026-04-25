import time
import uvicorn
import uuid
import asyncio
from fastapi import FastAPI, Depends, Query
from typing import Optional, List
from datetime import datetime

# Local imports
from services.search.engine import SearchMicroservice
from core.route_engine import route_engine
from database.session import SessionTransit
from core.system_monitor import system_monitor

app = FastAPI(title="RouteMaster Search Microservice")

async def heartbeat_loop(registry, name, node_id, host, port):
    """
    [Task 4.6] Load-Aware Heartbeat Loop.
    Broadcasting CPU metrics for autonomous rebalancing.
    """
    while True:
        try:
            # Refresh system stats
            await system_monitor.update_if_stale()
            stats = system_monitor.stats
            cpu_load = stats.get("cpu", 0.0)
            
            # Update discovery metadata with real-time load
            await registry.heartbeat_update(name, node_id, {"cpu_load": cpu_load})
            
            # Ensure base registration hasn't expired
            await registry.register(name, node_id, host, port, metadata={"cpu_load": cpu_load})
            
        except Exception as e:
            print(f"❌ Heartbeat Failed for {name}: {e}")
        await asyncio.sleep(10)

@app.on_event("startup")
async def startup_event():
    # Initialize system monitor for the standalone process
    await system_monitor.update_if_stale(force=True)
    
    # Task 7.6: Auto-Registration with Heartbeat
    from core.service_discovery import ServiceRegistry
    from core.lifespan import get_redis
    redis = await get_redis()
    if redis:
        registry = ServiceRegistry(redis)
        # Immediate registration
        await registry.register("search", "search-node-1", "127.0.0.1", 8001)
        # Background heartbeat loop
        asyncio.create_task(heartbeat_loop(registry, "search", "search-node-1", "127.0.0.1", 8001))
        
    print("🚀 Search Microservice Online & Registering Heartbeats.")

import os
NODE_ID = os.getenv("SEARCH_NODE_ID", f"search-{uuid.uuid4().hex[:8]}")

@app.get("/search")
async def execute_search(
    source: str,
    destination: str,
    date: str,
    quota: str = "GN",
    limit: int = 15,
    user_id: Optional[str] = None,
    search_id: Optional[str] = str(uuid.uuid4())
):
    """
    Decoupled Search Endpoint with Shadow Refinement & Rebalancing.
    """
    start_time = time.time()
    dt = datetime.strptime(date, "%Y-%m-%d")
    db = SessionTransit()
    try:
        engine = SearchMicroservice(db, route_engine)
        # 1. Discovery
        from core.route_engine.constraints_engine import ConstraintsEngine
        constraints = ConstraintsEngine.initialize_constraints("comfort", dt.date(), quota=quota)
        
        routes = await engine.execute_discovery(source, destination, dt, constraints, limit=limit*2)
        
        # 2. Verification
        verified = await engine.verify_batch(routes, dt, quota)
        
        # 3. Trigger Shadow Refinement [Task 104] with Autonomous Rebalancing [Task 4.6]
        if user_id and verified:
            # Save Context for Persistence
            from services.session_lock_service import SearchSessionManager
            context = {
                "source": source,
                "destination": destination,
                "date": date,
                "quota": quota,
                "results_preview": [r.to_dict() for r in verified[:3]]
            }
            SearchSessionManager.save_search_context(user_id, search_id, context)

            best_score = verified[0].score if hasattr(verified[0], 'score') else 100.0
            from services.search.shadow_engine import shadow_engine
            
            # Use ShadowEngine with Rebalancing Logic (delegation vs local execution)
            asyncio.create_task(shadow_engine.refine_in_background(
                user_id=user_id,
                search_id=search_id,
                source=source,
                destination=destination,
                travel_date=dt,
                constraints=constraints,
                original_best_score=best_score,
                local_node_id=NODE_ID
            ))

        return {
            "status": "success",
            "search_id": search_id,
            "count": len(verified),
            "results": [r.to_dict() for r in verified[:limit]]
        }
    finally:
        # [Task 4.8] Self-Healing Telemetry: Shed load during DB stress
        from services.cache_service import cache_service
        db_mode = await cache_service.get("DB:OPERATION_MODE")
        
        if db_mode != "READ_ONLY":
            try:
                from database.models import RouteSearchLog
                log = RouteSearchLog(
                    user_id=user_id,
                    src=source,
                    dst=destination,
                    date=dt.date(),
                    latency_ms=(time.time() - start_time) * 1000 if 'start_time' in locals() else 0,
                    created_at=datetime.utcnow()
                )
                db.add(log)
                db.commit()
            except Exception as e:
                print(f"⚠️ Telemetry Persistence Failed: {e}")
        else:
            print("🛡️ [DB_SENTINEL] Load Shedding: Skipping RouteSearchLog during DB Saturation.")
            
        db.close()

@app.post("/internal/shadow-refine")
async def internal_shadow_refine(payload: dict):
    """
    Internal delegation bridge for redistributed background tasks.
    """
    from services.search.shadow_engine import shadow_engine
    # Direct local execution since it was delegated here by a stressed peer
    asyncio.create_task(shadow_engine.refine_in_background(
        user_id=payload["user_id"],
        search_id=payload["search_id"],
        source=payload["source"],
        destination=payload["destination"],
        travel_date=datetime.fromisoformat(payload["travel_date"]),
        constraints=payload["constraints"],
        original_best_score=payload["original_best_score"],
        is_delegated=True # Signal to prevent recursive delegation loops
    ))
    return {"status": "delegation_accepted"}

@app.post("/internal/flex-find")
async def internal_flex_find(payload: dict):
    """
    [Group 1] Internal delegation bridge for FlexRouteAgent.
    Receives requests from stressed peers to find alternative routes locally.
    """
    from services.agents.flex_route_agent import flex_route_agent
    alternatives = await flex_route_agent.find_alternatives(
        source=payload["source"],
        destination=payload["destination"],
        travel_date=payload["travel_date"],
        original_train=payload["original_train"],
        original_class=payload["original_class"],
        is_delegated=True
    )
    return {"alternatives": alternatives}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
