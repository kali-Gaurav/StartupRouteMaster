import logging
from core.nexus.node import NexusNode
from .reconciler import rl_reconciler

logger = logging.getLogger("nexus.rl.node")

class RLPricingNode(NexusNode):
    """[Task 7.10] RL Optimization Node (Layer 4)."""
    
    def __init__(self, name: str = "rl_pricing", critical: bool = False, dependencies=None):
        super().__init__(name, critical=critical, dependencies=dependencies if dependencies else ["database", "cache"])
        
    async def on_start(self):
        """[Task 7.1, 7.10] Initialize RL Reconciler and Policy Engine."""
        logger.info("🧠 [NEXUS:RL] Activating Intelligent Pricing Core (Layer 4)...")
        await rl_reconciler.init()
        logger.info("✅ [NEXUS:RL] Online Learning Policy: ACTIVE.")
        
    async def on_stop(self):
        """Final policy flush if needed."""
        logger.info("🧠 [NEXUS:RL] Halting RL Engine.")
        # rl_reconciler could have its own shutdown if needed
        pass

rl_node = RLPricingNode()
