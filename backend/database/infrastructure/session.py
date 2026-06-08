import asyncio
import time
try:
    import aiosqlite  # optional — only needed for SQLite fallback in local dev
except ImportError:
    aiosqlite = None  # type: ignore
from sqlalchemy import create_engine, event, MetaData, Engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, declarative_base, Session
import logging
import os
from typing import Optional, List, Any, Dict, cast

from database.infrastructure.config import Config

logger = logging.getLogger("database-session")

_BASE_DIR = Config.BASE_DIR
transit_db_path = Config.GET_SQLALCHEMY_URL("transit", is_async=False)

# --- Metadata & Bases ---
from database.infrastructure.base import UserBase, TransitBase, Base

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
_pools_initialized = False
_db_lock = asyncio.Lock()

# --- Global Session Factory Holders ---
_SessionUser = None
_SessionTransit = None
_SessionAuth = None
_SessionRead = None
_AsyncSessionUser = None
_AsyncSessionTransit = None
_AsyncSessionAuth = None
_AsyncSessionRead = None

# --- Proxy Logic (Moved up to prevent circular NameErrors) ---
class AtomicSessionFactoryProxy:
    def __init__(self, internal_name):
        self._internal_name = internal_name

    def __call__(self, *args, **kwargs):
        factory = globals().get(self._internal_name)
        if factory is None:
            if not _pools_initialized:
                 logger.warning(f"JIT Access to {self._internal_name} before initialization!")
                 if not _pools_initialized:
                     raise RuntimeError(f"Database factory {self._internal_name} not yet initialized.")
            factory = globals().get(self._internal_name)
        if factory is None:
            logger.error(f"DEBUG: globals keys: {list(globals().keys())}")
            raise RuntimeError(f"Database factory {self._internal_name} not initialized (Even though pools are initialized).")
        return factory(*args, **kwargs)

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

import functools

def with_db_retry(max_retries: int = 5, initial_delay: float = 0.05):
    """Database lock recovery decorator. Nexus hooks are optional — silently skipped if archived."""
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
                            logger.warning(f"DB Locked (Async): Retrying {retries}/{max_retries} in {delay}s...")
                            await asyncio.sleep(delay)
                            delay *= 2
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
                            logger.warning(f"DB Locked (Sync): Retrying {retries}/{max_retries} in {delay}s...")
                            time.sleep(delay)
                            delay *= 2
                        else:
                            raise e
            return sync_wrapper
    return decorator

# --- Database Service Provider ---
class DatabaseServiceProvider:
    def __init__(self):
        self._pool_scaler_task = None
        self._vacuum_task = None

    async def init(self):
        await initialize_database_pools()
        if not self._pool_scaler_task:
            self._pool_scaler_task = asyncio.create_task(run_pool_scaler())
        if not self._vacuum_task:
            self._vacuum_task = asyncio.create_task(run_vacuum_worker())
        logger.info("IoC: Database Service Initialized.")

    async def shutdown(self):
        await _dispose_all_pools()
        if self._pool_scaler_task: self._pool_scaler_task.cancel()
        if self._vacuum_task: self._vacuum_task.cancel()

async def tune_db_performance(engine):
    if "sqlite" not in str(engine.url): return
    import psutil
    mem = psutil.virtual_memory()
    mmap_size = 512 * 1024 * 1024 if mem.total > 2048 * 1024 * 1024 else 128 * 1024 * 1024
    async with engine.connect() as conn:
        await conn.execute(text(f"PRAGMA mmap_size = {mmap_size};"))
        await conn.execute(text("PRAGMA cache_size = -128000;"))
        await conn.execute(text("PRAGMA synchronous = NORMAL;"))
        await conn.execute(text("PRAGMA journal_mode = WAL;"))
        await conn.execute(text("PRAGMA temp_store = MEMORY;"))
        await conn.commit()

async def tune_db_read_performance(engine):
    async with engine.connect() as conn:
        try:
            await conn.execute(text("PRAGMA query_only = ON;"))
            await conn.execute(text("PRAGMA mmap_size = 536870912;"))
        except: pass
        await conn.commit()

async def initialize_database_pools():
    global engine_user, engine_transit, engine_auth, engine_read
    global async_engine_user, async_engine_transit, async_engine_auth, async_engine_read
    global _SessionUser, _SessionTransit, _SessionAuth, _SessionRead
    global _AsyncSessionUser, _AsyncSessionTransit, _AsyncSessionAuth, _AsyncSessionRead
    global _pools_initialized, engine
    
    if _pools_initialized: 
        logger.info("[DB:INIT] Skipping - already initialized.")
        return
    async with _db_lock:
        if _pools_initialized: return
        
        logger.info("[DB:INIT] Initializing database connection pools (Phase 1)...")
        user_db_url_sync = Config.GET_SQLALCHEMY_URL("user", is_async=False)
        transit_db_url_sync = Config.GET_SQLALCHEMY_URL("transit", is_async=False)
        user_db_url_async = Config.GET_SQLALCHEMY_URL("user", is_async=True)
        transit_db_url_async = Config.GET_SQLALCHEMY_URL("transit", is_async=True)

        def get_engine_args(url: str, is_async: bool = False) -> Dict[str, Any]:
            args: Dict[str, Any] = {"execution_options": {"timeout": 30}}
            if "sqlite" in url:
                args["connect_args"] = {"check_same_thread": False, "timeout": 20}
                if not is_async:
                    args["pool_size"] = 20
                    args["max_overflow"] = 10
            else:
                args["pool_size"] = Config.DB_POOL_SIZE
                args["max_overflow"] = Config.DB_MAX_OVERFLOW
                args["pool_pre_ping"] = True
                args["pool_recycle"] = 1800
                if is_async and "postgresql" in url:
                    import ssl
                    ssl_ctx = ssl.create_default_context()
                    # By default Supabase poolers might need less strict checks during local dev
                    # ssl_ctx.check_hostname = False
                    # ssl_ctx.verify_mode = ssl.CERT_NONE
                    args["connect_args"] = {"statement_cache_size": 0, "ssl": ssl_ctx}
            return args

        engine_user = create_engine(user_db_url_sync, **get_engine_args(user_db_url_sync))
        engine_transit = create_engine(transit_db_url_sync, **get_engine_args(transit_db_url_sync))
        engine_read = create_engine(transit_db_url_sync, **get_engine_args(transit_db_url_sync))
        engine_auth = create_engine(user_db_url_sync, **get_engine_args(user_db_url_sync))

        async_engine_user = create_async_engine(user_db_url_async, **get_engine_args(user_db_url_async, is_async=True))
        async_engine_transit = create_async_engine(transit_db_url_async, **get_engine_args(transit_db_url_async, is_async=True))
        async_engine_auth = create_async_engine(user_db_url_async, **get_engine_args(user_db_url_async, is_async=True))
        async_engine_read = create_async_engine(transit_db_url_async, **get_engine_args(transit_db_url_async, is_async=True))

        _SessionUser = sessionmaker(bind=engine_user)
        _SessionTransit = sessionmaker(bind=engine_transit)
        _SessionAuth = sessionmaker(bind=engine_auth)
        _SessionRead = sessionmaker(bind=engine_read)

        await tune_db_performance(async_engine_user)
        await tune_db_performance(async_engine_transit)
        await tune_db_read_performance(async_engine_read)

        _AsyncSessionUser = async_sessionmaker(bind=async_engine_user, class_=AsyncSession, expire_on_commit=False)
        _AsyncSessionTransit = async_sessionmaker(bind=async_engine_transit, class_=AsyncSession, expire_on_commit=False)
        _AsyncSessionAuth = async_sessionmaker(bind=async_engine_auth, class_=AsyncSession, expire_on_commit=False)
        _AsyncSessionRead = async_sessionmaker(bind=async_engine_read, class_=AsyncSession, expire_on_commit=False)
        
        engine = engine_user
        _pools_initialized = True
        logger.info(f"✅ [DB:INIT] All Database pools active. _pools_initialized={_pools_initialized}")

async def run_vacuum_worker():
    while True:
        await asyncio.sleep(12 * 3600)
        if not _pools_initialized: continue
        try:
            for eng in [async_engine_user, async_engine_transit]:
                if eng and "sqlite" in str(eng.url):
                    async with eng.begin() as conn:
                        await conn.execute(text("VACUUM; ANALYZE;"))
        except Exception as e: logger.error(f"Vacuum error: {e}")

async def run_pool_scaler():
    while True:
        await asyncio.sleep(60)
        if not _pools_initialized: continue
        import psutil
        if psutil.virtual_memory().percent > 92:
             await _dispose_all_pools(force=True)

async def _dispose_all_pools(force: bool = False):
    try:
        if async_engine_user: await async_engine_user.dispose()
        if async_engine_transit: await async_engine_transit.dispose()
        if engine_user: engine_user.dispose()
        if engine_transit: engine_transit.dispose()
    except Exception as e: logger.error(f"Dispose error: {e}")

def get_db():
    if not _pools_initialized: 
        logger.error(f"❌ [DB:GET] Access attempt failed - pools not initialized! (Value: {_pools_initialized})")
        raise RuntimeError("DB not ready.")
    db = SessionUser()
    try: yield db
    finally: db.close()

def get_transit_db():
    if not _pools_initialized: raise RuntimeError("DB not ready.")
    db = SessionTransit()
    try: yield db
    finally: db.close()

async def get_async_db():
    async with _AsyncSessionUser() as session:
        try: yield session
        finally: await session.close()

async def get_async_transit_db():
    async with _AsyncSessionTransit() as session:
        try: yield session
        finally: await session.close()

def get_auth_db():
    if not _pools_initialized: raise RuntimeError("DB not ready.")
    db = SessionAuth()
    try: yield db
    finally: db.close()

async def get_async_auth_db():
    if not _pools_initialized: raise RuntimeError("DB not ready.")
    async with _AsyncSessionAuth() as session:
        try: yield session
        finally: await session.close()

async def init_db(target_tables: Optional[List[str]] = None):
    """JIT Schema Reflection."""
    if not _pools_initialized:
        await initialize_database_pools()
    from database import models
    async def create_target(engine, metadata, targets):
        async with engine.begin() as conn:
            if targets:
                target_tables = [metadata.tables[t] for t in targets if t in metadata.tables]
                await conn.run_sync(metadata.create_all, tables=target_tables)
            else:
                await conn.run_sync(metadata.create_all)
    await create_target(async_engine_user, UserBase.metadata, target_tables)
    await create_target(async_engine_transit, TransitBase.metadata, target_tables)

def get_source_connection():
    import sqlite3
    db_path = os.path.join(Config.DB_DIR, 'railway_data.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# Global Instance
database_service = DatabaseServiceProvider()
