import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database.session import get_db
from services.auth.engine import AuthMicroservice
from microservices.shared.auth import SharedAuthManager
from core.service_discovery import ServiceRegistry
from core.lifespan import get_redis

app = FastAPI(title="RouteMaster Auth Microservice")

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
        await registry.register("auth", "auth-node-1", "127.0.0.1", 8002)
        asyncio.create_task(heartbeat_loop(registry, "auth", "auth-node-1", "127.0.0.1", 8002))
    print("🚀 Auth Microservice Online & Heartbeating.")

@app.post("/validate")
async def validate_token(request: Request, db: Session = Depends(get_db)):
    """
    Decoupled Token Validation Endpoint.
    Used by the Gateway to verify JWTs and Sync users.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = auth_header.split(" ")[1]
    
    # Task 7.2: Use Auth Microservice Engine
    engine = AuthMicroservice(db)
    result = await engine.validate_token_and_user(token)
    
    return result

@app.post("/report-failure")
async def report_failure(ip: str, db: Session = Depends(get_db)):
    """Rate Limit Failure Reporting."""
    engine = AuthMicroservice(db)
    await engine.report_login_failure(ip)
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
