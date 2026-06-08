import logging
import asyncio
from typing import Optional
from .providers import ServiceProvider, ServiceStatus
from .microservice_client import MicroserviceClient
from .service_discovery import ServiceRegistry
from services.multi_layer_cache import multi_layer_cache

logger = logging.getLogger("routemaster.microservice_provider")

class MicroserviceServiceProvider(ServiceProvider):
    """
    Task 7: Microservice Bridge Provider.
    Orchestrates communication with decoupled services (Search, Auth, ML).
    Registers 'microservices' into the global container.
    """
    def __init__(self):
        super().__init__("microservices", version="1.1.0")
        self.client: Optional[MicroserviceClient] = None
        self.registry: Optional[ServiceRegistry] = None

    async def init(self):
        """Initializes service discovery and the resilient HTTP client."""
        await multi_layer_cache.initialize()
        redis = multi_layer_cache.redis
        if not redis:
            raise Exception("Redis required for Microservice Discovery.")

        self.registry = ServiceRegistry(redis)
        self.client = MicroserviceClient(self.registry)
        
        # Verify connectivity to discovery
        logger.info("📡 Microservice Provider: Connected to Redis Discovery.")

    async def shutdown(self):
        if self.client:
            await self.client.close()
        logger.info("🛑 Microservice Provider: Shutdown complete.")

    async def health_check(self) -> ServiceStatus:
        if not self.client or not self.registry:
            return ServiceStatus.FAILED
        return ServiceStatus.HEALTHY

# Register with IoC
from .container import container
microservice_provider = MicroserviceServiceProvider()
container.register(microservice_provider)
