import asyncio
import logging
from typing import Dict, Any
from .irctc_worker import run_booking_worker

logger = logging.getLogger(__name__)

class BookingWorkerPool:
    """
    Task 26 & 38: Headless Browser Worker Pool with Priority.
    Uses PriorityQueue to handle Tatkal bookings first.
    """
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self.queue = asyncio.PriorityQueue()
        self.active_workers: Dict[str, asyncio.Task] = {}
        self.worker_tasks = []

    async def start_manager(self):
        """Starts the background worker consumers."""
        for i in range(self.max_concurrent):
            task = asyncio.create_task(self._worker_loop(i))
            self.worker_tasks.append(task)
        logger.info(f"Worker Pool Manager started with {self.max_concurrent} slots.")

    async def submit_booking(self, booking_id: str, priority: int = 10):
        """
        Task 38: Submit with priority.
        0-5 = Tatkal/High Priority, 10+ = Normal.
        """
        if booking_id in self.active_workers:
            logger.info(f"Booking {booking_id} already in pool.")
            return
            
        await self.queue.put((priority, booking_id))
        logger.info(f"Booking {booking_id} queued with priority {priority}.")

    async def _worker_loop(self, worker_id: int):
        while True:
            try:
                priority, booking_id = await self.queue.get()
                logger.info(f"[Slot {worker_id}] Processing booking {booking_id} (Priority: {priority})")
                
                # Execute the worker
                await run_booking_worker(booking_id)
                
                self.queue.task_done()
                logger.info(f"[Slot {worker_id}] Finished booking {booking_id}.")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Slot {worker_id}] Error: {e}")
                await asyncio.sleep(1)

# Singleton instance
worker_pool = BookingWorkerPool(max_concurrent=5)
# Note: In a real app, start_manager() should be called in the FastAPI lifespan.
