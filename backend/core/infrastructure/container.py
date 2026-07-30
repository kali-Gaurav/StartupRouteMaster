import asyncio
import logging
import time
from typing import Dict, Any, Optional, Type, TypeVar
from .providers import ServiceProvider, ServiceStatus

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
    services: Dict[str, ServiceProvider]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ServiceContainer, cls).__new__(cls)
            cls._instance.services = {}
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
        if service.status in (ServiceStatus.HEALTHY, ServiceStatus.DEGRADED):
            return service

        async with service._init_lock:
            # Re-check status after lock
            if service.status in (ServiceStatus.HEALTHY, ServiceStatus.INITIALIZING, ServiceStatus.DEGRADED):
                return service

            service.status = ServiceStatus.INITIALIZING
            
            # Subtask 8.5: Retry on init failure
            for attempt in range(retry_limit + 1):
                try:
                    async with asyncio.timeout(timeout):
                        logger.info(f" IoC: Initializing '{name}' (Attempt {attempt+1})...")
                        await service.init()
                        # Only promote to HEALTHY if the service didn't set itself to DEGRADED
                        if service.status == ServiceStatus.INITIALIZING:
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

    async def burst_control(self, level: str):
        """
        [Task 122] Rapid Load-Shedding.
        Levels: NORMAL, WARM, HOT (Shed background), MELTDOWN (Shed non-core).
        """
        severity = {"NORMAL": 0, "WARM": 1, "HOT": 2, "MELTDOWN": 3}.get(level, 0)
        logger.warning(f"🚨 [NEXUS:SURGE] Scaling IoC Container to level: {level}")
        
        for name, svc in self.services.items():
            if severity >= 2 and svc.priority > 5: # Hot: Pause non-critical (priority 6+)
                await svc.pause()
            elif severity >= 3 and svc.priority > 2: # Meltdown: Pause everything except Core
                await svc.pause()
            elif severity == 0:
                await svc.resume()

    def get_all_status(self) -> Dict[str, Any]:
        """Returns the status, version, and metrics of all services."""
        statuses = {}
        for name, service in self.services.items():
            statuses[name] = {
                "status": service.status.value,
                "version": service.version,
                "priority": getattr(service, 'priority', 10),
                "error": service.error,
                "uptime": time.time() - getattr(service, '_init_time', time.time())
            }
        
        system_status = "online"
        if any(s.status == ServiceStatus.FAILED for s in self.services.values()):
            system_status = "degraded"
        
        return {
            "status": system_status,
            "services": statuses,
            "global_governance": "READY",
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
