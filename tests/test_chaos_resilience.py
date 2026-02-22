import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from backend.api.websockets import ConnectionManager
from backend.core.monitoring import REDIS_HEALTH_CHECKS, SYSTEM_DEGRADED_MODE

@pytest.mark.asyncio
async def test_redis_failure_degraded_mode():
    """Verify system enters Degraded Mode on Redis failure."""
    manager = ConnectionManager()
    
    # Mock redis to fail
    with patch("backend.api.websockets.aioredis.from_url", side_effect=Exception("Redis Connection Refused")):
        await manager.initialize()
        
        # Check metrics
        assert SYSTEM_DEGRADED_MODE.labels(reason="redis_failure")._value.get() == 1.0

@pytest.mark.asyncio
async def test_redis_recovery_from_degraded_mode():
    """Verify system recovers from Degraded Mode when Redis returns."""
    manager = ConnectionManager()
    
    # 1. Fail first
    with patch("backend.api.websockets.aioredis.from_url", side_effect=Exception("Redis Down")):
        await manager.initialize()
        assert SYSTEM_DEGRADED_MODE.labels(reason="redis_failure")._value.get() == 1.0
        
    # 2. Recover
    mock_redis = MagicMock()
    mock_redis.ping = AsyncMock(return_value=True)
    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock(return_value=None)
    mock_pubsub.psubscribe = AsyncMock(return_value=None)
    mock_redis.pubsub.return_value = mock_pubsub
    
    with patch("backend.api.websockets.aioredis.from_url", return_value=mock_redis):
        # We need to trigger initialize again. In production, _redis_listener does this.
        await manager.initialize()
        assert SYSTEM_DEGRADED_MODE.labels(reason="redis_failure")._value.get() == 0.0

@pytest.mark.asyncio
async def test_local_broadcast_fallback_on_redis_loss():
    """Verify that even if Redis is down, local broadcasts still work."""
    manager = ConnectionManager()
    
    # Mock a local websocket connection
    mock_ws = MagicMock()
    mock_ws.send_json = AsyncMock(return_value=None)
# directly add to sos_listeners since connect doesn't accept role
    manager.sos_listeners.append(mock_ws)
    
    # Simulation Redis is down
    manager.redis = None 
    # override initialize to prevent actual redis connections
    manager.initialize = AsyncMock(return_value=None)
    
    # Broadcast SOS
    sos_data = {"id": "123", "type": "fire"}
    await manager.broadcast_sos(sos_data)
    
    # Verify local send_json was still called
    mock_ws.send_json.assert_called()
    sent = mock_ws.send_json.call_args[0][0]
    assert sent["type"] == "sos_alert"
    assert sent["data"] == sos_data
