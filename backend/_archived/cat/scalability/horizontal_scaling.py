"""
Horizontal scaling configuration for the Contextual Availability Transformer (CAT) system.

Implements stateless inference service, connection pooling, and graceful shutdown.
"""

import asyncio
import logging
import signal
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from enum import Enum

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ShutdownState(Enum):
    """State of the graceful shutdown process."""
    RUNNING = "running"
    DRAINING = "draining"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"


@dataclass
class ConnectionPoolConfig:
    """
    Configuration for HTTP connection pooling.
    
    Controls connection behavior for external API calls.
    """
    max_connections: int = 100
    max_keepalive_connections: int = 20
    pool_timeout: float = 30.0
    pool_recycle: int = 3600  # Recycle connections after 1 hour
    pool_heartbeat: int = 60  # Send keepalive every 60 seconds
    retry_attempts: int = 3
    retry_backoff_factor: float = 0.5
    retry_max_delay: float = 10.0


class ConnectionPool:
    """
    Manages HTTP connection pooling for external API calls.
    
    Provides efficient reuse of connections and handles connection lifecycle.
    """
    
    def __init__(self, config: ConnectionPoolConfig = None):
        """
        Initialize the connection pool.
        
        Args:
            config: Connection pool configuration
        """
        self.config = config or ConnectionPoolConfig()
        self._client: Optional[httpx.AsyncClient] = None
        self._active_connections: int = 0
        self._total_requests: int = 0
        self._last_recycle: float = time.time()
        self._lock = asyncio.Lock()
    
    async def _create_client(self) -> httpx.AsyncClient:
        """Create a new HTTP client with connection pooling."""
        return httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=self.config.max_connections,
                max_keepalive_connections=self.config.max_keepalive_connections,
                pool_timeout=self.config.pool_timeout
            ),
            timeout=httpx.Timeout(
                connect=10.0,
                read=30.0,
                write=10.0,
                pool=10.0
            ),
            headers={
                "User-Agent": "CAT-Inference-Service/1.0",
                "Connection": "keep-alive"
            }
        )
    
    async def get_client(self) -> httpx.AsyncClient:
        """
        Get or create an HTTP client from the pool.
        
        Returns:
            Configured HTTP client
        """
        async with self._lock:
            if self._client is None:
                self._client = await self._create_client()
                logger.info("Created new HTTP client with connection pooling")
            
            # Recycle connections periodically
            if time.time() - self._last_recycle > self.config.pool_recycle:
                await self._recycle_connections()
            
            self._active_connections += 1
            self._total_requests += 1
            return self._client
    
    async def _recycle_connections(self) -> None:
        """Recycle connections in the pool."""
        if self._client:
            await self._client.aclose()
            self._client = await self._create_client()
            self._last_recycle = time.time()
            logger.info("Recycled HTTP client connections")
    
    async def release_client(self, client: httpx.AsyncClient) -> None:
        """
        Release a client back to the pool.
        
        Args:
            client: HTTP client to release
        """
        async with self._lock:
            if self._active_connections > 0:
                self._active_connections -= 1
    
    async def close(self) -> None:
        """Close all connections in the pool."""
        async with self._lock:
            if self._client:
                await self._client.aclose()
                self._client = None
                logger.info("Closed HTTP client connections")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        return {
            "active_connections": self._active_connections,
            "total_requests": self._total_requests,
            "max_connections": self.config.max_connections,
            "max_keepalive_connections": self.config.max_keepalive_connections,
            "pool_recycle_interval": self.config.pool_recycle,
            "last_recycle_seconds_ago": int(time.time() - self._last_recycle)
        }


def create_connection_pool(config: ConnectionPoolConfig = None) -> ConnectionPool:
    """
    Factory function to create a connection pool.
    
    Args:
        config: Connection pool configuration
        
    Returns:
        Configured ConnectionPool instance
    """
    return ConnectionPool(config)


class GracefulShutdownManager:
    """
    Manages graceful shutdown for instance rotation.
    
    Ensures in-flight requests complete before shutdown.
    """
    
    def __init__(self, shutdown_timeout: float = 30.0):
        """
        Initialize the graceful shutdown manager.
        
        Args:
            shutdown_timeout: Maximum time to wait for graceful shutdown
        """
        self.shutdown_timeout = shutdown_timeout
        self._state = ShutdownState.RUNNING
        self._in_flight_requests: int = 0
        self._start_time: float = time.time()
        self._shutdown_event: Optional[asyncio.Event] = None
        self._drain_timeout: float = 10.0  # Time to wait for requests to complete
        self._lock = asyncio.Lock()
    
    def increment_in_flight(self) -> None:
        """Increment the count of in-flight requests."""
        import asyncio
        if asyncio.current_task():
            asyncio.create_task(self._increment_async())
    
    async def _increment_async(self) -> None:
        """Async version of increment_in_flight."""
        async with self._lock:
            if self._state == ShutdownState.RUNNING:
                self._in_flight_requests += 1
    
    def decrement_in_flight(self) -> None:
        """Decrement the count of in-flight requests."""
        import asyncio
        if asyncio.current_task():
            asyncio.create_task(self._decrement_async())
    
    async def _decrement_async(self) -> None:
        """Async version of decrement_in_flight."""
        async with self._lock:
            if self._in_flight_requests > 0:
                self._in_flight_requests -= 1
    
    async def start_drain(self) -> bool:
        """
        Start the drain phase of graceful shutdown.
        
        Returns:
            True if drain started successfully
        """
        async with self._lock:
            if self._state != ShutdownState.RUNNING:
                return False
            
            self._state = ShutdownState.DRAINING
            logger.info("Started graceful shutdown drain phase")
            return True
    
    async def wait_for_drain(self) -> bool:
        """
        Wait for all in-flight requests to complete.
        
        Returns:
            True if all requests completed, False if timeout reached
        """
        start_time = time.time()
        
        while self._in_flight_requests > 0:
            elapsed = time.time() - start_time
            if elapsed > self._drain_timeout:
                logger.warning(
                    f"Drain timeout reached with {self._in_flight_requests} "
                    f"in-flight requests remaining"
                )
                return False
            
            await asyncio.sleep(0.1)
        
        return True
    
    async def shutdown(self) -> None:
        """Perform graceful shutdown."""
        async with self._lock:
            if self._state == ShutdownState.RUNNING:
                await self.start_drain()
            
            if self._state == ShutdownState.DRAINING:
                # Wait for drain
                await self.wait_for_drain()
                self._state = ShutdownState.SHUTTING_DOWN
        
        logger.info("Graceful shutdown completed")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get shutdown manager statistics."""
        return {
            "state": self._state.value,
            "in_flight_requests": self._in_flight_requests,
            "uptime_seconds": int(time.time() - self._start_time),
            "shutdown_timeout_seconds": self.shutdown_timeout
        }


class StatelessInferenceService:
    """
    Stateless inference service wrapper for horizontal scaling.
    
    Makes the inference service stateless by externalizing session state.
    """
    
    def __init__(
        self,
        app: FastAPI,
        connection_pool: ConnectionPool = None,
        shutdown_manager: GracefulShutdownManager = None
    ):
        """
        Initialize the stateless inference service.
        
        Args:
            app: FastAPI application
            connection_pool: Connection pool for external APIs
            shutdown_manager: Graceful shutdown manager
        """
        self.app = app
        self.connection_pool = connection_pool or create_connection_pool()
        self.shutdown_manager = shutdown_manager or GracefulShutdownManager()
        
        # Add middleware for request tracking
        self._add_middleware()
        
        # Add shutdown handlers
        self._add_shutdown_handlers()
    
    def _add_middleware(self) -> None:
        """Add middleware for request tracking and connection management."""
        
        @self.app.middleware("http")
        async def track_requests(request: Request, call_next):
            """Track in-flight requests for graceful shutdown."""
            self.shutdown_manager.increment_in_flight()
            
            try:
                response = await call_next(request)
                return response
            finally:
                self.shutdown_manager.decrement_in_flight()
        
        @self.app.middleware("http")
        async def add_connection_pooling(request: Request, call_next):
            """Add connection pool headers to requests."""
            response = await call_next(request)
            
            # Add connection pool stats to response headers
            pool_stats = self.connection_pool.get_stats()
            response.headers["X-Connection-Pool-Active"] = str(pool_stats["active_connections"])
            response.headers["X-Connection-Pool-Total"] = str(pool_stats["total_requests"])
            
            return response
    
    def _add_shutdown_handlers(self) -> None:
        """Add shutdown event handlers."""
        
        @self.app.on_event("shutdown")
        async def on_shutdown():
            """Handle application shutdown."""
            logger.info("Application shutdown initiated")
            await self.shutdown_manager.shutdown()
            await self.connection_pool.close()
            logger.info("Application shutdown complete")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check for load balancer.
        
        Returns:
            Health check status
        """
        return {
            "status": "healthy",
            "shutdown_state": self.shutdown_manager._state.value,
            "in_flight_requests": self.shutdown_manager._in_flight_requests,
            "connection_pool": self.connection_pool.get_stats()
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {
            "shutdown": self.shutdown_manager.get_stats(),
            "connection_pool": self.connection_pool.get_stats()
        }


def create_stateless_service(
    app: FastAPI,
    connection_pool_config: ConnectionPoolConfig = None,
    shutdown_timeout: float = 30.0
) -> StatelessInferenceService:
    """
    Factory function to create a stateless inference service.
    
    Args:
        app: FastAPI application
        connection_pool_config: Connection pool configuration
        shutdown_timeout: Graceful shutdown timeout
        
    Returns:
        Configured StatelessInferenceService instance
    """
    connection_pool = create_connection_pool(connection_pool_config)
    shutdown_manager = GracefulShutdownManager(shutdown_timeout)
    
    return StatelessInferenceService(app, connection_pool, shutdown_manager)
