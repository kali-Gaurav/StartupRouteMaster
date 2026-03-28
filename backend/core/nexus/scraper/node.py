import logging
from core.nexus.node import NexusNode
from services.scraper_sentinel import scraper_sentinel

logger = logging.getLogger("nexus.scraper.node")

class ScraperOrchestratorNode(NexusNode):
    """[Task 6.1 & 6.10] Scraper Orchestrator Node (Layer 3)."""
    
    def __init__(self, name: str = "scraper", critical: bool = False, dependencies=None):
        super().__init__(name, critical=critical, dependencies=dependencies if dependencies else ["cache"])
        
    async def on_start(self):
        """[Task 48.1] Initialize Scraper Sentinel Pool."""
        logger.info("[NEXUS:SCRAPER] Activating Scraper Sentinel (Layer 3)...")
        await scraper_sentinel.start()
        logger.info("[NEXUS:SCRAPER] Browser Context Pool: WARM.")
        
    async def on_stop(self):
        """[Task 1.6] Total shutdown of browser instances."""
        logger.info("[NEXUS:SCRAPER] Halting Scraper Sentinel.")
        await scraper_sentinel.stop()

scraper_node = ScraperOrchestratorNode()
