import asyncio
import httpx
import logging
from typing import Dict, Any, Optional, List
from .service_discovery import ServiceRegistry
from .resilience import CircuitBreaker, retry_with_backoff

logger = logging.getLogger("routemaster.microservice_client")

class MicroserviceClient:
    """
    Task 7.7: API Gateway Gateway / Client.
    Discovers nodes, handles retries, and trips circuit breakers on failure.
    """
    def __init__(self, registry: ServiceRegistry):
        self.registry = registry
        self.circuits: Dict[str, CircuitBreaker] = {}
        self.client = httpx.AsyncClient(timeout=10.0)

    def _get_circuit(self, service_name: str) -> CircuitBreaker:
        if service_name not in self.circuits:
            self.circuits[service_name] = CircuitBreaker(service_name)
        return self.circuits[service_name]

    @retry_with_backoff(retries=3, base_delay=0.1)
    async def call(self, service_name: str, endpoint: str, method: str = "GET", params: Optional[Dict] = None, data: Optional[Dict] = None) -> Any:
        """
        [Task 7.8/7.9] Orchestrates the resilient call.
        """
        base_url = await self.registry.resolve_endpoint(service_name)
        if not base_url:
            raise Exception(f"Service '{service_name}' not available in registry.")

        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        circuit = self._get_circuit(service_name)

        async def _execute():
            if method.upper() == "GET":
                resp = await self.client.get(url, params=params)
            else:
                resp = await self.client.post(url, json=data)
            
            resp.raise_for_status()
            return resp.json()

        return await circuit.call(_execute)

    async def close(self):
        await self.client.aclose()
