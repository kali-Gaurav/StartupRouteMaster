import logging
from core.nexus.node import NexusNode
from services.scraper_sentinel import scraper_sentinel

logger = logging.getLogger("nexus.scraper.node")

class ScraperOrchestratorNode(NexusNode):
    """[Task 6.1 & 6.10] Scraper Orchestrator Node (Layer 3)."""
    
    def __init__(self, name: str = "scraper", critical: bool = False, dependencies=None):
        super().__init__(name, critical=critical, dependencies=dependencies if dependencies else ["cache"])
        
    async def on_start(self):
        """[Task 48.1] Initialize Scraper Sentinel Pool and Live Ingestion."""
        logger.info("[NEXUS:SCRAPER] Activating Scraper Sentinel (Layer 3)...")
        await scraper_sentinel.start()
        
        # [Task 48.9] Start Live Ingestion Worker (Real-time Pipeline)
        from services.realtime_ingestion.ingestion_worker import start_ingestion_service
        logger.info("[NEXUS:SCRAPER] Starting Live Data Ingestion Worker...")
        start_ingestion_service(interval_minutes=15) # Optimized for VPS
        
        logger.info("[NEXUS:SCRAPER] Browser Context Pool: WARM | Ingestion: ACTIVE.")
        
    async def on_stop(self):
        """[Task 1.6] Total shutdown of browser instances and workers."""
        logger.info("[NEXUS:SCRAPER] Halting Scraper Sentinel and Ingestion.")
        from services.realtime_ingestion.ingestion_worker import stop_ingestion_service
        stop_ingestion_service()
        await scraper_sentinel.stop()

scraper_node = ScraperOrchestratorNode()
