import asyncio
import json
import uuid
import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from backend.api.websockets import ConnectionManager
from backend.services.multi_layer_cache import multi_layer_cache

async def test_distributed_sync():
    print("\n--- Phase 13: Distributed Sync Verification ---")
    
    # Initialize two separate "instances" of ConnectionManager
    # In a real app, these would be on different processes/servers
    manager1 = ConnectionManager()
    manager2 = ConnectionManager()
    
    await manager1.initialize()
    await manager2.initialize()
    
    # Store results
    received_by_instance2 = []
    
    # Mock a websocket connection for instance 2
    class MockWebSocket:
        def __init__(self):
            self.sent_messages = []
        async def accept(self):
            pass
        async def send_text(self, text):
            self.sent_messages.append(json.loads(text))
            received_by_instance2.append(json.loads(text))
    
    mock_ws = MockWebSocket()
    await manager2.connect(mock_ws)
    await manager2.subscribe_to_train(mock_ws, "TRAIN123")
    print("Instance 2: Subscriber connected to TRAIN123")
    
    # Instance 1 publishes a position
    test_payload = {
        "train_number": "TRAIN123",
        "lat": 28.6139,
        "lon": 77.2090,
        "timestamp": "2023-10-27T12:00:00Z"
    }
    
    print("Instance 1: Publishing position for TRAIN123")
    await manager1.broadcast_to_train("TRAIN123", test_payload)
    
    # Wait for Pub/Sub propagation
    await asyncio.sleep(0.5)
    
    # Verify Instance 2 received it
    if len(received_by_instance2) > 0:
        print(f"✅ SUCCESS: Instance 2 received distributed update: {received_by_instance2[0]}")
    else:
        print("❌ FAILURE: Instance 2 did not receive the update via Redis Pub/Sub")
    
    # Verify State Sync (Catch-up)
    print("\n--- Phase 13: State Sync (Catch-up) Verification ---")
    
    # Pre-cache a position in Redis manually (simulating the broadcaster)
    last_pos = {
        "train_number": "TRAIN123",
        "lat": 25.18,
        "lon": 80.18,
        "status": "cached"
    }
    history_key = "pos:last:TRAIN123"
    await multi_layer_cache.initialize()
    if multi_layer_cache.redis:
        await multi_layer_cache.redis.setex(history_key, 60, json.dumps(last_pos))
    else:
        print("⚠️ Redis not available in multi_layer_cache")
    
    # Instance 3 joins fresh
    manager3 = ConnectionManager()
    await manager3.initialize()
    
    received_by_instance3 = []
    class MockWS3:
        async def accept(self):
            pass
        async def send_text(self, text):
            received_by_instance3.append(json.loads(text))
            
    mock_ws3 = MockWS3()
    print("Instance 3: New subscriber connecting to TRAIN123")
    await manager3.connect(mock_ws3)
    await manager3.subscribe_to_train(mock_ws3, "TRAIN123")
    
    # Check if they got the cached position immediately
    if len(received_by_instance3) > 0 and received_by_instance3[0].get("status") == "cached":
        print(f"✅ SUCCESS: Instance 3 received 'last known position' catch-up: {received_by_instance3[0]}")
    else:
        print("❌ FAILURE: Instance 3 did not receive catch-up data")

    # Cleanup
    await manager1.disconnect(None, "TRAIN123") # Doesn't matter for mock
    await manager2.redis.close()
    await manager1.redis.close()
    await manager3.redis.close()

if __name__ == "__main__":
    asyncio.run(test_distributed_sync())
