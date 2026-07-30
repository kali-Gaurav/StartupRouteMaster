import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Tuple
from core.sovereign.network_pressure import network_pressure
from services.search.service import SearchService as search_service
from core.data_utils.structures import Persona

logger = logging.getLogger("sovereign.cache_warmer")

class SovereignCacheWarmer:
    """
    [SOVEREIGN] Proactive Cache Hydration Service.
    Monitors Network Pressure and pre-warms Redis for high-demand corridors.
    Ensures <200ms TTFB for millions of users by staying ahead of the demand curve.
    """
    def __init__(self):
        self._active = False
        self._warm_interval = 600  # 10 minutes
        self._pressure_threshold = 0.75  # Warm if pressure is above this
        self._max_warms_per_cycle = 20

    async def start(self):
        """Start the proactive warming loop."""
        if self._active:
            return
        self._active = True
        logger.info("🔥 [SOVEREIGN:WARMER] Proactive Cache Hydration Service online.")
        asyncio.create_task(self._warming_loop())

    async def stop(self):
        """Stop the warming loop."""
        self._active = False
        logger.info("🛑 [SOVEREIGN:WARMER] Proactive Cache Hydration Service shutting down.")

    async def _warming_loop(self):
        while self._active:
            try:
                # 1. Get all nodes under pressure
                snapshot = network_pressure.get_current_snapshot()
                if not snapshot:
                    await asyncio.sleep(60)
                    continue

                hot_corridors = [
                    (node_id, node) for node_id, node in snapshot.nodes.items()
                    if node.pressure_score >= self._pressure_threshold
                    and "->" in node_id
                ]

                # Sort by highest pressure
                hot_corridors.sort(key=lambda x: x[1].pressure_score, reverse=True)
                
                logger.info(f"🔎 [SOVEREIGN:WARMER] Identified {len(hot_corridors)} high-pressure corridors for hydration.")

                # 2. Warm the top X corridors
                count = 0
                for corridor_id, node in hot_corridors[:self._max_warms_per_cycle]:
                    src, dst = corridor_id.split("->")
                    await self._warm_corridor(src, dst)
                    count += 1
                    await asyncio.sleep(2)  # Throttled warming

                logger.info(f"✅ [SOVEREIGN:WARMER] Hydration cycle complete. {count} corridors pre-warmed.")

            except Exception as e:
                logger.error(f"❌ [SOVEREIGN:WARMER] Warming cycle failed: {e}")
            
            await asyncio.sleep(self._warm_interval)

    async def _warm_corridor(self, source: str, destination: str):
        """Trigger a background search to hydrate the cache."""
        try:
            # We warm for the next 3 days
            today = datetime.now()
            for i in range(3):
                travel_date = (today + timedelta(days=i)).strftime("%Y-%m-%d")
                
                # Perform an internal search (discovery_only=True to be fast but fill cache)
                # We use a special 'SYSTEM' quota to bypass rate limits
                await search_service.search_routes(
                    source=source,
                    destination=destination,
                    travel_date=travel_date,
                    budget_category="COMFORT",
                    quota="SYSTEM",
                    discovery_only=True 
                )
                
            logger.debug(f"🌊 [SOVEREIGN:WARMER] Hydrated {source}->{destination} for next 3 days.")
        except Exception as e:
            logger.warning(f"⚠️ [SOVEREIGN:WARMER] Failed to warm {source}->{destination}: {e}")

# Singleton
sovereign_cache_warmer = SovereignCacheWarmer()
