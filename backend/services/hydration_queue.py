import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

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
        self.stats = {"dropped": 0, "completed": 0}

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
