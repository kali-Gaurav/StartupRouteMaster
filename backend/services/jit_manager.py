import asyncio
import logging
import time
from enum import Enum
from typing import Dict, List, Set, Optional, Any, Callable, Awaitable
from datetime import datetime

logger = logging.getLogger("jit-manager")

class JITState(Enum):
    PENDING = "pending"
    LOADING = "loading"
    READY = "ready"
    FAILED = "failed"
    DEGRADED = "degraded"

class JITNode:
    def __init__(self, name: str, dependencies: List[str], loader: Callable[[], Awaitable[None]]):
        self.name = name
        self.dependencies = dependencies
        self.loader = loader
        self.state = JITState.PENDING
        self.error: Optional[str] = None
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.event = asyncio.Event()
        self.lock = asyncio.Lock()

class JITManager:
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(JITManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized: return
        self.nodes: Dict[str, JITNode] = {}
        self._initialized = True
        self.global_start_time = time.time()

    def register_node(self, name: str, dependencies: List[str], loader: Callable[[], Awaitable[None]]):
        """Register a new node in the JIT dependency graph."""
        self.nodes[name] = JITNode(name, dependencies, loader)
        logger.debug(f"JIT: Registered node '{name}' (depends on: {dependencies})")

    async def ensure_ready(self, node_name: str):
        """
        Main entry point for JIT triggering. 
        Guarantees that a node and all its dependencies are ready.
        Implements Thundering Herd protection via asyncio.Event.
        """
        if node_name not in self.nodes:
            raise ValueError(f"JIT: Node '{node_name}' not registered.")

        node = self.nodes[node_name]

        # 1. If already ready, return instantly
        if node.state == JITState.READY:
            return

        # 2. If already loading, wait for the event
        if node.state == JITState.LOADING:
            await node.event.wait()
            if node.state == JITState.FAILED:
                raise RuntimeError(f"JIT: Node '{node_name}' failed to load: {node.error}")
            return

        # 3. Double-check lock for atomic loading
        async with node.lock:
            # Re-check state inside lock
            if node.state == JITState.READY:
                return
            
            if node.state == JITState.LOADING:
                await node.event.wait()
                return

            # Start loading process
            node.state = JITState.LOADING
            node.event.clear()
            node.start_time = time.time()
            
            try:
                # Resolve dependencies first
                if node.dependencies:
                    logger.info(f"JIT: Node '{node_name}' waiting on dependencies: {node.dependencies}")
                    await asyncio.gather(*(self.ensure_ready(dep) for dep in node.dependencies))

                # Execute node loader
                logger.info(f"⚡ JIT: Executing loader for '{node_name}'...")
                await node.loader()
                
                node.state = JITState.READY
                node.end_time = time.time()
                logger.info(f"✅ JIT: Node '{node_name}' ready (Took {node.end_time - node.start_time:.2f}s)")
            except Exception as e:
                node.state = JITState.FAILED
                node.error = str(e)
                logger.error(f"❌ JIT: Node '{node_name}' failed: {e}")
                raise e
            finally:
                node.event.set()

    def get_status(self) -> Dict[str, Any]:
        """Return the current state of the entire DAG."""
        return {
            "uptime_seconds": time.time() - self.global_start_time,
            "nodes": {
                name: {
                    "state": node.state.value,
                    "error": node.error,
                    "duration": (node.end_time - node.start_time) if node.end_time else None
                } for name, node in self.nodes.items()
            }
        }

# Global Instance
jit_manager = JITManager()
