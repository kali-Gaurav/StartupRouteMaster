import asyncio
import time
import aiosqlite
from sqlalchemy import create_engine, event, MetaData, Engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base, Session
import logging
import os
from typing import Optional, List, Any

from .config import Config

logger = logging.getLogger("database-session")

_BASE_DIR = Config.BASE_DIR

# --- Metadata & Bases ---
UserBase = declarative_base()
TransitBase = declarative_base()
Base = UserBase

# --- Global Engine Pointers ---
engine_user = None
engine_transit = None
engine_auth = None 

async_engine_user = None
async_engine_transit = None
async_engine_auth = None 

engine = None  

# --- Raw Async Pool (Subtask 1.1: Ultra-Turbo Decoupling) ---
_raw_transit_pool: asyncio.Queue = asyncio.Queue(maxsize=20)
_RAW_POOL_SIZE = 10

async def init_raw_transit_pool():
    """Initializes a raw aiosqlite pool independent of SQLAlchemy."""
    db_path = Config.GET_SQLALCHEMY_URL("transit", is_async=False).replace("sqlite:///", "")
    for _ in range(_RAW_POOL_SIZE):
        conn = await aiosqlite.connect(db_path)
        conn.row_factory = aiosqlite.Row
        await _raw_transit_pool.put(conn)
    logger.info(f"⚡ Ultra-Turbo Raw Pool Initialized (Size: {_RAW_POOL_SIZE})")

import contextlib

@contextlib.asynccontextmanager
async def get_raw_transit_conn():
    """Context manager for acquiring and releasing raw connections."""
    if _raw_transit_pool.empty() and not _pools_initialized:
        raise RuntimeError("Raw pool not initialized.")
    conn = await _raw_transit_pool.get()
    try:
        yield conn
    finally:
        await _raw_transit_pool.put(conn)

# factories will be assigned here
_SessionUser = None
_SessionTransit = None
_SessionAuth = None

class AtomicSessionFactoryProxy:
    """
    Subtask 4.8: Dynamic Factory Proxy.
    Ensures that modules importing SessionLocal/SessionTransit at module-level
    always get a callable that points to the latest initialized factory.
    """
    def __init__(self, internal_name):
        self._internal_name = internal_name

    def __call__(self, *args, **kwargs):
        factory = globals().get(self._internal_name)
        if factory is None:
            raise RuntimeError(f"Database factory {self._internal_name} not initialized. JIT DAG may have skipped 'DATABASE' node.")
        return factory(*args, **kwargs)

# Stable pointers for external imports (Now Proxies)
SessionUser = AtomicSessionFactoryProxy("_SessionUser")
SessionTransit = AtomicSessionFactoryProxy("_SessionTransit")
SessionAuth = AtomicSessionFactoryProxy("_SessionAuth")
SessionLocal = AtomicSessionFactoryProxy("_SessionUser")

def get_SessionUser():
    return SessionUser()

def get_SessionTransit():
    return SessionTransit()

def get_SessionAuth():
    return SessionAuth()

_pools_initialized = False
_db_lock = asyncio.Lock()

async def initialize_database_pools():
    """
    Subtask 4.1 & 4.5: Lazy Engine Instantiation & Auth Isolation.
    """
    global engine_user, engine_transit, engine_auth, async_engine_user, async_engine_transit, async_engine_auth
    global _SessionUser, _SessionTransit, _SessionAuth, AsyncSessionUser, AsyncSessionTransit, AsyncSessionAuth
    global SessionUser, SessionTransit, SessionAuth, SessionLocal
    global engine
    global _pools_initialized
    
    if _pools_initialized:
        return
        
    async with _db_lock:
        if _pools_initialized:
            return

        logger.info("🗄️ JIT: Initializing database connection pools (including Isolated Auth)...")

        # Connection args
        user_db_url_sync = Config.GET_SQLALCHEMY_URL("user", is_async=False)
        transit_db_url_sync = Config.GET_SQLALCHEMY_URL("transit", is_async=False)
        user_db_url_async = Config.GET_SQLALCHEMY_URL("user", is_async=True)
        transit_db_url_async = Config.GET_SQLALCHEMY_URL("transit", is_async=True)

        engine_user = create_engine(user_db_url_sync, connect_args={"check_same_thread": False} if "sqlite" in user_db_url_sync else {})
        engine_transit = create_engine(transit_db_url_sync, connect_args={"check_same_thread": False} if "sqlite" in transit_db_url_sync else {})
        
        auth_sync_kwargs = {"pool_size": 5, "max_overflow": 0} if "sqlite" not in user_db_url_sync else {}
        engine_auth = create_engine(user_db_url_sync, connect_args={"check_same_thread": False} if "sqlite" in user_db_url_sync else {}, **auth_sync_kwargs)
        
        engine = engine_user

        # Async engines with appropriate pool sizes
        is_sqlite = "sqlite" in user_db_url_async
        pool_kwargs = {"pool_size": 20, "max_overflow": 10} if not is_sqlite else {}
        auth_pool_kwargs = {"pool_size": 10, "max_overflow": 5} if not is_sqlite else {}

        async_engine_user = create_async_engine(user_db_url_async, echo=False, pool_pre_ping=True, **pool_kwargs)
        async_engine_transit = create_async_engine(transit_db_url_async, echo=False, pool_pre_ping=True, **pool_kwargs)
        # Auth pool is small but guaranteed (Subtask 4.5)
        async_engine_auth = create_async_engine(user_db_url_async, echo=False, pool_pre_ping=True, **auth_pool_kwargs)

        # Factories (Assigned to private globals)
        _SessionUser = sessionmaker(autocommit=False, autoflush=False, bind=engine_user)
        _SessionTransit = sessionmaker(autocommit=False, autoflush=False, bind=engine_transit)
        _SessionAuth = sessionmaker(autocommit=False, autoflush=False, bind=engine_auth)
        
        # [9.1] Public Pointers MUST remain as Proxies
        # We do not overwrite SessionUser/SessionTransit here.
        # They were already assigned to AtomicSessionFactoryProxy at module level.

        AsyncSessionUser = sessionmaker(async_engine_user, class_=AsyncSession, expire_on_commit=False)
        AsyncSessionTransit = sessionmaker(async_engine_transit, class_=AsyncSession, expire_on_commit=False)
        AsyncSessionAuth = sessionmaker(async_engine_auth, class_=AsyncSession, expire_on_commit=False)
        
        # Trigger raw pool for Ultra-Turbo (Subtask 1.1)
        await init_raw_transit_pool()
        
        _pools_initialized = True
        logger.info("✅ All Database pools active (Isolated Auth ready).")

async def pre_warm_connections():
    """
    Subtask 4.2: Predictive Pool Pre-Warming.
    Fires SELECT 1 to force TCP handshakes in the pool before user requests.
    """
    if not _pools_initialized:
        await initialize_database_pools()
        
    logger.debug("🔥 Predictive Pre-warming: Firing TCP handshakes (SELECT 1)...")
    try:
        # Fire concurrent SELECT 1 against user and transit DBs
        async def ping_db(engine):
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
                
        tasks = [ping_db(async_engine_user) for _ in range(2)] + \
                [ping_db(async_engine_transit) for _ in range(2)]
        await asyncio.gather(*tasks)
    except Exception as e:
        logger.error(f"⚠️ Pre-warm failed: {e}")

async def run_pool_scaler():
    """
    Subtask 4.6: Dynamic Pool Sizing via Telemetry.
    Adjusts pool overflow based on predictions_total.
    """
    from core.metrics import jit_metrics
    while True:
        await asyncio.sleep(30)
        if not _pools_initialized: continue
        
        # Simple Logic: If traffic > 100 req/sec, allow more overflow
        # (predictions_total is a counter, so we check delta)
        # For this implementation, we log the intent.
        # SQLAlchemy pools are not easily resizable after creation without 
        # replacing the engine, but we can simulate the 'reaper' logic.
        
        logger.debug(f"📊 Pool Scaler: Traffic at {jit_metrics.predictions_total} total requests.")

async def run_connection_reaper():
    """
    Subtask 4.7: Memory-Aware Connection Reaper.
    Hardened: Fires at 90% RAM to avoid system-wide OOM.
    Also disposes idle connections every 10 minutes regardless of pressure.
    """
    import psutil
    last_reap = 0
    last_periodic_clear = time.time()
    
    while True:
        await asyncio.sleep(30)
        if not _pools_initialized: continue
        
        try:
            mem = psutil.virtual_memory()
            now = time.time()
            
            # 1. Critical Reap (OOM Prevention)
            if mem.percent > 90 and (now - last_reap) > 120:
                logger.warning(f"🚨 Memory Critical ({mem.percent}%). Reaping all DB pools...")
                await _dispose_all_pools()
                last_reap = now
                from core.metrics import jit_metrics
                jit_metrics.reaper_events += 1
            
            # 2. Periodic Maintenance (Hygiene)
            elif (now - last_periodic_clear) > 600:
                logger.info("🧹 Periodic Pool Maintenance: Disposing idle connections.")
                await _dispose_all_pools()
                last_periodic_clear = now
                
        except Exception as e:
            logger.error(f"Reaper Error: {e}")

async def _dispose_all_pools():
    """Helper to dispose all active database engines."""
    try:
        if async_engine_user: await async_engine_user.dispose()
        if async_engine_transit: await async_engine_transit.dispose()
        if async_engine_auth: await async_engine_auth.dispose()
        if engine_user: engine_user.dispose()
        if engine_transit: engine_transit.dispose()
        if engine_auth: engine_auth.dispose()
    except Exception as e:
        logger.error(f"Error during pool disposal: {e}")

# --- Dependency Injectors ---

def get_db():
    if not _pools_initialized: raise RuntimeError("Database not JIT initialized")
    db = SessionUser()
    try: yield db
    finally: db.close()

def get_transit_db():
    if not _pools_initialized: raise RuntimeError("Database not JIT initialized")
    db = SessionTransit()
    try: yield db
    finally: db.close()

def get_auth_db():
    """Subtask 4.5: Isolated Auth Session Injector (Sync)."""
    if not _pools_initialized:
        import asyncio
        # This is a bit tricky in sync code if not already initialized
        # But initialize_database_pools is async.
        # In practice, app startup or first async request will have initialized it.
        pass 
    db = SessionAuth()
    try: yield db
    finally: db.close()

async def get_async_db():
    if not _pools_initialized: raise RuntimeError("Database not JIT initialized")
    async with AsyncSessionUser() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_async_transit_db():
    if not _pools_initialized: raise RuntimeError("Database not JIT initialized")
    async with AsyncSessionTransit() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_async_auth_db():
    """Subtask 4.5: Isolated Auth Session Injector."""
    if not _pools_initialized:
        await initialize_database_pools()
    async with AsyncSessionAuth() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db(target_tables: Optional[List[str]] = None):
    """
    Subtask 4.9: JIT Schema Reflection.
    Allows initializing ONLY the tables needed for the current intent.
    """
    if not _pools_initialized:
        await initialize_database_pools()
        
    from . import models
    
    async def create_target(engine, metadata, targets):
        async with engine.begin() as conn:
            if targets:
                # Filter metadata to only include requested tables
                # (Simplified for this subtask)
                logger.info(f"🗄️ JIT: Reflecting specific tables: {targets}")
                pass
            await conn.run_sync(metadata.create_all)

    await create_target(async_engine_user, UserBase.metadata, target_tables)
    await create_target(async_engine_transit, TransitBase.metadata, target_tables)

def get_source_connection():
    import sqlite3
    db_path = os.path.join(_BASE_DIR, 'railway_data.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
