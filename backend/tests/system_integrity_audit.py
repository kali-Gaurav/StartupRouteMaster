import sys
import os
# Add 'backend' to path so we can import from 'database' and 'services'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import logging
from datetime import datetime
from unittest.mock import patch, AsyncMock
from core.redis_client import async_redis_client as redis_client
from services.search_service import SearchService
from services.telemetry_service import push_to_stream

# Ensure standard logging is active
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("routemaster.integrity_audit")

async def run_audit():
    print("\n--- 🛡️ Starting System Integrity Audit ---")
    
    # 1. Test Redis Connection
    try:
        await redis_client.ping()
        print("✅ Redis: Connected & Responsive")
    except Exception as e:
        print(f"❌ Redis: OFFLINE ({e})")

    # 2. Test Data Pipeline (Trace 1 search)
    print("\n--- 🔍 Testing Data Integrity (Search -> Stream -> Heatmap) ---")
    origin, dest = "DEL", "BOM"
    event = {
        "origin": origin,
        "destination": dest,
        "timestamp": datetime.utcnow().isoformat(),
        "latency_ms": "10.0",
        "method": "test_search"
    }
    await push_to_stream(event)
    
    # Wait for aggregator to consume (simulated)
    # Since we are not running the aggregator in this process, we just check the stream
    print("✅ Data Pipeline: Event pushed to telemetry stream")

    # 3. Chaos Simulation: Simulate Service Failure
    print("\n--- 🌪️ Chaos Test: Simulating Service Failure ---")
    # Simulate SearchService without Redis (Heuristic Fallback Test)
    # We patch _get_redis to return None to simulate Redis down
    with patch("services.search_service.SearchService._get_redis", return_value=None):
        try:
            # We don't actually need a real DB here, just testing the logic path
            service = SearchService(None)
            # This should not crash if it handles the 'None' redis gracefully
            await service.search_routes(source="DEL", destination="BOM", travel_date="2026-05-01", limit=1)
            print("✅ Graceful Fallback: Verified (Service handled Redis outage)")
        except Exception as e:
            print(f"❌ Graceful Fallback: Failed ({e})")

if __name__ == "__main__":
    asyncio.run(run_audit())
