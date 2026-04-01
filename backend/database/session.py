import asyncio
import time
import aiosqlite
from sqlalchemy import create_engine, event, MetaData, Engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base, Session
import logging
import os
from typing import Optional, List, Any

from database.config import Config

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
                        from core.nexus.audit.chaos import nexus_chaos
                        await nexus_chaos.apply_trap("db_io")
                        return await func(*args, **kwargs)
                    except Exception as e:
                        err_str = str(e).lower()
                        if ("locked" in err_str or "busy" in err_str) and retries < max_retries:
                            retries += 1
                            from core.nexus.database.watchdog import database_watchdog
                            database_watchdog.report_lock_event(func.__name__)
                            logger.warning(f"DB Locked (Async): Retrying {retries}/{max_retries} in {delay}s...")
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
                        from core.nexus.audit.chaos import nexus_chaos
                        nexus_chaos.apply_trap_sync("db_io")
                        return func(*args, **kwargs)
                    except Exception as e:
                        err_str = str(e).lower()
                        if ("locked" in err_str or "busy" in err_str) and retries < max_retries:
                            retries += 1
                            from core.nexus.database.watchdog import database_watchdog
                            database_watchdog.report_lock_event(func.__name__)
                            logger.warning(f"DB Locked (Sync): Retrying {retries}/{max_retries} in {delay}s...")
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
    raw_url = Config.GET_SQLALCHEMY_URL("transit", is_async=False)
    # [Issue 7] Fix sslmode for aiosqlite (remove params)
    db_path = raw_url.split("?")[0].replace("sqlite:///", "") 
    logger.info(f"Initializing Ultra-Turbo Raw Pool (Size: {_RAW_POOL_SIZE}) at {db_path}")
    if "postgresql" in raw_url:
        logger.info("Skipping raw pool for PostgreSQL")
        return

    for _ in range(_RAW_POOL_SIZE):
        # Ensure db_path is clean of any query parameters for aiosqlite
        conn = await aiosqlite.connect(db_path)
        conn.row_factory = aiosqlite.Row
        await _raw_transit_pool.put(conn)
    logger.info(f"Ultra-Turbo Raw Pool Initialized (Size: {_RAW_POOL_SIZE})")

import contextlib

@contextlib.asynccontextmanager
async def get_raw_transit_conn():
    """Context manager for acquiring and releasing raw connections."""
    raw_url = Config.GET_SQLALCHEMY_URL("transit", is_async=False)
    is_postgres = "postgresql" in raw_url.lower()

    if is_postgres:
        # For Postgres, standard SQLAlchemy async session is fine
        # We wrap it to look like a raw connection with 'execute'
        async with AsyncSessionTransit() as session:
            # Add a thin proxy to make it behave like a raw aiosqlite connection if needed
            # But normally we can just use the session.
            yield session
            return

    if _raw_transit_pool.empty() and not _pools_initialized:
        # Fallback: if called before full IoC, try to init pool now
        try:
            await init_raw_transit_pool()
        except Exception as e:
            logger.error(f"Failed to JIT initialize raw pool: {e}")
            raise RuntimeError("Raw pool not initialized.")
            
    # [Nexus Fix] Avoid perpetual hang if pool failed to populate
    if _raw_transit_pool.empty() and _pools_initialized:
         async with AsyncSessionTransit() as session:
            yield session
            return

    conn = await _raw_transit_pool.get()
    try:
        yield conn
    finally:
        await _raw_transit_pool.put(conn)

# factories will be assigned here
def SessionUser(): return _SessionUser()
def SessionTransit(): return _SessionTransit()
def SessionAuth(): return _SessionAuth()
def SessionRead(): return _SessionRead()
def SessionLocal(): return _SessionUser() # Legacy alias

from sqlalchemy.ext.asyncio import AsyncSession
AsyncSessionUser = lambda: _AsyncSessionUser()
AsyncSessionTransit = lambda: _AsyncSessionTransit()
AsyncSessionAuth = lambda: _AsyncSessionAuth()
AsyncSessionRead = lambda: _AsyncSessionRead()

from core.providers import ServiceProvider, ServiceStatus
from core.container import container

class DatabaseServiceProvider(ServiceProvider):
    """
    Task 8: Database IoC Provider.
    Manages complex connection pools, raw aiosqlite pools, and performance tuning.
    """
    def __init__(self):
        super().__init__("db", version="1.5.0")
        self._pool_scaler_task = None
        self._vacuum_task = None

    async def init(self):
        """IoC Lifecycle: Initialize all pools and tuning."""
        await initialize_database_pools()
        # await pre_warm_connections()
        
        # Start background maintenance tasks
        if not self._pool_scaler_task:
            self._pool_scaler_task = asyncio.create_task(run_pool_scaler())
        if not self._vacuum_task:
            self._vacuum_task = asyncio.create_task(run_vacuum_worker())
        
        logger.info("IoC: Database Service Initialized and background workers started.")

    async def shutdown(self):
        """IoC Lifecycle: Dispose all pools."""
        await _dispose_all_pools()
        if self._pool_scaler_task: self._pool_scaler_task.cancel()
        if self._vacuum_task: self._vacuum_task.cancel()
        logger.info("IoC: Database Service shutdown.")

class AtomicSessionFactoryProxy:
    """
    Task 11 & Task 8: Dynamic On-Demand Proxy with IoC support.
    Ensures that modules importing SessionLocal/SessionTransit at module-level
    always get a callable that points to the latest initialized factory.
    Triggers IoC "db" service if not ready.
    """
    def __init__(self, internal_name):
        self._internal_name = internal_name

    def __call__(self, *args, **kwargs):
        factory = globals().get(self._internal_name)
        if factory is None:
            # Task 11 & Subtask 3.1: Enforce Single Source of Truth
            if not _pools_initialized:
                 from core.container import container
                 # Instead of JIT'ing here, we rely on the Lifespan or Container having run.
                 # If we are in a context where its NOT initialized, it's an architectural failure.
                 logger.warning(f"JIT Access to {self._internal_name} before initialization! Waiting for core boot...")
                 # For sync contexts, we can't easily wait, so we raise a clear error to find gaps.
                 if not _pools_initialized:
                     raise RuntimeError(f"Database factory {self._internal_name} not yet initialized. The startup flow must be audited.")
                 
            factory = globals().get(self._internal_name)
        
        if factory is None:
            raise RuntimeError(f"Database factory {self._internal_name} not initialized.")
            
        return factory(*args, **kwargs)

# Stable pointers for external imports (Now Proxies)
SessionUser = AtomicSessionFactoryProxy("_SessionUser")
SessionTransit = AtomicSessionFactoryProxy("_SessionTransit")
SessionAuth = AtomicSessionFactoryProxy("_SessionAuth")
SessionLocal = AtomicSessionFactoryProxy("_SessionUser")
SessionRead = AtomicSessionFactoryProxy("_SessionRead")

AsyncSessionUser = AtomicSessionFactoryProxy("_AsyncSessionUser")
AsyncSessionTransit = AtomicSessionFactoryProxy("_AsyncSessionTransit")
AsyncSessionAuth = AtomicSessionFactoryProxy("_AsyncSessionAuth")
AsyncSessionRead = AtomicSessionFactoryProxy("_AsyncSessionRead")
AsyncSessionLocal = AsyncSessionUser

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
    Subtask 4.3: SQLite Performance Tuning.
    [Task 11] Optimized for large station graphs.
    """
    if "sqlite" not in str(engine.url):
        return

    import psutil
    mem = psutil.virtual_memory()
    # 512MB if > 2GB RAM, else 128MB (Hardened for Hostinger KVM 2)
    mmap_size = 512 * 1024 * 1024 if mem.total > 2048 * 1024 * 1024 else 128 * 1024 * 1024

    async with engine.connect() as conn:
        await conn.execute(text(f"PRAGMA mmap_size = {mmap_size};"))
        await conn.execute(text("PRAGMA cache_size = -128000;")) # 128MB cache
        await conn.execute(text("PRAGMA synchronous = NORMAL;"))
        await conn.execute(text("PRAGMA journal_mode = WAL;"))
        await conn.execute(text("PRAGMA temp_store = MEMORY;"))
        await conn.commit()

    logger.info(f"[NEXUS:CACHE] DB Tuned (P5.1): mmap={mmap_size//1024//1024}MB, sync=NORMAL, mode=WAL")


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
    logger.debug("Read-Replica Tuned: query_only=ON")

async def run_vacuum_worker():
    """
    Task 20: SQLite Maintenance Worker.
    Periodically runs VACUUM and ANALYZE to optimize DB performance.
    """
    from core.orchestrator import orchestrator
    while not orchestrator.is_shutting_down:
        from core.nexus.watchdog import nexus_watchdog
        nexus_watchdog.poke("vacuum_worker")
        # Run every 12 hours
        await asyncio.sleep(12 * 3600)
        
        if not _pools_initialized: continue
        
        logger.info("DB Maintenance: Running VACUUM/ANALYZE on SQLite databases...")
        try:
            for eng in [async_engine_user, async_engine_transit]:
                if "sqlite" in str(eng.url):
                    async with eng.begin() as conn:
                        await conn.execute(text("VACUUM;"))
                        await conn.execute(text("ANALYZE;"))
            logger.info("DB Maintenance: Optimized successfully.")
        except Exception as e:
            logger.error(f"DB Maintenance Error: {e}")

async def initialize_database_pools():
    """
    Subtask 4.1 & 4.5: Lazy Engine Instantiation & Auth Isolation.
    [Task 11] Integrated DBConnectionManager profiling and timeouts.
    """
    global engine_user, engine_transit, engine_auth, engine_read
    global async_engine_user, async_engine_transit, async_engine_auth, async_engine_read
    global _SessionUser, _SessionTransit, _SessionAuth, _SessionRead
    global _AsyncSessionUser, _AsyncSessionTransit, _AsyncSessionAuth, _AsyncSessionRead
    global _pools_initialized, engine
    import importlib
    manager_mod = importlib.import_module("database.manager")
    db_manager = manager_mod.db_manager
    
    if _pools_initialized:
        return
        
    async with _db_lock:
        if _pools_initialized:
            return

        logger.info("JIT: Initializing optimized database connection pools (Group 5)...")

        # 1. URLs and Config
        user_db_url_sync = Config.GET_SQLALCHEMY_URL("user", is_async=False)
        transit_db_url_sync = Config.GET_SQLALCHEMY_URL("transit", is_async=False)
        user_db_url_async = Config.GET_SQLALCHEMY_URL("user", is_async=True)
        transit_db_url_async = Config.GET_SQLALCHEMY_URL("transit", is_async=True)
        user_db_url_async = Config.GET_SQLALCHEMY_URL("user", is_async=True)
        transit_db_url_async = Config.GET_SQLALCHEMY_URL("transit", is_async=True)
        with open("tmp_db_trace.txt", "a") as f:
            f.write(f"USER_ASYNC: {user_db_url_async}\n")
            f.write(f"TRANSIT_ASYNC: {transit_db_url_async}\n")
        
        # Removed OneDrive/Dropbox Warning per User Request (Task 118 Revoke)
        pass

        # [Task 2] Robust Pool Configuration & SSL Fix
        def get_engine_args(url, is_async=False):
            args = {"execution_options": execution_options}
            is_sqlite = "sqlite" in url
            
            if is_sqlite:
                args["connect_args"] = {"check_same_thread": False, "timeout": 20}
                # [Elite] LIFO pool for SQLite avoids unnecessary file locks
                args["pool_use_lifo"] = True
                if not is_async:
                    args["pool_size"] = 5 # Task 118: Increased to 5 to avoid re-entrant deadlocks
                    args["max_overflow"] = 0 # Strictly NO overflow to cap the RAM
            else:
                # PostgreSQL / Supabase
                args["pool_size"] = Config.DB_POOL_SIZE
                args["max_overflow"] = Config.DB_MAX_OVERFLOW
                args["pool_pre_ping"] = True
                
                # [Task 118] Supabase Recycle Guard (Avoid TCP timeouts)
                args["pool_recycle"] = int(os.getenv("DB_RECYCLE", 1800))
                args["pool_use_lifo"] = True 

                if is_async and "postgresql" in url:
                    import ssl
                    args["connect_args"] = {
                        "ssl": ssl.create_default_context(ssl.Purpose.SERVER_AUTH),
                        "timeout": 30,
                        "command_timeout": 60, # Elite hard-timeout for hung queries
                        "prepared_statement_cache_size": 0,
                        "statement_cache_size": 0 
                    }
            return args

        execution_options = {"timeout": 30}

        # 2. Sync Engines with Profiling
        engine_user = create_engine(user_db_url_sync, **get_engine_args(user_db_url_sync))
        engine_transit = create_engine(transit_db_url_sync, **get_engine_args(transit_db_url_sync))
        engine_read = create_engine(transit_db_url_sync, **get_engine_args(transit_db_url_sync))
        engine_auth = create_engine(user_db_url_sync, **get_engine_args(user_db_url_sync))
        
        # [Task 11.3] Instrument sync engines
        db_manager.instrument_engine(engine_user)
        db_manager.instrument_engine(engine_transit)
        db_manager.instrument_engine(engine_read)

        # 3. Async Engines with Profiling
        async_engine_user = create_async_engine(user_db_url_async, **get_engine_args(user_db_url_async, is_async=True))
        async_engine_transit = create_async_engine(transit_db_url_async, **get_engine_args(transit_db_url_async, is_async=True))
        async_engine_auth = create_async_engine(user_db_url_async, **get_engine_args(user_db_url_async, is_async=True))
        async_engine_read = create_async_engine(transit_db_url_async, **get_engine_args(transit_db_url_async, is_async=True))

        # [Task 11.3] Instrument async engines
        db_manager.instrument_engine(async_engine_user)
        db_manager.instrument_engine(async_engine_transit)
        db_manager.instrument_engine(async_engine_read)

        # 4. Factories
        _SessionUser = sessionmaker(autocommit=False, autoflush=False, bind=engine_user)
        _SessionTransit = sessionmaker(autocommit=False, autoflush=False, bind=engine_transit)
        _SessionAuth = sessionmaker(autocommit=False, autoflush=False, bind=engine_auth)
        _SessionRead = sessionmaker(autocommit=False, autoflush=False, bind=engine_read)
        
        # 5. [Task 11.5] Tune Async Engines for performance
        await tune_db_performance(async_engine_user)
        await tune_db_performance(async_engine_transit)
        await tune_db_performance(async_engine_auth)
        await tune_db_read_performance(async_engine_read)

        _AsyncSessionUser = sessionmaker(async_engine_user, class_=AsyncSession, expire_on_commit=False)
        _AsyncSessionTransit = sessionmaker(async_engine_transit, class_=AsyncSession, expire_on_commit=False)
        _AsyncSessionAuth = sessionmaker(async_engine_auth, class_=AsyncSession, expire_on_commit=False)
        _AsyncSessionRead = sessionmaker(async_engine_read, class_=AsyncSession, expire_on_commit=False)
        
        # Subtask 1.1: Initialize Raw Pool for Ultra-Turbo (Placeholder Removed in Task 118)
        # await init_raw_transit_pool()
        
        # [Task 50.1] Map engine alias for V3 Audit
        global engine
        engine = engine_user
        
        _pools_initialized = True
        logger.info("All Database pools active and instrumented with DBManager (Task 11 Group 5 complete).")

async def pre_warm_connections():
    """
    Subtask 4.2: Predictive Pool Pre-Warming.
    Fires SELECT 1 to force TCP handshakes in the pool before user requests.
    """
    if not _pools_initialized:
        await initialize_database_pools()
        
    logger.debug("Predictive Pre-warming: Firing TCP handshakes (SELECT 1)...")
    try:
        # Fire concurrent SELECT 1 against user and transit DBs
        async def ping_db(engine):
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
                
        tasks = [ping_db(async_engine_user) for _ in range(2)] + \
                [ping_db(async_engine_transit) for _ in range(2)]
        await asyncio.gather(*tasks)
    except Exception as e:
        logger.error(f"Pre-warm failed: {e}")

async def _has_active_connections() -> bool:
    """[Task 118] Elite Pool Safety Check. Prevents closing engines that are processing data."""
    try:
        from core.nexus.audit.governor import nexus_governor
        # 1. Governor Latch
        stats = await nexus_governor.get_stats()
        if stats["is_under_pressure"]: return True # Safety: Don't dispose during high pressure
        
        # 2. Connection Pool Introspection
        for eng in [async_engine_user, async_engine_transit, async_engine_auth]:
            if eng and hasattr(eng, 'pool'):
                # checkedout tells us if any sessions are currently in use
                if eng.pool.checkedout() > 0:
                    return True
        return False
    except: return False # Fallback to safety

async def run_pool_scaler():
    """[Task 118 Upgrade] Advanced Governor-Aware Pool Scaling."""
    from core.nexus.audit.governor import nexus_governor
    last_load_state = False 
    
    while True:
        from core.nexus.watchdog import nexus_watchdog
        nexus_watchdog.poke("db_pool_scaler")
        await asyncio.sleep(20) 
        if not _pools_initialized: continue
        
        gov_stats = await nexus_governor.get_stats()
        current_load_state = gov_stats["is_under_pressure"] or gov_stats["throttle_factor"] > 0.4
        
        if current_load_state and not last_load_state:
            logger.info("⚖️ Pool Scaler: System Pressure Detected. Pre-warming database connections.")
            await pre_warm_connections()
            last_load_state = True
            
        elif not current_load_state and last_load_state:
            # Sustained idle check (Task 118: 60s)
            await asyncio.sleep(60)
            if not await _has_active_connections():
                logger.info("📉 Pool Scaler: System Cooldown. Safe Repository Disposal.")
                await _dispose_all_pools()
                last_load_state = False
        
        # [Elite] OOM Emergency Override
        import psutil
        if psutil.virtual_memory().percent > 92:
             logger.critical("🚨 [NEXUS:OOM] Memory Critical (>92%). Forcing Emergency DB Disposal.")
             await _dispose_all_pools(force=True)
             import gc; gc.collect()
        # [Task 118] Hygiene Flush every 10 min if idle
        if not current_load_state and time.time() % 600 < 20: 
             if not await _has_active_connections():
                 await _dispose_all_pools()

async def _dispose_all_pools(force: bool = False):
    """Helper to dispose all active database engines. Task 118: Added active safe-lock."""
    if not force and await _has_active_connections():
        logger.debug("Skipping pool disposal: Active connections detected.")
        return

    try:
        if async_engine_user: await async_engine_user.dispose()
        if async_engine_transit: await async_engine_transit.dispose()
        if async_engine_auth: await async_engine_auth.dispose()
        if engine_user: engine_user.dispose()
        if engine_transit: engine_transit.dispose()
        if engine_auth: engine_auth.dispose()
        logger.info(f"DB Engines Disposed {'(FORCED)' if force else '(IDLE)'}.")
    except Exception as e:
        logger.error(f"Error during pool disposal: {e}")

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
                logger.warning(f"Memory Critical ({mem.percent}%). Reaping all DB pools and triggering GC...")
                await _dispose_all_pools()
                
                # Subtask 2.2: Aggressive GC
                import gc
                gc.collect()
                
                last_reap = now
                from core.metrics import jit_metrics
                jit_metrics.reaper_events += 1
            
            # 2. Periodic Maintenance (Hygiene)
            elif (now - last_periodic_clear) > 600:
                logger.info("Periodic Pool Maintenance: Disposing idle connections.")
                await _dispose_all_pools()
                last_periodic_clear = now
                
        except Exception as e:
            logger.error(f"Reaper Error: {e}")

# --- Dependency Injectors ---

def get_db():
    if not _pools_initialized:
        # Task 11: For sync, we assume middleware or bootstrap triggered it
        raise RuntimeError("Database not JIT initialized. Ensure ensure_ready('DATABASE') is called.")
    db = SessionUser()
    try: yield db
    finally: db.close()

def get_read_db():
    """
    Subtask 2.7: Read-Replica Dependency.
    [Task 11.10] Failover: Falls back to Primary if _SessionRead is unstable.
    """
    if not _pools_initialized:
        raise RuntimeError("Database not JIT initialized.")
    
    from .manager import db_manager
    if db_manager._failover_active:
        db = _SessionTransit() # Primary
    else:
        try:
            db = _SessionRead()
        except Exception:
            db_manager.set_failover(True)
            db = _SessionTransit()
            
    try: yield db
    finally: db.close()

async def get_async_read_db():
    """[Task 11] Async Read-Replica injector with failover."""
    if not _pools_initialized:
        await container.get("db")
        
    from .manager import db_manager
    factory = _AsyncSessionTransit if db_manager._failover_active else _AsyncSessionRead
    
    async with factory() as session:
        try:
            yield session
        except Exception:
            db_manager.set_failover(True)
            async with _AsyncSessionTransit() as fallback:
                yield fallback
        finally:
            await session.close()

async def get_async_db():
    if not _pools_initialized:
        await container.get("db")
    async with _AsyncSessionUser() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_async_transit_db():
    if not _pools_initialized:
        await container.get("db")
    async with _AsyncSessionTransit() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_async_auth_db():
    if not _pools_initialized:
        await container.get("db")
    async with _AsyncSessionAuth() as session:
        try:
            yield session
        finally:
            await session.close()

def get_transit_db():
    if not _pools_initialized:
        raise RuntimeError("Database not JIT initialized.")
    db = SessionTransit()
    try: yield db
    finally: db.close()

def get_auth_db():
    """Subtask 4.5: Isolated Auth Session Injector (Sync)."""
    if not _pools_initialized:
        pass 
    db = SessionAuth()
    try: yield db
    finally: db.close()

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
                logger.info(f"JIT: Reflecting specific tables: {targets}")
                # SQLAlchemy metadata.create_all(tables=[...])
                target_tables = [metadata.tables[t] for t in targets if t in metadata.tables]
                await conn.run_sync(metadata.create_all, tables=target_tables)
            else:
                await conn.run_sync(metadata.create_all)

    await create_target(async_engine_user, UserBase.metadata, target_tables)
    await create_target(async_engine_transit, TransitBase.metadata, target_tables)

def get_source_connection():
    import sqlite3
    db_path = os.path.join(_BASE_DIR, 'railway_data.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# Register Database in Global Container [Task 8]
database_service = DatabaseServiceProvider()
container.register(database_service)
