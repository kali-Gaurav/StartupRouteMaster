import logging
import time
import sys
import os
import asyncio
from contextlib import asynccontextmanager

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware

from database.session import init_db
from dependencies import get_route_engine
from services.multi_layer_cache import multi_layer_cache
from database.config import Config
from core.middleware.observability import ObservabilityMiddleware

# --- Import V2 Routers ---
from api.v2 import search as search_v2, debug, admin, live, user as user_v2, booking as booking_v2, booking_ws, agent
from api import chat, chat_ws, sos, voice_triage, search, bookings, stations, payments, auth, users, flow, bank_webhooks, admin_refunds, admin_reconciliation, tatkal, telegram_bot, vault

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("api-gateway")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting RouteMaster V2 Production Gateway...")
    await init_db()
    await multi_layer_cache.initialize()
    
    # Warm up route engine
    logger.info("📡 Warming up routing graph...")
    get_route_engine()
    
    # Task 38: Start Escalation Monitor
    from services.emergency.escalation_service import escalation_service
    await escalation_service.start()
    
    # Task 26/38: Start Booking Worker Pool
    from workers.worker_pool import worker_pool
    await worker_pool.start_manager()
    
    # Task 11: Start UDP Safety Listener
    from workers.udp_safety_listener import UDPSafetyListener
    udp_listener = UDPSafetyListener()
    asyncio.create_task(udp_listener.start())
    app.state.udp_listener = udp_listener
    
    yield
    # Shutdown
    logger.info("🛑 Shutting down Gateway...")
    await escalation_service.stop()
    if hasattr(app.state, 'udp_listener'):
        app.state.udp_listener.stop()

app = FastAPI(
    title="RouteMaster V2 API",
    description="Unified Railway Intelligence Gateway (Search, Real-time, Analytics, Auth Sync)",
    version="2.5.0",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# Suggestion #19: Latency Tracking
# app.add_middleware(ObservabilityMiddleware)

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
            "detail": str(exc) if debug_val else "Please contact support."
        }
    )

# --- Register Routers ---
app.include_router(search_v2.router, prefix="/api/v2")
app.include_router(live.router, prefix="/api/v2")
app.include_router(user_v2.router, prefix="/api/v2")
app.include_router(booking_v2.router, prefix="/api/v2")
app.include_router(booking_ws.router, prefix="/api/v2")
app.include_router(debug.router, prefix="/api/v2")
app.include_router(admin.router, prefix="/api/v2")

# V1 / Legacy / Base Routers (to match frontend expectations)
app.include_router(search.router)      # already has /api/search prefix
app.include_router(bookings.router)    # already has /api/v1/booking prefix
app.include_router(stations.router)    # already has /api/stations prefix
app.include_router(payments.router, prefix="/api") # Router has /payment prefix, becomes /api/payment
app.include_router(auth.router)        # already has /api/auth prefix
app.include_router(users.router, prefix="/api")    # Router has /user prefix, becomes /api/user
app.include_router(sos.router, prefix="/api")   # Router has /sos prefix, becomes /api/sos
app.include_router(flow.router)        # already has /api/flow prefix

app.include_router(chat.router, prefix="/api")
app.include_router(chat_ws.router, prefix="/api")
app.include_router(voice_triage.router)
app.include_router(bank_webhooks.router, prefix="/api")
app.include_router(admin_refunds.router, prefix="/api")
app.include_router(admin_reconciliation.router, prefix="/api")
app.include_router(tatkal.router, prefix="/api")
app.include_router(telegram_bot.router, prefix="/api")
app.include_router(vault.router, prefix="/api")

@app.get("/api/sos/test-route")
async def test_route():
    return {"message": "Root test route works"}

@app.get("/admin/dashboard", tags=["Internal"])
async def serve_dashboard():
    from fastapi.responses import FileResponse
    return FileResponse("monitoring/dashboard.html")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "db_mode": "Local SQLite (Physical Split)",
        "cache": "connected" if multi_layer_cache.redis else "disconnected",
        "version": "2.5.0"
    }

@app.get("/")
async def root():
    return {"message": "Welcome to RouteMaster V2 API Portal. Use /docs for documentation."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=Config.ENVIRONMENT == "development")
