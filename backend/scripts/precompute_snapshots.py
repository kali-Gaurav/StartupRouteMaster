import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# Add backend to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.route_engine.engine import RailwayRouteEngine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("precompute_snapshots")

async def precompute():
    engine = RailwayRouteEngine()
    
    # Precompute for today and next 2 days
    today = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
    dates = [today + timedelta(days=i) for i in range(3)]
    
    logger.info(f"Starting precomputation for dates: {[d.date() for d in dates]}")
    
    for target_date in dates:
        logger.info(f"--- Precomputing for {target_date.date()} ---")
        try:
            # This triggers building the graph, saving the snapshot, and warming up hub tables
            graph = await engine._get_current_graph(target_date)
            logger.info(f"Successfully precomputed graph for {target_date.date()}")
            
            # Optional: Trigger hub precomputation for major pairs if needed
            # await engine.hub_manager.precompute_hub_connectivity(target_date, graph)
            
        except Exception as e:
            logger.error(f"Failed precomputation for {target_date.date()}: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(precompute())
