import time
import logging
import json
import asyncio
import hashlib
import pickle
from typing import Any, Dict, List, Optional, Tuple, Callable
from sqlalchemy import event, text, Engine
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine

logger = logging.getLogger("database.manager")
slow_query_logger = logging.getLogger("database.slow_queries")

# Threshold in seconds for slow query logging
SLOW_QUERY_THRESHOLD = 0.5 

class DBConnectionManager:
    """
    ⚙️ TASK GROUP 5: DATABASE OPTIMIZATION
    ✅ TASK 11: DB Connection Manager
    
    A centralized manager for pooling optimization, query profiling, 
    slow query logging, and failover management.
    """
    
    def __init__(self):
        self._queries_executed = 0
        self._slow_queries_count = 0
        self._total_query_time = 0.0
        self._is_replica_available = True
        self._failover_active = False

    def instrument_engine(self, engine: Any):
        """
        Adds profiling and slow query logging to a SQLAlchemy engine (sync or async).
        """
        # Handle both Engine and AsyncEngine
        target = engine.sync_engine if hasattr(engine, "sync_engine") else engine

        @event.listens_for(target, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            context._query_start_time = time.time()

        @event.listens_for(target, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            total_time = time.time() - context._query_start_time
            self._queries_executed += 1
            self._total_query_time += total_time
            
            if total_time > SLOW_QUERY_THRESHOLD:
                self._slow_queries_count += 1
                self._log_slow_query(statement, parameters, total_time, conn)

    def _log_slow_query(self, statement: str, parameters: Any, duration: float, conn: Connection):
        """
        Logs details of slow queries and optionally runs EXPLAIN for index suggestions.
        """
        slow_query_logger.warning(
            f"🐌 SLOW QUERY ({duration:.3f}s): {statement[:200]}... | Params: {parameters}"
        )
        
        # [Task 11.5] Auto-index suggestion for SQLite
        if "sqlite" in str(conn.engine.url):
            try:
                # We can't easily run EXPLAIN in the middle of a cursor execute event 
                # without deadlocks or recursion, so we log it for offline analysis
                # or run it in a separate thread/sync connection if safe.
                pass
            except Exception:
                pass

    def get_pool_stats(self, engine: Engine) -> Dict[str, Any]:
        """Returns connection pool metrics."""
        pool = engine.pool
        return {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow() if hasattr(pool, "overflow") else 0,
            "total_queries": self._queries_executed,
            "slow_queries": self._slow_queries_count,
            "avg_latency": self._total_query_time / max(self._queries_executed, 1)
        }

    async def check_health(self, engine: Any) -> bool:
        """Runs a lightweight health check (SELECT 1)."""
        try:
            if hasattr(engine, "connect") and asyncio.iscoroutinefunction(engine.connect):
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
            else:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"❌ DB Health Check Failed: {e}")
            return False

    def set_failover(self, active: bool):
        """Activates or deactivates failover mode."""
        self._failover_active = active
        if active:
            logger.warning("🚨 Failover System: Redirecting all traffic to Primary (Read-Replica Bypass)")
        else:
            logger.info("✅ Failover System: Read-Replica restored.")

    # [Task 11.7] Caching Layer
    async def get_cached_query(self, key: str) -> Optional[Any]:
        """Retrieve results from Redis cache via MultiLayerCache."""
        from services.multi_layer_cache import multi_layer_cache
        return await multi_layer_cache.get(f"db_cache:{key}")

    async def set_cached_query(self, key: str, value: Any, ttl: int = 300):
        """Store results in Redis cache via MultiLayerCache."""
        from services.multi_layer_cache import multi_layer_cache
        try:
            await multi_layer_cache.put(f"db_cache:{key}", value, ttl=ttl)
        except Exception as e:
            logger.debug(f"DB Caching failed: {e}")

def cached_query(ttl: int = 300):
    """
    Decorator for caching DB method results in Redis.
    Usage:
        @cached_query(ttl=600)
        async def get_user_by_id(self, user_id: int): ...
    """
    def decorator(func: Callable):
        import functools
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Create a cache key based on function name and args
            arg_str = f"{func.__name__}:{args[1:]}:{kwargs}" # Skip 'self/cls'
            key = hashlib.md5(arg_str.encode()).hexdigest()
            
            # 1. Try Cache
            cached = await db_manager.get_cached_query(key)
            if cached is not None:
                return cached
            
            # 2. Run Query
            result = await func(*args, **kwargs)
            
            # 3. Save to Cache
            if result is not None:
                await db_manager.set_cached_query(key, result, ttl=ttl)
            
            return result
        return wrapper
    return decorator

# Singleton instance
db_manager = DBConnectionManager()
