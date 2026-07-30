import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from providers.gateway import ProviderGateway

MOCK_NTES_DATA = {
    "train_no": "12345",
    "current_station": "NDLS",
    "delay_info": "On Time",
    "scraped_at": "2024-03-23T12:00:00"
}

@pytest.fixture
def gateway():
    with patch('backend.providers.gateway.AsyncSessionUser'), \
         patch('backend.providers.gateway.cache_system.get', return_value=None), \
         patch('backend.providers.gateway.cache_system.put', return_value=None), \
         patch('backend.providers.gateway.RETRY_DELAY_SECONDS', 0.0), \
         patch('backend.providers.gateway.MAX_RETRIES', 0):
        gw = ProviderGateway()
        gw._is_budget_ok = AsyncMock(return_value=True)
        gw._record_api_cost = AsyncMock()
        return gw

@pytest.mark.asyncio
async def test_rapidapi_failover_to_ntes(gateway):
    gateway.rapidapi_client.get_live_status = AsyncMock(side_effect=Exception("RapidAPI Fail"))
    gateway.ntes_client.get_live_status = AsyncMock(return_value=MOCK_NTES_DATA)
    
    status = await gateway.get_live_status("12345", "2024-03-23")
    
    assert status is not None
    assert gateway.rapidapi_client.get_live_status.called
    assert gateway.ntes_client.get_live_status.called

@pytest.mark.asyncio
async def test_budget_enforcement(gateway):
    gateway._is_budget_ok = AsyncMock(return_value=False)
    gateway.rapidapi_client.get_live_status = AsyncMock()
    gateway.ntes_client.get_live_status = AsyncMock(return_value=MOCK_NTES_DATA)
    
    await gateway.get_live_status("12345", "2024-03-23")
    
    assert not gateway.rapidapi_client.get_live_status.called
    # Use a small wait if necessary, but it's sync in the wrapper call
    assert gateway.ntes_client.get_live_status.called
