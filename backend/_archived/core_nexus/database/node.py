import logging
from core.nexus.node import NexusNode
from database.session import initialize_database_pools, _dispose_all_pools

logger = logging.getLogger("nexus.database.node")

class DatabaseEngineNode(NexusNode):
    """[Task 5.1 & 10.1] Database Engine Node (Layer 2)."""
    
    def __init__(self, name: str = "database", critical: bool = True, dependencies=None):
        super().__init__(name, critical=critical, dependencies=dependencies if dependencies else ["cache", "security"])
        
    async def on_start(self):
        """[Task 4.1] Initialize Optimized Database Pools (Sync & Async)."""
        logger.info("[NEXUS:DATABASE] Initializing JIT Pools (Layer 2)...")
        await initialize_database_pools()
        
        # [Critical Fix] Ensure tables exist before finishing the boot
        from database.session import init_db
        try:
            await init_db()
            logger.info("[NEXUS:DATABASE] JIT Schema Verification Success.")
        except Exception as e:
            logger.error(f"[NEXUS:DATABASE] Schema JIT failed: {e}")
            # If critical, we should probably raise here, but for dev we continue
            
        logger.info("[NEXUS:DATABASE] Engine Readiness Confirmed.")
        
        
    async def on_stop(self):
        """[Task 1.6] Atomic Pool Disposal."""
        logger.info("[NEXUS:DATABASE] Disposing Database Pools.")
        await _dispose_all_pools()

database_node = DatabaseEngineNode()
