import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# --- Import necessary modules ---
# Import Pydantic models and Gateway
from providers.models import UnifiedLiveStatus
from providers.gateway import provider_gateway
from providers.config import config as provider_config
from database.config import Config
# from core.redis import async_redis_client # Gateway manages its cache interaction

logger = logging.getLogger(__name__)

# Existing request coalescing logic (now handled by ProviderGateway or to be removed)
# _inflight_live_status: Dict[str, asyncio.Future] = {}

class LiveStatusService:
    """
    Service responsible for providing live train status information.
    Now delegates all fetching to the ProviderGateway.
    """
    # Removed aiohttp session management as it's no longer directly used for fetching.
    # If the service needs to *use* the gateway's output, it will receive normalized data.

    def __init__(self):
        # The service now relies on the ProviderGateway for fetching.
        # Any direct configuration like base_url or enabled flags might become
        # implicit through the gateway's provider configuration or explicit checks.
        
        # We can use provider_config to check if providers are enabled, if needed.
        # Example: Check if RapidAPI or NTES is configured.
        self.is_live_status_provider_available = bool(provider_config.RAPIDAPI_KEY) or bool(Config.ENABLE_LIVE_STATUS) # Placeholder check. Actual check should be more robust.
        
        # Cache TTL is now managed by the ProviderGateway.
        # self.cache_ttl = 60 # This line is removed.

        logger.info("LiveStatusService initialized. Fetching will be delegated to ProviderGateway.")

    async def get_live_status(self, train_number: str) -> Optional[Dict[str, Any]]:
        """
        Fetches live status for a specific train number by delegating to the ProviderGateway.
        
        This method now acts as a facade, calling the unified gateway and returning
        its normalized data. It removes direct API calls, custom caching, and
        request coalescing logic, as these are handled by the gateway.
        """
        # Check if live status fetching is generally enabled.
        # This check might need refinement: does it mean if *any* provider is available, or if the service itself is enabled?
        # For now, assume it means if we have *some* configured provider.
        if not self.is_live_status_provider_available:
            logger.warning("Live status fetching is disabled. No providers configured or enabled.")
            return None
            
        # --- Delegate to ProviderGateway ---
        # The ProviderGateway's get_live_status requires train_date.
        # This service's original signature didn't have train_date.
        # We need to decide how to obtain train_date here.
        # For now, as a placeholder, we'll use today's date, but this needs to be addressed.
        # A better approach might be to pass train_date if available, or infer it.
        today_date_str = datetime.utcnow().strftime('%Y-%m-%d')
        
        logger.debug(f"Delegating live status fetch for train {train_number} to ProviderGateway.")
        
        # Call the gateway
        unified_live_status = await provider_gateway.get_live_status(train_number, train_date=today_date_str)
        
        # The gateway returns a UnifiedLiveStatus object or None.
        # If the downstream code expects a Dict[str, Any], we need to convert it.
        if unified_live_status:
            # Return the model's dictionary representation, matching old signature expectation
            return unified_live_status.model_dump()
        else:
            logger.warning(f"ProviderGateway returned no live status for train {train_number}.")
            return None

    # Removed _execute_fetch, _normalize_response, _inflight_live_status logic
    # as they are now handled by the ProviderGateway and its clients/cache.

    # Removed cache and session management as they are now handled by ProviderGateway.

# --- Singleton instance ---
# This service would likely be instantiated and managed by the IoC container.
# For demonstration, we assume it's instantiated somewhere.
# live_status_service = LiveStatusService() 
