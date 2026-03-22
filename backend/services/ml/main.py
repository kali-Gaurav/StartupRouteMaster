import uvicorn
from fastapi import FastAPI, Depends, Query
from sqlalchemy.orm import Session
from database.session import get_db
from services.ml.engine import MLMicroservice
from core.service_discovery import ServiceRegistry
from core.lifespan import get_redis

app = FastAPI(title="RouteMaster ML Microservice")

async def heartbeat_loop(registry, name, node_id, host, port):
    while True:
        try:
            await registry.register(name, node_id, host, port)
        except: pass
        await asyncio.sleep(10)

@app.on_event("startup")
async def startup_event():
    # Task 7.6: Auto-Registration with Heartbeat
    redis = await get_redis()
    if redis:
        registry = ServiceRegistry(redis)
        await registry.register("ml", "ml-node-1", "127.0.0.1", 8003)
        asyncio.create_task(heartbeat_loop(registry, "ml", "ml-node-1", "127.0.0.1", 8003))
    print("🚀 ML Microservice Online & Heartbeating.")

@app.get("/predict/delay")
async def predict_delay(
    train_number: str,
    station_code: str,
    db: Session = Depends(get_db)
):
    """
    Decoupled Delay Prediction.
    """
    engine = MLMicroservice(db)
    return await engine.predict_delay(train_number, station_code)

@app.get("/predict/demand")
async def predict_demand(
    train_number: str,
    date: str,
    db: Session = Depends(get_db)
):
    """
    Decoupled Demand Prediction.
    """
    engine = MLMicroservice(db)
    return await engine.predict_tatkal_demand(train_number, date)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
