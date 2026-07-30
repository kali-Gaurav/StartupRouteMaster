import asyncio
import logging
import sys
import os

# FORCE DEVELOPMENT MODE
os.environ["ENVIRONMENT"] = "development"
os.environ["SLIM_MODE"] = "false"

from httpx import AsyncClient, ASGITransport
from app import app
from core.nexus.bootstrapper import nexus_boot
from core.nexus.transit.reconciler import transit_node
from core.nexus.transit.stream import transit_streamer

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("verify-sse")

async def test_sse_broadcast():
    logger.info("[NEXUS:TEST] Phase 2: SSE Byte-Level Audit...")
    
    # 1. Bootstrap Core
    from core.nexus.security.node import security_node
    from core.nexus.cache.node import cache_node
    from core.nexus.database.node import database_node
    from core.nexus.financial.node import financial_node
    from core.nexus.scraper.node import scraper_node
    from core.nexus.search.node import search_node
    
    nexus_boot.register(security_node)
    nexus_boot.register(cache_node)
    nexus_boot.register(database_node)
    nexus_boot.register(financial_node)
    nexus_boot.register(scraper_node)
    nexus_boot.register(search_node)
    nexus_boot.register(transit_node)
    
    await nexus_boot.bootstrap()
    
    # 2. Start Raw SSE Consumer
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        async def consume_raw():
            try:
                # Request the stream
                async with client.stream("GET", "/api/v3/transit/stream", timeout=30.0) as response:
                    logger.info(f"[NEXUS:TEST] Connection Established. Code: {response.status_code}")
                    async for chunk in response.aiter_bytes():
                        decoded = chunk.decode('utf-8')
                        logger.info(f"[NEXUS:TEST] CHUNK RECEIVED: {repr(decoded)}")
                        if "data:" in decoded:
                            logger.info("[NEXUS:TEST] FOUND DATA MARKER.")
                            return True
            except Exception as e:
                logger.error(f"[NEXUS:TEST] Consumer Critical Failure: {e}")
            return False

        consumer = asyncio.create_task(consume_raw())
        
        # 3. Trigger Broadcast
        logger.info("[NEXUS:TEST] Awaiting warmup...")
        await asyncio.sleep(5)
        
        logger.info("[NEXUS:TEST] Triggering Fiber Broadcast...")
        await transit_streamer.broadcast({
            "status": "FIBER_VERIFIED",
            "timestamp": "NEXUS_P2_STABLE"
        })
        
        try:
            success = await asyncio.wait_for(consumer, timeout=10.0)
            if success:
                logger.info("[NEXUS:TEST] SUCCESS: Nexus Fiber Real-time Propagation Verified.")
            else:
                logger.error("[NEXUS:TEST] FAILURE: Fiber Stream severed without data.")
        except asyncio.TimeoutError:
             logger.error("[NEXUS:TEST] FAILURE: Connectivity Timeout (Gate potentially blocking chunks).")
             consumer.cancel()

if __name__ == "__main__":
    asyncio.run(test_sse_broadcast())
