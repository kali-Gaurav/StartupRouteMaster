"""
JIT Manager - High-Performance Just-In-Time Node Manager
=========================================================

Handles lazy-loading of system components with dependency management:
- Async dependency resolution
- State management (PENDING, LOADING, READY, ERROR)
- Automatic retry on failures

With resilience patterns: circuit breaker, retry, metrics tracking, and comprehensive error handling.

Author: RouteMaster Intelligence System
Date: 2026-02-17
"""

import asyncio
import logging
from enum import Enum
from typing import Dict, List, Any, Callable, Optional, Set
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime

from core.resilience import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.retry import RetryPolicy

logger = logging.getLogger("jit-manager")


class JITState(Enum):
    """JIT node states."""
    PENDING = "pending"
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"


@dataclass
class JITNode:
    """JIT node with dependencies and loader."""
    def __init__(
        self,
        name: str,
        dependencies: Optional[List[str]] = None,
        loader: Optional[Callable] = None,
        max_retries: int = 3
    ):
        self.name = name
        self.dependencies = dependencies or []
        self.loader = loader
        self.max_retries = max_retries
        self.state = JITState.PENDING
        self.error = None
        self.retry_count = 0
        self._lock = asyncio.Lock()
        self._ready_event = asyncio.Event()

    def can_retry(self) -> bool:
        """Check if node can be retried."""
        return self.retry_count < self.max_retries

    async def load(self, manager: 'JitManager'):
        """
        Load the node with dependency resolution.
        
        Args:
            manager: JIT manager instance
        """
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
                self.retry_count = 0
                self._ready_event.set()
                logger.info(f"✅ JIT: Node [{self.name}] is READY.")
                
            except Exception as e:
                self.state = JITState.ERROR
                self.error = str(e)
                self.retry_count += 1
                self._ready_event.set()  # Release waiters even on error
                logger.error(f"❌ JIT: Node [{self.name}] FAILED (attempt {self.retry_count}): {e}")
                raise e

    def reset(self):
        """Reset node to initial state."""
        self.state = JITState.PENDING
        self.error = None
        self.retry_count = 0
        self._ready_event = asyncio.Event()


@dataclass
class LoadMetrics:
    """JIT load operation metrics."""
    node_name: str
    duration_ms: float
    success: bool
    retry_count: int
    timestamp: datetime


class JitManager:
    """
    Elite High-Performance JIT Node Manager.
    Handles lazy-loading of system components with dependency management.
    
    With resilience patterns: circuit breaker, retry, metrics tracking, and health checks.
    """
    
    def __init__(self):
        """Initialize JIT manager with resilience patterns."""
        self.nodes: Dict[str, JITNode] = {}
        
        # Circuit breaker for node loading
        self._load_breaker = circuit_breaker_manager.get_or_create(
            "jit_manager_load",
            CircuitConfig(
                failure_threshold=10,
                timeout_seconds=60.0,
                success_threshold=5
            )
        )
        
        # Retry policy for node loading
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=5.0,
            conditions=[
                lambda e: isinstance(e, (ConnectionError, TimeoutError)),
                lambda e: "timeout" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        # Load history
        self._load_history: deque = deque(maxlen=100)
        self._history_lock = asyncio.Lock()
        
        # Dependency graph for cycle detection
        self._dependency_graph: Dict[str, Set[str]] = {}
        
        logger.info("JitManager initialized with resilience patterns")

    def register_node(
        self,
        name_or_node: Any,
        dependencies: Optional[List[str]] = None,
        loader: Optional[Callable[..., Any]] = None,
        max_retries: int = 3
    ) -> JITNode:
        """
        Register a JIT node.
        
        Args:
            name_or_node: Node name or JITNode instance
            dependencies: List of dependency names
            loader: Loader function
            max_retries: Maximum retry attempts
            
        Returns:
            Registered JITNode
        """
        if isinstance(name_or_node, JITNode):
            node = name_or_node
            self.nodes[node.name] = node
        else:
            node = JITNode(
                str(name_or_node),
                dependencies,
                loader,
                max_retries
            )
            self.nodes[str(name_or_node)] = node
        
        # Update dependency graph
        self._dependency_graph[node.name] = set(node.dependencies)
        
        logger.info(f"📝 Registered JIT node: {node.name} (deps: {node.dependencies})")
        return node

    def unregister_node(self, name: str) -> bool:
        """
        Unregister a JIT node.
        
        Args:
            name: Node name
            
        Returns:
            True if unregistered, False if not found
        """
        if name in self.nodes:
            del self.nodes[name]
            self._dependency_graph.pop(name, None)
            logger.info(f"🗑️ Unregistered JIT node: {name}")
            return True
        return False

    def _detect_cycle(self, node_name: str, visited: Set[str], recursion_stack: Set[str]) -> bool:
        """
        Detect cycles in dependency graph using DFS.
        
        Args:
            node_name: Current node
            visited: Set of visited nodes
            recursion_stack: Set of nodes in current recursion
            
        Returns:
            True if cycle detected
        """
        visited.add(node_name)
        recursion_stack.add(node_name)
        
        for dep in self._dependency_graph.get(node_name, set()):
            if dep not in visited:
                if self._detect_cycle(dep, visited, recursion_stack):
                    return True
            elif dep in recursion_stack:
                return True
        
        recursion_stack.remove(node_name)
        return False

    def validate_dependencies(self) -> Dict[str, Any]:
        """
        Validate all node dependencies.
        
        Returns:
            Dict with validation results
        """
        issues = []
        
        for node_name in self.nodes:
            # Check for missing dependencies
            for dep in self._dependency_graph.get(node_name, set()):
                if dep not in self.nodes:
                    issues.append({
                        "type": "missing_dependency",
                        "node": node_name,
                        "dependency": dep
                    })
            
            # Check for cycles
            if self._detect_cycle(node_name, set(), set()):
                issues.append({
                    "type": "circular_dependency",
                    "node": node_name
                })
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "total_nodes": len(self.nodes)
        }

    async def ensure_ready(self, name: str) -> bool:
        """
        Ensure a node is ready, loading if necessary.
        
        Args:
            name: Node name
            
        Returns:
            True if ready, False if failed
        """
        if name not in self.nodes:
            raise ValueError(f"JIT: Node [{name}] not registered.")
        
        node = self.nodes[name]
        
        if node.state == JITState.READY:
            return True
        
        if node.state == JITState.ERROR and not node.can_retry():
            logger.warning(f"⚠️ JIT: Node [{name}] has exhausted retries")
            return False
        
        start_time = datetime.utcnow()
        
        try:
            await node.load(self)
            
            # Record success metrics
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            await self._record_metrics(name, duration_ms, True, node.retry_count)
            
            return True
            
        except Exception as e:
            # Record failure metrics
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            await self._record_metrics(name, duration_ms, False, node.retry_count)
            
            logger.error(f"❌ JIT: Failed to load node [{name}]: {e}")
            return False

    async def ensure_all_ready(self, names: Optional[List[str]] = None) -> Dict[str, bool]:
        """
        Ensure multiple nodes are ready.
        
        Args:
            names: List of node names (all if None)
            
        Returns:
            Dict mapping node name to success status
        """
        target_nodes = names or list(self.nodes.keys())
        results = {}
        
        for name in target_nodes:
            results[name] = await self.ensure_ready(name)
        
        return results

    def mark_ready(self, name: str):
        """
        Manually mark a node as ready (used in scripts/tests).
        
        Args:
            name: Node name
        """
        if name in self.nodes:
            self.nodes[name].state = JITState.READY
            self.nodes[name]._ready_event.set()
            logger.info(f"✅ JIT: Node [{name}] marked ready manually")

    def mark_all_ready(self):
        """Mark all nodes as ready (for testing)."""
        for node in self.nodes.values():
            node.state = JITState.READY
            node._ready_event.set()
        logger.info("✅ All JIT nodes marked ready")

    def reset_node(self, name: str):
        """Reset a node to initial state."""
        if name in self.nodes:
            self.nodes[name].reset()
            logger.info(f"🔄 JIT: Node [{name}] reset")

    def reset_all(self):
        """Reset all nodes to initial state."""
        for node in self.nodes.values():
            node.reset()
        logger.info("🔄 All JIT nodes reset")

    def get_status(self) -> Dict[str, str]:
        """Get status of all nodes."""
        return {name: node.state.value for name, node in self.nodes.items()}

    def get_ready_nodes(self) -> List[str]:
        """Get list of ready nodes."""
        return [name for name, node in self.nodes.items() if node.state == JITState.READY]

    def get_pending_nodes(self) -> List[str]:
        """Get list of pending nodes."""
        return [name for name, node in self.nodes.items() if node.state != JITState.READY]

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    async def _record_metrics(
        self,
        node_name: str,
        duration_ms: float,
        success: bool,
        retry_count: int
    ):
        """Record load metrics."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "node_name": node_name,
                "duration_ms": duration_ms,
                "success": success,
                "retry_count": retry_count
            })
        
        async with self._history_lock:
            self._load_history.append({
                "node_name": node_name,
                "duration_ms": duration_ms,
                "success": success,
                "retry_count": retry_count,
                "timestamp": datetime.utcnow().isoformat()
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_loads": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        durations = [m["duration_ms"] for m in self._metrics]
        
        # Count by node
        by_node = {}
        for m in self._metrics:
            node = m["node_name"]
            by_node[node] = by_node.get(node, {"total": 0, "success": 0})
            by_node[node]["total"] += 1
            if m["success"]:
                by_node[node]["success"] += 1
        
        return {
            "total_loads": total,
            "successful_loads": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "by_node": by_node,
            "total_nodes": len(self.nodes),
            "ready_nodes": len(self.get_ready_nodes()),
            "circuit_breaker_state": self._load_breaker.get_state().value
        }

    def health_check(self) -> dict:
        """Check service health."""
        validation = self.validate_dependencies()
        
        return {
            "status": "healthy",
            "nodes_registered": len(self.nodes),
            "nodes_ready": len(self.get_ready_nodes()),
            "nodes_pending": len(self.get_pending_nodes()),
            "dependency_validation": validation,
            "circuit_breaker": {
                "state": self._load_breaker.get_state().value,
                "failure_count": self._load_breaker.failure_count,
                "success_count": self._load_breaker.success_count
            },
            "metrics": self.get_metrics()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._load_breaker.reset()
        logger.info("Circuit breaker reset for JIT manager")

    def get_load_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent load history."""
        return list(self._load_history)[-limit:]


# Singleton Instance
jit_manager = JitManager()
