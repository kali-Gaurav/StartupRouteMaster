import logging
import asyncio
import gc
from contextlib import asynccontextmanager
from fastapi import FastAPI

from core.orchestrator import orchestrator
from services.jit_manager import jit_manager
from services.storage_sync import r2_sync_manager
from core.jit_loaders import load_database, load_cache, load_route_engine, load_ml_models
from core.auth.provider import auth_service # Register Auth IoC [Task 10]

logger = logging.getLogger("routemaster.lifespan")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Task 2: Modularized Lifespan Manager.
    Handles startup/shutdown orchestration safely and lazily.
    """
    # 1. R2 Sync - Initial Download [Task 11]
    try:
        await r2_sync_manager.full_sync_down()
    except Exception as e:
        logger.error(f"⚠️ R2 Initial Sync Failed (Continuing in local-only mode): {e}")
    
    # 2. Aggressive GC Tuning for VPS [Task 41]
    gc.set_threshold(400, 5, 5)
    
    # 3. Register JIT Nodes -> Now handled by ServiceProvider registration in module imports
    # jit_manager.register_node("DATABASE", [], load_database)
    # jit_manager.register_node("CACHE", [], load_cache)
    # jit_manager.register_node("GRAPH", ["DATABASE", "CACHE"], load_route_engine)
    
    # 4. Register Background Services
    from services.feedback_loop import feedback_loop
    from services.behavior_tracker import behavior_tracker
    from core.metrics import run_event_loop_monitor
    from services.multi_layer_cache import multi_layer_cache
    from utils.http_client import HttpClientManager
    from core.container import container
    
    await HttpClientManager.get_session()
    
    orchestrator.register_task("event_loop_monitor", run_event_loop_monitor, priority=0)
    orchestrator.register_task("r2_periodic_sync", r2_sync_manager.run_periodic_sync, priority=1)
    
    # Note: DB Pool Scaler/Vacuum are now managed within DatabaseServiceProvider.init()
    
    orchestrator.register_task("feedback_punishment", feedback_loop.run_punishment_cycle, priority=2)
    orchestrator.register_task("behavior_cleanup", behavior_tracker.cleanup_idle_states, priority=2)
    orchestrator.register_task("trending_analyzer", multi_layer_cache.warmup.run_trending_analyzer, priority=2)
    
    # ⚡ [TRULY LAZY STARTUP]
    asyncio.create_task(orchestrator.bootstrap())
    
    logger.info("🚀 RouteMaster V2 API Gateway Lifespan: System is Online.")
    yield
    
    # --- GRACEFUL SHUTDOWN ---
    logger.info("🔌 Lifespan: Initiating shutdown...")
    await r2_sync_manager.full_sync_up()
    await orchestrator.shutdown(timeout=5.0)
    await container.shutdown_all() # Shutdown all managed services [Task 8]
    
    try:
        from utils.http_client import HttpClientManager
        await HttpClientManager.close_session()
    except Exception as e:
        logger.warning(f"Shutdown cleanup error: {e}")
        
    gc.collect()
    # [Task 13.1] Final Log Flush
    for handler in logging.getLogger().handlers:
        handler.flush()
    logger.info("🛑 Lifespan: Shutdown complete.")
