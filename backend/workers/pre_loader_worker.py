import asyncio
import logging
import json
from datetime import datetime, timedelta
from database.redis_client import redis_client
from services.search_service import SearchService
from database.session import SessionTransit

logger = logging.getLogger("routemaster.pre_loader")

class PreLoaderWorker:
    """
    [Neural Brain] The Pre-Loader.
    Consumes the Demand Heatmap and proactively hydrates caches for high-demand routes.
    """
    def __init__(self):
        self.threshold = 5 # Minimum demand to trigger pre-load

    async def start(self):
        logger.info("Pre-Loader worker started...")
        while True:
            try:
                # Fetch demand heatmap
                heatmap = await redis_client.hgetall("global_demand_heatmap")
                
                for key, count in heatmap.items():
                    key_str = key.decode()
                    demand_count = int(count.decode())
                    
                    if demand_count >= self.threshold:
                        # Parse key: demand:{origin}:{dest}:{hour}
                        parts = key_str.split(":")
                        if len(parts) == 4:
                            origin, dest = parts[1], parts[2]
                            await self.hydrate_route(origin, dest)
                            # Reset or decay the demand after pre-loading to avoid loop
                            await redis_client.hset("global_demand_heatmap", key, 0)
                
                await asyncio.sleep(60) # Run every minute
            except Exception as e:
                logger.error(f"Pre-Loader Error: {e}")
                await asyncio.sleep(10)

    async def hydrate_route(self, origin: str, dest: str):
        logger.info(f"⚡ Hydrating cache for corridor: {origin} -> {dest}")
        db = SessionTransit()
        try:
            search_service = SearchService(db)
            await search_service.search_routes(
                source=origin,
                destination=dest,
                travel_date=(datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d"),
                limit=10
            )
        except Exception as e:
            logger.error(f"Failed to hydrate {origin}->{dest}: {e}")
        finally:
            db.close()

pre_loader = PreLoaderWorker()

if __name__ == "__main__":
    asyncio.run(pre_loader.start())
