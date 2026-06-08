import heapq
import threading
from typing import Any, Tuple, Optional

class PriorityQueue:
    """
    A thread-safe priority queue implementation.
    Used by various backend services for request ordering and task prioritization.
    """
    
    def __init__(self):
        self._queue = []
        self._count = 0
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        
    def put(self, item: Any, priority: int = 0):
        """
        Put an item into the queue with a given priority.
        Lower priority numbers are retrieved first.
        """
        with self._condition:
            # We add self._count to handle items with same priority (FIFO)
            entry = (priority, self._count, item)
            heapq.heappush(self._queue, entry)
            self._count += 1
            self._condition.notify()
            
    def get(self, block: bool = True, timeout: Optional[float] = None) -> Any:
        """
        Get the highest priority item from the queue.
        """
        with self._condition:
            if block:
                if not self._queue:
                    if not self._condition.wait(timeout):
                        raise IndexError("get from empty queue (timeout)")
            
            if not self._queue:
                raise IndexError("get from empty queue")
                
            return heapq.heappop(self._queue)[2]
            
    def qsize(self) -> int:
        """Return the size of the queue."""
        with self._lock:
            return len(self._queue)
            
    def empty(self) -> bool:
        """Return True if the queue is empty."""
        with self._lock:
            return not self._queue
            
    def clear(self):
        """Clear all items from the queue."""
        with self._lock:
            self._queue.clear()
            self._count = 0
