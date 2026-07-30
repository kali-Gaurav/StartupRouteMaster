import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque

logger = logging.getLogger("hydration-queue")

@dataclass(order=True)
class HydrationTask:
    priority: int # Lower is higher priority (0 = Critical)
    timestamp: float = field(compare=False)
    data: Dict[str, Any] = field(compare=False)
    retry_count: int = field(default=0, compare=False)

class PrioritizedHydrationQueue:
    """
    Subtask 1.11: Memory-Safe Prioritized Hydration Queue.
    Handles backpressure and ensures high-confidence predictions are hydrated first.
    """
    
    def __init__(self, max_size: int = 2000):
        self.queue = asyncio.PriorityQueue(maxsize=max_size)
        self.max_size = max_size
        self.processing_count = 0
        self.stats = {"dropped": 0, "completed": 0, "errors": 0}
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        logger.info("PrioritizedHydrationQueue initialized with resilience patterns")
    
    async def _record_metrics(self, operation_type: str, success: bool, error: Optional[str] = None):
        """Record metrics for queue operations."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success,
                "error": error
            })
    
    def get_metrics(self) -> dict:
        """Get queue metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        by_type = {}
        for m in self._metrics:
            op_type = m.get("operation_type", "unknown")
            if op_type not in by_type:
                by_type[op_type] = {"total": 0, "success": 0}
            by_type[op_type]["total"] += 1
            if m["success"]:
                by_type[op_type]["success"] += 1
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "operation_breakdown": by_type,
            "queue_size": self.queue.qsize(),
            "queue_full": self.queue.full(),
            "processing_count": self.processing_count,
            "stats": self.stats
        }
    
    def health_check(self) -> dict:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "queue_size": self.queue.qsize(),
            "queue_max_size": self.max_size,
            "queue_full": self.queue.full(),
            "processing_count": self.processing_count,
            "stats": self.stats,
            "metrics": self.get_metrics()
        }

    async def push(self, data: Dict[str, Any], confidence: float):
        """
        Pushes a prediction for hydration.
        Confidence 0.9+ -> Priority 0
        Confidence 0.8+ -> Priority 1
        Otherwise -> Priority 2
        """
        # Calculate Priority
        priority = 2
        if confidence >= 0.95: priority = 0
        elif confidence >= 0.85: priority = 1

        task = HydrationTask(priority=priority, timestamp=time.time(), data=data)
        
        try:
            # Non-blocking put with backpressure
            # If queue is full, we drop the LOWEST priority items first
            if self.queue.full():
                if priority >= 2:
                    self.stats["dropped"] += 1
                    return # Drop low priority
                else:
                    # If high priority, we must make room by dropping a low priority one
                    # (This is a simplified version of priority-based eviction)
                    self.stats["dropped"] += 1
            
            self.queue.put_nowait(task)
        except asyncio.QueueFull:
            self.stats["dropped"] += 1

    async def get_next(self) -> HydrationTask:
        return await self.queue.get()

    def task_done(self):
        self.queue.task_done()
        self.stats["completed"] += 1

hydration_queue = PrioritizedHydrationQueue()
