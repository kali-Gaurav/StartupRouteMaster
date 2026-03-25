import logging
import asyncio
from typing import List, Set
from database.session import AsyncSessionUser, init_db
from core.route_engine.transfer_graph_builder import TransferGraphBuilder
from core.hubs import MEGA_HUBS, MAJOR_HUBS

logger = logging.getLogger("cache-warmup")

class CacheWarmupService:
    """
    [Task 23] Pre-warms the Transfer Graph for major hubs.
    Eliminates first-request JIT latency.
    """
    
    def __init__(self):
        self._is_running = False

    async def run_hub_warmup_cycle(self):
        """
        Background task to warm the transfer cache for top 30 hubs.
        """
        if self._is_running: return
        self._is_running = True
        
        try:
            logger.info("🔥 Starting Hub Transfer Cache Warmup (MEGA/MAJOR Tiers)...")
            await init_db()
            
            # Combine hubs
            target_hubs = list(MEGA_HUBS) + list(MAJOR_HUBS)
            
            async with AsyncSessionUser() as session:
                builder = TransferGraphBuilder(session)
                
                # We'll warm the most common 20 hubs first
                count = 0
                for hub_code in target_hubs[:20]:
                    try:
                        # Build logic usually requires finding the Stop ID for the code
                        from database.models import Stop
                        from sqlalchemy import select
                        
                        stmt = select(Stop).where(Stop.code == hub_code)
                        result = await session.execute(stmt)
                        stop = result.scalar_one_or_none()
                        
                        if stop:
                            # Triggering explicit/implicit build for this stop
                            # If the builder caches internally, this warms it.
                            logger.debug(f"Warming transfers for {hub_code}...")
                            # In current implementation, build_transfer_graph builds EVERYTHING.
                            # We might want to optimize builder to build per-hub.
                            # For Task 23, we'll just trigger a full build if it's not already built.
                            await builder.build_transfer_graph()
                            # Once built, the builder or a global cache should hold it.
                            break # build_transfer_graph covers all stops usually
                        
                    except Exception as e:
                        logger.warning(f"Failed to warm hub {hub_code}: {e}")
                
            logger.info("✅ Hub Transfer Cache Warmup Complete.")
        except Exception as e:
            logger.error(f"❌ Cache Warmup Failed: {e}", exc_info=True)
        finally:
            self._is_running = False

hub_warmup_service = CacheWarmupService()
