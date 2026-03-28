import logging
import asyncio
from typing import Optional
from core.nexus.node import NexusNode
from core.route_engine.graph import TimeDependentGraph
from core.route_engine.raptor import OptimizedRAPTOR
from services.multi_layer_cache import multi_layer_cache

logger = logging.getLogger("nexus.search.node")

class NexusSearchNode(NexusNode):
    """[Task 8.10] Search Engine V3 Lifecycle Orchestrator.
    Manages RAPTOR and Graph-Propagated Search components.
    """
    
    def __init__(self, name: str = "search", critical: bool = True, dependencies=None):
        super().__init__(name, critical=critical, dependencies=dependencies if dependencies else ["database", "cache", "scraper", "financial"])
        self.graph: Optional[TimeDependentGraph] = None
        self.engine: Optional[OptimizedRAPTOR] = None

    async def on_start(self):
        """[Task 8.2 & 8.3] Initialize Graph with mmap and Cache Latch.
        [Task 122] Pre-warm the graph for the current day to ensure instant first-request performance.
        """
        logger.info("[NEXUS:SEARCH] Building Time-Dependent Graph (mmap-aware)...")
        
        # 1. Verify Cache Health [Task 8.3]
        from services.multi_layer_cache import multi_layer_cache
        if not multi_layer_cache.health_latch:
             logger.warning("[NEXUS:SEARCH] Cache Latch is DOWN. Search will operate in Direct-to-DB mode (Slow).")
        
        # 2. Pre-warm the main route engine
        try:
            from core.route_engine.engine import route_engine
            # This call will build/load the graph for the current day and initialize all engines.
            await route_engine.init()
            
            # Keep a reference to the graph for health checks if needed
            self.graph = route_engine.graph
            logger.info("[NEXUS:SEARCH] Route Engine V3 Established and Graph is HOT.")
        except Exception as e:
            logger.error(f"[NEXUS:SEARCH] Graph Initialization Failed: {e}", exc_info=True)
            raise e

    async def on_stop(self):
        """Clean up graph memory and engine resources."""
        logger.info("[NEXUS:SEARCH] Search Node Shutdown initiated.")
        try:
            from core.route_engine.engine import route_engine
            await route_engine.shutdown()
        except Exception as e:
            logger.error(f"[NEXUS:SEARCH] Error during engine shutdown: {e}")
        self.graph = None
        self.engine = None
        logger.info("[NEXUS:SEARCH] Search Node Shutdown complete.")

search_node = NexusSearchNode()
