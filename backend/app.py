import logging
import time
import sys
import os
import asyncio
from contextlib import asynccontextmanager

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from services.multi_layer_cache import multi_layer_cache
from database.config import Config
from core.middleware.observability import ObservabilityMiddleware

# --- Import V2 Routers ---
from api.v2 import search as search_v2, debug, admin, live, user as user_v2, booking as booking_v2, booking_ws, agent, admin_auth, monitoring, unlock, webhooks, auth_refresh
from api import chat, chat_ws, sos, voice_triage, search, bookings, stations, payments, auth, users, flow, bank_webhooks, admin_refunds, admin_reconciliation, tatkal, telegram_bot, vault

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("api-gateway")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup Logic
    logger.info("🚀 Starting RouteMaster V2 Backend...")
    
    # 1. Initialize Cache
    await multi_layer_cache.initialize()
    
    # 2. Warm up Route Engine (Task 19)
    from core.route_engine import route_engine
    logger.info("📡 Warming up routing graph...")
    # This will trigger snapshot loading/building
    await route_engine._get_current_graph(datetime.utcnow())
    
    # 3. Start Background Workers (Task 7 & 11)
    from workers.worker_pool import worker_pool
    from workers.udp_safety_listener import UDPSafetyListener
    from services.emergency.escalation_service import escalation_service
    
    asyncio.create_task(worker_pool.start_manager())
    
    # [28.3] Start Cleanup Worker
    from workers.cleanup_worker import cleanup_loop
    asyncio.create_task(cleanup_loop())
    
    udp_listener = UDPSafetyListener()
    asyncio.create_task(udp_listener.start())
    
    asyncio.create_task(escalation_service.start())
    logger.info("🚀 SOS Escalation Monitor Started")

    yield
    
    # Shutdown Logic
    logger.info("🛑 Shutting down RouteMaster V2...")
    if multi_layer_cache.redis:
        await multi_layer_cache.redis.close()

app = FastAPI(
    title="RouteMaster V2",
    description="Intelligent, Safe, and Ethical Railway Routing",
    version="2.5.0",
    lifespan=lifespan
)

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ObservabilityMiddleware)

# --- Static Files & Media ---
os.makedirs("media/sos", exist_ok=True)
app.mount("/media", StaticFiles(directory="media"), name="media")

# Standard Error Handler
from starlette.responses import JSONResponse

@app.exception_handler(Exception)
async def unified_exception_handler(request: Request, exc: Exception):
    logger.error(f"UNHANDLED ERROR: {exc}", exc_info=True)
    try:
        debug_val = Config.DEBUG
    except:
        debug_val = False
        
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "A critical system error occurred.",
            "detail": str(exc)
        }
    )

# --- Register Routers ---
app.include_router(search_v2.router, prefix="/api/v2")
app.include_router(live.router, prefix="/api/v2")
app.include_router(monitoring.router, prefix="/api/v2")
app.include_router(user_v2.router, prefix="/api/v2")
app.include_router(booking_v2.router, prefix="/api/v2")
app.include_router(booking_ws.router, prefix="/api/v2")
app.include_router(debug.router, prefix="/api/v2")
app.include_router(admin.router, prefix="/api/v2")
app.include_router(admin_auth.router, prefix="/api/v2")
app.include_router(agent.router, prefix="/api/v2")
app.include_router(unlock.router, prefix="/api/v2")
app.include_router(webhooks.router, prefix="/api/v2")
app.include_router(auth_refresh.router, prefix="/api/v2")

# Legacy V1 Routers
app.include_router(sos.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(chat_ws.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(bookings.router, prefix="/api")
app.include_router(stations.router, prefix="/api")
app.include_router(payments.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(flow.router, prefix="/api")
app.include_router(bank_webhooks.router, prefix="/api")
app.include_router(admin_refunds.router, prefix="/api")
app.include_router(admin_reconciliation.router, prefix="/api")
app.include_router(tatkal.router, prefix="/api")
app.include_router(telegram_bot.router, prefix="/api")
app.include_router(vault.router, prefix="/api")

from datetime import datetime

@app.get("/health")
async def health_check():
    cache_status = "connected" if multi_layer_cache.redis else "disconnected"
    return {
        "status": "healthy",
        "db_mode": "Local SQLite (Physical Split)",
        "cache": cache_status,
        "version": "2.5.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/")
async def root():
    return {"message": "Welcome to RouteMaster V2 API Portal. Use /docs for documentation."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
