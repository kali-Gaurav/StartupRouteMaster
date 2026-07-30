"""
Read Replica Management & Failover

Manages primary and replica database connections with automatic failover.
Replicas are used for read queries (SELECT), primary for writes (INSERT/UPDATE/DELETE).
"""

import logging
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, text, Engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
import asyncio

logger = logging.getLogger("db-replication")


class ReplicationManager:
    """Manages primary and replica database connections with failover."""

    def __init__(
        self,
        primary_url: str,
        replica_urls: List[str],
        pool_size: int = 10,
        max_overflow: int = 20,
        is_async: bool = False,
        pool_pre_ping: bool = True,
    ):
        """
        Initialize replication manager.

        Args:
            primary_url: Primary database connection string
            replica_urls: List of replica database connection strings
            pool_size: SQLAlchemy pool size
            max_overflow: SQLAlchemy max overflow
            is_async: Whether to use async engines
            pool_pre_ping: Enable connection health checks
        """
        self.primary_url = primary_url
        self.replica_urls = replica_urls or []
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.is_async = is_async
        self.pool_pre_ping = pool_pre_ping

        self.primary_engine: Optional[Engine | AsyncEngine] = None
        self.replica_engines: List[Engine | AsyncEngine] = []
        self.current_replica_index = 0
        self.replica_health: Dict[int, bool] = {}  # replica_index -> is_healthy
        self.replication_lag_ms: Dict[int, float] = {}  # replica_index -> lag in ms
        self._health_check_task: Optional[asyncio.Task] = None
        self._lock: Optional[asyncio.Lock] = None

    async def initialize(self):
        """Initialize primary and replica engines."""
        self._lock = asyncio.Lock()
        engine_kwargs = self._get_engine_kwargs()

        # Create primary engine
        if self.is_async:
            self.primary_engine = create_async_engine(self.primary_url, **engine_kwargs)
        else:
            self.primary_engine = create_engine(self.primary_url, **engine_kwargs)

        # Create replica engines
        for i, replica_url in enumerate(self.replica_urls):
            if self.is_async:
                engine = create_async_engine(replica_url, **engine_kwargs)
            else:
                engine = create_engine(replica_url, **engine_kwargs)
            self.replica_engines.append(engine)
            self.replica_health[i] = True
            self.replication_lag_ms[i] = 0.0

        # Start health check task
        if self.is_async:
            self._health_check_task = asyncio.create_task(self._health_check_loop())

        logger.info(f"✅ Replication initialized: 1 primary + {len(self.replica_engines)} replicas")

    def _get_engine_kwargs(self) -> Dict[str, Any]:
        """Get SQLAlchemy engine kwargs."""
        kwargs: Dict[str, Any] = {
            "execution_options": {"timeout": 30},
        }

        # SQLite doesn't support pool_size, max_overflow, pool_pre_ping
        if "sqlite" not in self.primary_url:
            kwargs["pool_pre_ping"] = self.pool_pre_ping
            kwargs["pool_size"] = self.pool_size
            kwargs["max_overflow"] = self.max_overflow

        # PostgreSQL-specific settings
        if "postgresql" in self.primary_url:
            kwargs["pool_recycle"] = 1800
            if self.is_async:
                import ssl
                ssl_ctx = ssl.create_default_context()
                kwargs["connect_args"] = {
                    "statement_cache_size": 0,
                    "ssl": ssl_ctx,
                }

        return kwargs

    async def _health_check_loop(self):
        """Periodically check replica health and replication lag."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                await self._check_all_replicas()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")

    async def _check_all_replicas(self):
        """Check health and lag for all replicas."""
        for i, engine in enumerate(self.replica_engines):
            try:
                await self._check_replica_health(i, engine)
            except Exception as e:
                logger.warning(f"Replica {i} health check failed: {e}")
                self.replica_health[i] = False

    async def _check_replica_health(self, index: int, engine: Engine | AsyncEngine):
        """Check if replica is healthy and measure replication lag."""
        try:
            if self.is_async:
                async with engine.connect() as conn:
                    # Check connection
                    result = await conn.execute(text("SELECT 1"))
                    result.close()

                    # Measure replication lag (PostgreSQL specific)
                    try:
                        lag_result = await conn.execute(
                            text("SELECT EXTRACT(EPOCH FROM (NOW() - pg_last_xact_replay_timestamp())) * 1000 as lag_ms")
                        )
                        lag_row = await lag_result.fetchone()
                        if lag_row:
                            self.replication_lag_ms[index] = float(lag_row[0] or 0)
                    except Exception:
                        pass  # Lag measurement failed, but connection is OK

                    self.replica_health[index] = True
            else:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                    self.replica_health[index] = True
        except Exception as e:
            logger.warning(f"Replica {index} failed health check: {e}")
            self.replica_health[index] = False

    def get_primary_engine(self) -> Engine | AsyncEngine:
        """Get primary database engine."""
        if self.primary_engine is None:
            raise RuntimeError("Replication manager not initialized")
        return self.primary_engine

    def get_replica_engine_sync(self, fallback_to_primary: bool = True) -> Engine | AsyncEngine:
        """
        Get a healthy replica engine (synchronous version).
        Falls back to primary if no replicas available.

        Args:
            fallback_to_primary: If True, fallback to primary when no healthy replicas

        Returns:
            A healthy replica engine, or primary if fallback_to_primary=True
        """
        if not self.replica_engines:
            if fallback_to_primary:
                logger.debug("No replicas configured, using primary")
                return self.get_primary_engine()
            raise RuntimeError("No replica engines available")

        for _ in range(len(self.replica_engines)):
            replica_index = self.current_replica_index % len(self.replica_engines)
            self.current_replica_index += 1

            if self.replica_health.get(replica_index, False):
                engine = self.replica_engines[replica_index]
                logger.debug(f"Using replica {replica_index} (lag: {self.replication_lag_ms.get(replica_index, 0):.0f}ms)")
                return engine

        if fallback_to_primary:
            logger.warning("No healthy replicas, falling back to primary")
            return self.get_primary_engine()
        else:
            raise RuntimeError("No healthy replica engines available")

    async def get_replica_engine(self, fallback_to_primary: bool = True) -> Engine | AsyncEngine:
        """
        Get a healthy replica engine. Falls back to primary if no replicas available.

        Args:
            fallback_to_primary: If True, fallback to primary when no healthy replicas

        Returns:
            A healthy replica engine, or primary if fallback_to_primary=True
        """
        if not self.replica_engines:
            if fallback_to_primary:
                logger.debug("No replicas configured, using primary")
                return self.get_primary_engine()
            raise RuntimeError("No replica engines available")

        if self._lock is None:
            raise RuntimeError("Replication manager not initialized")

        async with self._lock:
            # Find next healthy replica
            for _ in range(len(self.replica_engines)):
                replica_index = self.current_replica_index % len(self.replica_engines)
                self.current_replica_index += 1

                if self.replica_health.get(replica_index, False):
                    engine = self.replica_engines[replica_index]
                    logger.debug(f"Using replica {replica_index} (lag: {self.replication_lag_ms.get(replica_index, 0):.0f}ms)")
                    return engine

            # No healthy replicas
            if fallback_to_primary:
                logger.warning("No healthy replicas, falling back to primary")
                return self.get_primary_engine()
            else:
                raise RuntimeError("No healthy replica engines available")

    def get_replica_lag(self, replica_index: int) -> float:
        """Get replication lag for a replica in milliseconds."""
        return self.replication_lag_ms.get(replica_index, 0.0)

    def is_replica_healthy(self, replica_index: int) -> bool:
        """Check if a replica is healthy."""
        return self.replica_health.get(replica_index, False)

    async def shutdown(self):
        """Shutdown all engines."""
        if self._health_check_task:
            self._health_check_task.cancel()

        if self.primary_engine:
            if self.is_async:
                await self.primary_engine.dispose()
            else:
                self.primary_engine.dispose()

        for engine in self.replica_engines:
            if self.is_async:
                await engine.dispose()
            else:
                engine.dispose()


# Global replication managers (one per database)
_transit_replication_manager: Optional[ReplicationManager] = None


async def initialize_transit_replicas(
    primary_url: str,
    replica_urls: Optional[List[str]] = None,
    **kwargs,
) -> ReplicationManager:
    """Initialize read replicas for transit database."""
    global _transit_replication_manager

    if replica_urls is None:
        replica_urls = []

    _transit_replication_manager = ReplicationManager(
        primary_url=primary_url,
        replica_urls=replica_urls,
        **kwargs,
    )
    await _transit_replication_manager.initialize()
    return _transit_replication_manager


def get_transit_replication_manager() -> Optional[ReplicationManager]:
    """Get the transit database replication manager."""
    return _transit_replication_manager
