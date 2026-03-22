import uvicorn
import asyncio
import json
import time
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from database.session import get_db
from core.system_monitor import system_monitor

app = FastAPI(title="RouteMaster Analytics Microservice")

STREAM_NAME = "analytics:events"

async def process_event(event: dict):
    """Deep analytics processing (e.g., aggregation, anomaly search)."""
    etype = event.get("type", "unknown")
    logger.info(f"📊 Processing Analytics Event: {etype}")
    # Simulate DB persistence or ML aggregation
    await asyncio.sleep(0.05) 

async def analytics_worker():
    """
    Task 7.5: Redis-Streams Consumer (Message Queue).
    Asynchronously processes events produced by the Gateway.
    """
    from core.lifespan import get_redis
    redis = await get_redis()
    if not redis:
        logger.error("❌ Analytics Worker: Redis unavailable.")
        return

    # Create group if not exists
    try:
        await redis.xgroup_create(STREAM_NAME, "analytics_group", mkstream=True)
    except: pass

    logger.info("👷 Analytics Worker Started. Listening for events...")
    while True:
        try:
            # Read from stream
            messages = await redis.xreadgroup("analytics_group", "worker_1", {STREAM_NAME: ">"}, count=10, block=2000)
            for _, msgs in messages:
                for msg_id, data in msgs:
                    event = json.loads(data[b"payload"])
                    await process_event(event)
                    await redis.xack(STREAM_NAME, "analytics_group", msg_id)
        except Exception as e:
            logger.error(f"Analytics Worker Error: {e}")
            await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    # Task 7.6: Auto-Registration with Heartbeat
    from core.service_discovery import ServiceRegistry
    from core.lifespan import get_redis
    redis = await get_redis()
    if redis:
        registry = ServiceRegistry(redis)
        async def heartbeat():
             while True:
                 await registry.register("analytics", "analytics-node-1", "127.0.0.1", 8004)
                 await asyncio.sleep(10)
        asyncio.create_task(heartbeat())
        asyncio.create_task(analytics_worker())
    
    print("🚀 Analytics Microservice, Worker & Heartbeat Online.")

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "analytics"}

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("routemaster.analytics")
    uvicorn.run(app, host="0.0.0.0", port=8004)
