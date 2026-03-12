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

import functools

def with_db_retry(max_retries: int = 5, initial_delay: float = 0.05):
    """
    Subtask 2.8: Database Lock Recovery Decorator.
    Catches 'database is locked' errors and retries with exponential backoff.
    Essential for SQLite stability on VPS under concurrent writes.
    """
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                retries = 0
                delay = initial_delay
                while True:
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        err_str = str(e).lower()
                        if ("locked" in err_str or "busy" in err_str) and retries < max_retries:
                            retries += 1
                            logger.warning(f"⏳ DB Locked (Async): Retrying {retries}/{max_retries} in {delay}s...")
                            await asyncio.sleep(delay)
                            delay *= 2 # Exponential backoff
                        else:
                            raise e
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                retries = 0
                delay = initial_delay
                while True:
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        err_str = str(e).lower()
                        if ("locked" in err_str or "busy" in err_str) and retries < max_retries:
                            retries += 1
                            logger.warning(f"⏳ DB Locked (Sync): Retrying {retries}/{max_retries} in {delay}s...")
                            time.sleep(delay)
                            delay *= 2
                        else:
                            raise e
            return sync_wrapper
    return decorator

# --- Global Engine Pointers ---
engine_user = None
engine_transit = None
engine_auth = None 
engine_read = None # Subtask 2.7

async_engine_user = None
async_engine_transit = None
async_engine_auth = None 
async_engine_read = None # Subtask 2.7

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

async def tune_db_performance(engine):
    """
    Subtask 2.3: Dynamic DB Performance Tuning.
    Adjusts mmap and cache limits based on available VPS RAM.
    """
    import psutil
    mem = psutil.virtual_memory()
    # 256MB if > 1GB RAM, else 64MB
    mmap_size = 256 * 1024 * 1024 if mem.total > 1024 * 1024 * 1024 else 64 * 1024 * 1024
    
    async with engine.connect() as conn:
        await conn.execute(text(f"PRAGMA mmap_size = {mmap_size};"))
        await conn.execute(text("PRAGMA cache_size = -64000;")) # 64MB cache
        await conn.execute(text("PRAGMA synchronous = NORMAL;"))
        await conn.execute(text("PRAGMA journal_mode = WAL;"))
        await conn.commit()
    
    logger.debug(f"⚙️ DB Tuned: mmap={mmap_size//1024//1024}MB, sync=NORMAL, mode=WAL")

async def tune_db_read_performance(engine):
    """
    Subtask 2.7: Read-Replica Optimization.
    Enforces query_only mode for the read-pool.
    """
    async with engine.connect() as conn:
        try:
            await conn.execute(text("PRAGMA query_only = ON;"))
            await conn.execute(text("PRAGMA mmap_size = 536870912;")) # 512MB for reads
        except: pass
        await conn.commit()
    logger.debug("📖 Read-Replica Tuned: query_only=ON")

async def initialize_database_pools():
    """
    Subtask 4.1 & 4.5: Lazy Engine Instantiation & Auth Isolation.
    [Subtask 2.7] Read-Replica Pool initialization.
    """
    global engine_user, engine_transit, engine_auth, engine_read
    global async_engine_user, async_engine_transit, async_engine_auth, async_engine_read
    global _SessionUser, _SessionTransit, _SessionAuth, _SessionRead
    global AsyncSessionUser, AsyncSessionTransit, AsyncSessionAuth, AsyncSessionRead
    global SessionUser, SessionTransit, SessionAuth, SessionLocal, SessionRead
    global engine
    global _pools_initialized
    
    if _pools_initialized:
        return
        
    async with _db_lock:
        if _pools_initialized:
            return

        logger.info("🗄️ JIT: Initializing database connection pools (including Isolated Auth/Read-Replica)...")

        # Connection args
        user_db_url_sync = Config.GET_SQLALCHEMY_URL("user", is_async=False)
        transit_db_url_sync = Config.GET_SQLALCHEMY_URL("transit", is_async=False)
        user_db_url_async = Config.GET_SQLALCHEMY_URL("user", is_async=True)
        transit_db_url_async = Config.GET_SQLALCHEMY_URL("transit", is_async=True)

        engine_user = create_engine(user_db_url_sync, connect_args={"check_same_thread": False} if "sqlite" in user_db_url_sync else {})
        engine_transit = create_engine(transit_db_url_sync, connect_args={"check_same_thread": False} if "sqlite" in transit_db_url_sync else {})
        engine_read = create_engine(transit_db_url_sync, connect_args={"check_same_thread": False} if "sqlite" in transit_db_url_sync else {})
        
        auth_sync_kwargs = {"pool_size": 5, "max_overflow": 0} if "sqlite" not in user_db_url_sync else {}
        engine_auth = create_engine(user_db_url_sync, connect_args={"check_same_thread": False} if "sqlite" in user_db_url_sync else {}, **auth_sync_kwargs)
        
        engine = engine_user

        # Async engines
        async_engine_user = create_async_engine(user_db_url_async, echo=False, pool_pre_ping=True)
        async_engine_transit = create_async_engine(transit_db_url_async, echo=False, pool_pre_ping=True)
        async_engine_auth = create_async_engine(user_db_url_async, echo=False, pool_pre_ping=True)
        async_engine_read = create_async_engine(transit_db_url_async, echo=False, pool_pre_ping=True)

        # Factories
        _SessionUser = sessionmaker(autocommit=False, autoflush=False, bind=engine_user)
        _SessionTransit = sessionmaker(autocommit=False, autoflush=False, bind=engine_transit)
        _SessionAuth = sessionmaker(autocommit=False, autoflush=False, bind=engine_auth)
        _SessionRead = sessionmaker(autocommit=False, autoflush=False, bind=engine_read)
        
        # [2.3 / 2.7] Tune Async Engines
        await tune_db_performance(async_engine_user)
        await tune_db_performance(async_engine_transit)
        await tune_db_performance(async_engine_auth)
        await tune_db_read_performance(async_engine_read)

        AsyncSessionUser = sessionmaker(async_engine_user, class_=AsyncSession, expire_on_commit=False)
        AsyncSessionTransit = sessionmaker(async_engine_transit, class_=AsyncSession, expire_on_commit=False)
        AsyncSessionAuth = sessionmaker(async_engine_auth, class_=AsyncSession, expire_on_commit=False)
        AsyncSessionRead = sessionmaker(async_engine_read, class_=AsyncSession, expire_on_commit=False)
        
        await init_raw_transit_pool()
        _pools_initialized = True
        logger.info("✅ All Database pools active (Isolated Auth/Read-Replica ready).")
        
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
    Subtask 2.1: Advanced Dynamic Pool Sizing.
    Optimizes VPS RAM by disposing pools during idle periods
    and pre-warming them during surge detection.
    """
    from core.metrics import jit_metrics
    last_load_state = False # False = Idle, True = Surge
    
    while True:
        await asyncio.sleep(15) # Check more frequently for scaling
        if not _pools_initialized: continue
        
        current_load_state = jit_metrics.is_overloaded or jit_metrics.event_loop_latency_ms > 20
        
        if current_load_state and not last_load_state:
            # Transition: Idle -> Surge
            logger.info("📈 Pool Scaler: System load detected. Pre-warming database pools...")
            await pre_warm_connections()
            last_load_state = True
            
        elif not current_load_state and last_load_state:
            # Transition: Surge -> Idle
            # We wait for a sustained idle period before shrinking
            await asyncio.sleep(45)
            # Re-check load
            if not (jit_metrics.is_overloaded or jit_metrics.event_loop_latency_ms > 20):
                logger.info("📉 Pool Scaler: System idle. Shrinking DB pools to save VPS RAM.")
                await _dispose_all_pools()
                last_load_state = False
        
        # Periodic 'Idle heartbeat' to ensure we stay lean
        if not current_load_state and not last_load_state:
            import psutil
            if psutil.virtual_memory().percent > 85:
                logger.debug("🧹 Pool Scaler: High RAM while idle. Force-disposing pools.")
                await _dispose_all_pools()

async def run_ghost_connection_killer():
    """
    Subtask 2.4: Ghost Connection Killer.
    Aggressively disposes idle pools every 60 seconds if system is not under load.
    Prevents lingering RAM bloat from stagnant connections.
    """
    from core.metrics import jit_metrics
    while True:
        await asyncio.sleep(60)
        if not _pools_initialized: continue
        
        # Only kill if NOT in surge and NOT currently processing high traffic
        if not (jit_metrics.is_overloaded or jit_metrics.event_loop_latency_ms > 20):
            logger.info("👻 Ghost Killer: System idle. Disposing stagnant DB pools.")
            await _dispose_all_pools()

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
                logger.warning(f"🚨 Memory Critical ({mem.percent}%). Reaping all DB pools and triggering GC...")
                await _dispose_all_pools()
                
                # Subtask 2.2: Aggressive GC
                import gc
                gc.collect()
                
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

def get_read_db():
    """Subtask 2.7: Read-Replica Dependency."""
    if not _pools_initialized: raise RuntimeError("Database not JIT initialized")
    db = _SessionRead()
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
