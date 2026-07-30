import asyncio
import logging
from datetime import datetime
from database.infrastructure.session import SessionLocal
from core.infrastructure.redis_manager import async_redis_client as redis_client
from database.models import DemandTrainingData

logger = logging.getLogger("routemaster.demand_exporter")

class DemandExporterWorker:
    """
    [Neural Brain] The Exporter.
    Periodically snapshots Redis Heatmap into the SQL training table.
    """
    async def start(self):
        logger.info("Demand Exporter worker started...")
        while True:
            try:
                # 1. Snapshot the heatmap
                heatmap = await redis_client.hgetall("global_demand_heatmap")
                
                if not heatmap:
                    logger.info("Heatmap empty, skipping snapshot.")
                else:
                    db = SessionLocal()
                    try:
                        for key, score in heatmap.items():
                            key_str = key.decode()
                            demand_score = float(score.decode())
                            
                            # Parse demand:{origin}:{dest}:{hour}
                            parts = key_str.split(":")
                            if len(parts) == 4:
                                origin, dest, hour = parts[1], parts[2], parts[3]
                                
                                # Log to SQL Training Table
                                data = DemandTrainingData(
                                    origin=origin,
                                    destination=dest,
                                    hour=int(hour),
                                    day_of_week=datetime.utcnow().weekday(),
                                    demand_score=demand_score,
                                    created_at=datetime.utcnow()
                                )
                                db.add(data)
                        
                        db.commit()
                        logger.info(f"💾 Snapshot {len(heatmap)} demand points to SQL training set.")
                    finally:
                        db.close()
                
                # Snapshot Frequency
                await asyncio.sleep(3600) # Run every hour
            except Exception as e:
                logger.error(f"Demand Exporter Error: {e}", exc_info=True)
                await asyncio.sleep(60)

if __name__ == "__main__":
    exporter = DemandExporterWorker()
    asyncio.run(exporter.start())
