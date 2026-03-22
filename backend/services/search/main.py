import uvicorn
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
    """Keep the service registration alive in Redis."""
    while True:
        try:
            await registry.register(name, node_id, host, port)
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

@app.get("/search")
async def execute_search(
    source: str,
    destination: str,
    date: str,
    quota: str = "GN",
    limit: int = 15
):
    """
    Decoupled Search Endpoint.
    Used by the API Gateway over HTTP/IPC.
    """
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
        
        return {
            "status": "success",
            "count": len(verified),
            "results": [r.to_dict() for r in verified[:limit]]
        }
    finally:
        db.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
