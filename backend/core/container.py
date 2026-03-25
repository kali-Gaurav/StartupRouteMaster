import asyncio
import logging
import time
from typing import Dict, Any, Optional, Type, TypeVar
from core.providers import ServiceProvider, ServiceStatus

logger = logging.getLogger("routemaster.container")

T = TypeVar("T", bound=ServiceProvider)

class ServiceContainer:
    """
    Task 8: Singleton Service Container (IoC).
    Replaces legacy JITManager with a cleaner DI pattern.
    Supports Lazy Loading, Timeouts, and Retries.
    """
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ServiceContainer, cls).__new__(cls)
            cls._instance.services: Dict[str, ServiceProvider] = {}
        return cls._instance

    def register(self, service: ServiceProvider):
        """Registers a service provider in the container."""
        self.services[service.name] = service
        logger.info(f" IoC: Registered '{service.name}' v{service.version}")

    async def get(self, name: str, timeout: float = 30.0, retry_limit: int = 2) -> Any:
        """
        Resolves a service by name. 
        Triggers lazy initialization if required.
        """
        if name not in self.services:
            raise ValueError(f"IoC: Service '{name}' not found in container.")

        service = self.services[name]
        if service.status == ServiceStatus.HEALTHY:
            return service

        async with service._init_lock:
            # Re-check status after lock
            if service.status in (ServiceStatus.HEALTHY, ServiceStatus.INITIALIZING):
                return service

            service.status = ServiceStatus.INITIALIZING
            
            # Subtask 8.5: Retry on init failure
            for attempt in range(retry_limit + 1):
                try:
                    async with asyncio.timeout(timeout):
                        logger.info(f" IoC: Initializing '{name}' (Attempt {attempt+1})...")
                        await service.init()
                        service.status = ServiceStatus.HEALTHY
                        return service
                except Exception as e:
                    logger.warning(f" IoC: '{name}' init failed: {e}")
                    if attempt < retry_limit:
                        await asyncio.sleep(1.0 * (attempt + 1))
                    else:
                        service.status = ServiceStatus.FAILED
                        service.error = str(e)
                        # Subtask 8.7: Fallback modes
                        await service.fallback()
                        return service

    def get_all_status(self) -> Dict[str, Any]:
        """Returns the status and version of all services in the container."""
        statuses = {
            name: {
                "status": service.status.value,
                "version": service.version,
                "error": service.error
            }
            for name, service in self.services.items()
        }
        # Aggregate status: online if all healthy/degraded, otherwise failed
        system_status = "online"
        if any(s.status == ServiceStatus.FAILED for s in self.services.values()):
            system_status = "degraded"
        
        return {
            "status": system_status,
            "services": statuses,
            "timestamp": time.time()
        }

    async def shutdown_all(self):
        """Graceful shutdown of all services."""
        for name, service in self.services.items():
            try:
                await service.shutdown()
                logger.info(f" IoC: Shut down '{name}'.")
            except Exception as e:
                logger.error(f"IoC: Error shutting down '{name}': {e}")

# Global Instance
container = ServiceContainer()
