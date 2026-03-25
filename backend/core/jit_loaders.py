import logging
import asyncio
from typing import Any

logger = logging.getLogger("jit-loaders")

async def load_database():
    """JIT Loader for Database Connection Pools."""
    from database.session import initialize_database_pools
    logger.info("🗄️ JIT: Initializing Database Pools...")
    await initialize_database_pools()

async def load_cache():
    """JIT Loader for Multi-Layer Cache."""
    from services.multi_layer_cache import multi_layer_cache
    logger.info("🚀 JIT: Initializing Multi-Layer Cache...")
    await multi_layer_cache.initialize()

async def load_route_engine():
    """JIT Loader for Route Engine."""
    from core.route_engine import route_engine
    logger.info("🧠 JIT: Initializing Railway Route Engine...")
    if hasattr(route_engine, '_ensure'):
        route_engine._ensure()

async def load_ml_models():
    """JIT Loader for ML Models."""
    from core.ml_models.loader import model_loader
    logger.info("🤖 JIT: Initializing ML Model Loader...")
    # Trigger base loader
    await model_loader.get_model("mock") 
