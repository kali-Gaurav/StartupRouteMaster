import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Any, Dict

logger = logging.getLogger("routemaster.ioc")

class ServiceStatus(Enum):
    PENDING = "pending"
    INITIALIZING = "initializing"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"

class ServiceProvider(ABC):
    """
    Task 8: Base Service Provider for IoC Container.
    Handles lifecycle, health, and fallback logic.
    """
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.status = ServiceStatus.PENDING
        self.error: Optional[str] = None
        self._init_lock = asyncio.Lock()

    @abstractmethod
    async def init(self):
        """Override with actual initialization logic."""
        pass

    async def initialize(self):
        """[Task 27.11] Backward compatibility alias for init."""
        await self.init()

    async def shutdown(self):
        """Standard cleanup hook. Re-implement in child classes if needed."""
        self.status = ServiceStatus.PENDING
        pass

    async def health_check(self) -> ServiceStatus:
        """Override with deep health check logic."""
        return self.status

    async def fallback(self):
        """Called if init fails after all retries."""
        logger.warning(f"⚠️ Service '{self.name}' entering fallback mode.")
        self.status = ServiceStatus.DEGRADED
