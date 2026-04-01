import asyncio
import logging
import time
from typing import List, Dict, Optional, Set
from .state import SystemState
from .node import NexusNode, NodeStatus
from .recovery import AutoRecoverySentinel
from .telemetry import nexus_telemetry # Import NexusTelemetry

logger = logging.getLogger("nexus.bootstrapper")

class NexusBootstrapper:
    """[Task 1.3 & 1.4] High-Integrity Deterministic Bootstrapper for V3 Fiber."""
    
    def __init__(self):
        self.nodes: Dict[str, NexusNode] = {}
        self.state = SystemState.OFFLINE
        self.boot_order: List[str] = []
        self._lock = asyncio.Lock()
        
        # [Task 21] Resilience Sentinel
        self.recovery = AutoRecoverySentinel(self)
        
        # [Task 24] Memory Hygiene
        from .audit.mem_profiler import mem_profiler
        self.profiler = mem_profiler
        
        # [Improved Idea] Telemetry Component
        self.telemetry = nexus_telemetry
        
    def register(self, node: NexusNode):
        """Register a node in the dependency graph."""
        self.nodes[node.name] = node
        logger.info(f"[NEXUS] Registered: {node.name} (Deps: {node.dependencies})")

    async def bootstrap(self) -> bool:
        """[Task 1.4] Parallel-Aware Layered Boot using asyncio.TaskGroup."""
        async with self._lock:
            self.state = SystemState.BOOTING
            logger.info("[NEXUS] Initiating State-Graph Resolution (Task 1.4)...")
            
            # Topological Sort for Dependency Mapping [Task 1.3]
            try:
                layers = self._resolve_dependency_layers()
            except Exception as e:
                logger.critical(f"[NEXUS] Dependency Resolution Error: {e}")
                self.state = SystemState.SAFE_MODE
                return False

            # [Task 1.7] Pre-Boot Resource Snapshot
            from core.resource_monitor import resource_monitor
            stats = resource_monitor.get_stats()
            logger.info(f"[NEXUS:RESOURCES] Pre-Boot RAM: {stats['process_rss_mb']:.1f}MB | CPU: {stats['cpu_percent']}%")
            
            # 2. Sequential Layer-by-Layer Parallel Boot
            try:
                from utils.integrity import integrity_engine
                for idx, layer in enumerate(layers):
                    # Parallel init of nodes in the same layer
                    # [Gap 1] Boot Timeout Guard: 30s per layer
                    async with asyncio.timeout(30.0):
                         async with asyncio.TaskGroup() as tg:
                             for node_name in layer:
                                 node = self.nodes[node_name]
                                 tg.create_task(node.start())
                    
                    # [Task 1.7] Post-Layer Telemetry
                    st = resource_monitor.get_stats()
                    logger.info(f"[NEXUS:LAYER_{idx}] Boot-up Peak RAM: {st['process_rss_mb']:.1f}MB")
                    
                    # Verify Layer Health [Task 1.5]
                    for node_name in layer:
                        node = self.nodes.get(node_name)
                        if not node:
                             logger.error(f"[NEXUS] Critical Error: Node '{node_name}' evaporated during boot.")
                             continue
                             
                        if node.status == NodeStatus.FAILED:
                            if node.critical:
                                raise RuntimeError(f"Critical Node {node_name} failed boot.")
                            else:
                                self.state = SystemState.DEGRADED
                    
                    self.boot_order.extend(layer)
                
                if self.state != SystemState.DEGRADED:
                    self.state = SystemState.READY
                
                # [Task 21] Start Auto-Recovery Watchdog
                self.recovery.start()
                
                # [Task 24] Start Memory Profiler
                self.profiler.start()
                    
                logger.info(f"[NEXUS] Master Boot Sequence Complete. Ready State: {self.state}")
                return True

            except Exception as e:
                logger.critical(f"[NEXUS] Master Boot Failure: {e}")
                self.state = SystemState.SAFE_MODE
                return False

    def _resolve_dependency_layers(self) -> List[List[str]]:
        """[Task 1.3] Group nodes into parallel-ready layers."""
        visited: Set[str] = set()
        layers: List[List[str]] = []
        
        nodes_to_process = set(self.nodes.keys())
        
        while nodes_to_process:
            current_layer = []
            for name in list(nodes_to_process):
                node = self.nodes[name]
                # Filter dependencies that are NOT in the graph AT ALL
                # (Treating them as externally satisfied or disabled)
                active_deps = {d for d in node.dependencies if d in self.nodes}
                
                if active_deps.issubset(visited):
                    current_layer.append(name)
            
            if not current_layer:
                logger.error(f"[NEXUS] Remaining Nodes: {nodes_to_process} | Visited: {visited}")
                # Log why it's stuck:
                for n in nodes_to_process:
                     unvisited = [d for d in self.nodes[n].dependencies if d not in visited]
                     logger.error(f"  - Node '{n}' waiting for unvisited: {unvisited}")
                raise RuntimeError("Circular Dependency or Missing Node detected in Nexus Graph!")
                
            layers.append(current_layer)
            visited.update(current_layer)
            nodes_to_process.difference_update(current_layer)
            
        return layers

    async def halt(self) -> bool:
        """[Task 1.6] Graceful Stop Protocol (Reverse Order)."""
        async with self._lock:
            # [Task 21] Disable Sentinel first
            self.recovery.stop()
            
            # [Task 24] Disable Profiler
            self.profiler.stop()
            
            self.state = SystemState.HALTED
            logger.warning("[NEXUS] Initiating Reverse-Order Halt Sequence (Task 1.6)...")
            
            all_successful = True
            for node_name in reversed(self.boot_order):
                node = self.nodes[node_name]
                if not await node.stop():
                    all_successful = False
            
            self.boot_order = []
            return all_successful

# Global Singleton
nexus_boot = NexusBootstrapper()
