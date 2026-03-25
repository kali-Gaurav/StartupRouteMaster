import asyncio
import logging
from enum import Enum
from typing import Dict, List, Any, Callable, Optional, Set

logger = logging.getLogger("jit-manager")

class JITState(Enum):
    PENDING = "pending"
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"

class JITNode:
    def __init__(self, name: str, dependencies: List[str] = None, loader: Callable = None):
        self.name = name
        self.dependencies = dependencies or []
        self.loader = loader
        self.state = JITState.PENDING
        self.error = None
        self._lock = asyncio.Lock()
        self._ready_event = asyncio.Event()

    async def load(self, manager: 'JitManager'):
        async with self._lock:
            if self.state == JITState.READY:
                return
            
            if self.state == JITState.LOADING:
                await self._ready_event.wait()
                return

            self.state = JITState.LOADING
            logger.info(f"🚀 JIT: Loading node [{self.name}]...")
            
            try:
                # Ensure all dependencies are ready
                for dep_name in self.dependencies:
                    await manager.ensure_ready(dep_name)
                
                # Run the actual loader
                if self.loader:
                    if asyncio.iscoroutinefunction(self.loader):
                        await self.loader()
                    else:
                        self.loader()
                
                self.state = JITState.READY
                self._ready_event.set()
                logger.info(f"✅ JIT: Node [{self.name}] is READY.")
            except Exception as e:
                self.state = JITState.ERROR
                self.error = str(e)
                self._ready_event.set() # Release waiters even on error
                logger.error(f"❌ JIT: Node [{self.name}] FAILED: {e}")
                raise e

class JitManager:
    """
    Elite High-Performance JIT Node Manager.
    Handles lazy-loading of system components with dependency management.
    """
    def __init__(self):
        self.nodes: Dict[str, JITNode] = {}

    def register_node(self, name_or_node: Any, dependencies: List[str] = None, loader: Callable = None):
        if isinstance(name_or_node, JITNode):
            self.nodes[name_or_node.name] = name_or_node
        else:
            self.nodes[str(name_or_node)] = JITNode(str(name_or_node), dependencies, loader)

    async def ensure_ready(self, name: str):
        if name not in self.nodes:
            raise ValueError(f"JIT: Node [{name}] not registered.")
        
        node = self.nodes[name]
        if node.state != JITState.READY:
            await node.load(self)

    def mark_ready(self, name: str):
        """Manually mark a node as ready (used in scripts/tests)."""
        if name in self.nodes:
            self.nodes[name].state = JITState.READY
            self.nodes[name]._ready_event.set()

    def get_status(self) -> Dict[str, str]:
        return {name: node.state.value for name, node in self.nodes.items()}

# Singleton Instance
jit_manager = JitManager()
