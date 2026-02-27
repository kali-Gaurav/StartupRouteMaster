import logging
import httpx
import asyncio
from datetime import datetime
from pybreaker import CircuitBreakerError

from services.redirect_service import redirect_service
from services.cache_service import cache_service # New: Import cache_service

logger = logging.getLogger(__name__)

async def run_partner_health_check_task():
    """
    Asynchronous task to periodically check the health of partner redirect URLs.
    Logs the status of each partner and stores it in Redis.
    """
    logger.info("Starting partner health check task.")
    
    partners_to_check = redirect_service.partners.keys()
    
    async with httpx.AsyncClient() as client:
        tasks = []
        for partner_name in partners_to_check:
            partner_config = redirect_service.partners.get(partner_name)
            if not partner_config or not partner_config.get("base_url"):
                logger.warning(f"Partner '{partner_name}' has no base_url configured, skipping health check.")
                continue
            
            base_url = partner_config["base_url"]
            tasks.append(check_single_partner(client, partner_name, base_url))
        
        await asyncio.gather(*tasks)
            
    logger.info("Finished partner health check task.")

async def check_single_partner(client: httpx.AsyncClient, partner_name: str, url: str):
    """
    Checks the health of a single partner URL and stores the status in Redis.
    """
    status_key = f"partner_health:{partner_name}"
    try:
        # Use circuit breaker to protect against cascading failures
        @redirect_service.partner_breaker
        async def _check():
            return await client.get(url, timeout=5)
        
        response = await _check()
        if response.status_code == 200:
            logger.info(f"Partner '{partner_name}' ({url}) is UP. Status: {response.status_code}")
            if cache_service.is_available():
                cache_service.set(status_key, "UP", ttl=60 * 5) # Cache status for 5 minutes
        else:
            logger.warning(f"Partner '{partner_name}' ({url}) is DOWN/Degraded. Status: {response.status_code}")
            if cache_service.is_available():
                cache_service.set(status_key, "DOWN", ttl=60 * 5) # Cache status for 5 minutes
    except CircuitBreakerError as exc:
        logger.error(f"Partner '{partner_name}' ({url}) circuit breaker open: {exc}")
        if cache_service.is_available():
            cache_service.set(status_key, "CIRCUIT_OPEN", ttl=60 * 5)
    except httpx.RequestError as exc:
        logger.error(f"Partner '{partner_name}' ({url}) health check failed due to request error: {exc}")
        if cache_service.is_available():
            cache_service.set(status_key, "DOWN", ttl=60 * 5) # Cache status for 5 minutes
    except Exception as exc:
        logger.error(f"Partner '{partner_name}' ({url}) health check failed due to unexpected error: {exc}")
        if cache_service.is_available():
            cache_service.set(status_key, "DOWN", ttl=60 * 5) # Cache status for 5 minutes

if __name__ == "__main__":
    # Example of how to run the task independently for testing
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_partner_health_check_task())
