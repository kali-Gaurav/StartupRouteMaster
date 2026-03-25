import asyncio
import logging
from typing import Dict, List, Set, Optional
from core.nexus.node import NexusNode
from core.nexus.state import nexus_state_manager, NexusState

logger = logging.getLogger("nexus.boot")

class NexusBootstrapper:
    """[Task 1.3] Orchestrates the parallel, dependency-resolved startup of RouteMaster nodes."""
    
    def __init__(self):
        self._nodes: Dict[str, NexusNode] = {}
        self._boot_order: List[List[str]] = [] # Layers of nodes to boot in parallel
        self._halted = False
        self._boot_completed = False
        self._start_time = None
        
    def register(self, node: NexusNode):
        """Adds a service node to the bootstrapper."""
        self._nodes[node.name] = node
        logger.debug(f"ℹ️ Registered Nexus Node: {node.name}")
        
    def resolve_dependencies(self):
        """[Task 1.3] Sorts nodes into parallelizable layers based on their dependency graph (DAG)."""
        resolved: Set[str] = set()
        layers: List[List[str]] = []
        pending = set(self._nodes.keys())
        
        while pending:
            current_layer = []
            for node_name in list(pending):
                deps = set(self._nodes[node_name].dependencies)
                # If all dependencies are already resolved, add this node to the current layer
                if deps.issubset(resolved):
                    current_layer.append(node_name)
                    
            if not current_layer:
                cycle_nodes = ", ".join(pending)
                logger.error(f"🛑 [BOOT ERROR] Circular Dependency detected in Nexus Spine: {cycle_nodes}")
                raise RuntimeError(f"Circular Dependency detected: {cycle_nodes}")
                
            layers.append(current_layer)
            resolved.update(current_layer)
            pending.difference_update(current_layer)
            
        self._boot_order = layers
        logger.info(f"📊 [BOOT GRAPH] Resolved into {len(layers)} execution levels.")

    async def bootstrap(self, gate_halt: bool = True):
        """Main entry point to boot the entire system safely."""
        nexus_state_manager.set_state(NexusState.BOOTING)
        self.resolve_dependencies()
        
        try:
            for i, layer in enumerate(self._boot_order):
                logger.debug(f"🚀 Initializing Layer {i+1}/{len(self._boot_order)}: {', '.join(layer)}")
                # Start all nodes in the current layer in parallel
                tasks = [self._nodes[node_name].start() for node_name in layer]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Verify layer success
                for node_name, result in zip(layer, results):
                    if isinstance(result, Exception):
                        logger.error(f"🚨 [CRITICAL] Node {node_name} failed: {result}")
                        if gate_halt:
                            nexus_state_manager.set_state(NexusState.HALTED, reason=f"Critical Node Failure: {node_name}")
                            self._halted = True
                            return False
                            
            nexus_state_manager.set_state(NexusState.READY)
            self._boot_completed = True
            return True
            
        except Exception as e:
            nexus_state_manager.set_state(NexusState.HALTED, reason=str(e))
            logger.critical(f"🛑 [BOOT ABORTED] System failed to reach READY state: {e}")
            return False

    async def halt(self):
        """Safe shutdown protocol for all nodes in reverse order."""
        logger.warning("🔌 [HALT] Initiating System-Wide Graceful Shutdown...")
        
        # Stop everything in reverse of the dependency order
        for layer in reversed(self._boot_order):
            tasks = [self._nodes[node_name].stop() for node_name in layer]
            await asyncio.gather(*tasks, return_exceptions=True)
            
        nexus_state_manager.set_state(NexusState.OFFLINE)
        logger.info("🛑 [OFFLINE] System shutdown complete. Registry data flushed.")

# Global Access via Singleton
nexus_boot = NexusBootstrapper()
