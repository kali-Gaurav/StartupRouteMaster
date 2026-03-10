import asyncio
import logging
from typing import Dict, Any, Set

logger = logging.getLogger(__name__)

class BookingWorkerPool:
    """
    Refactored for Phase 1 (Ethical RouteMaster).
    The pool now manages background agent notifications and escrow timeouts
    instead of running headless scraping browsers.
    """
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self.queue = asyncio.PriorityQueue()
        self.active_ids: Set[str] = set()
        self.worker_tasks = []
        self._producer_task = None

    async def start_manager(self):
        """Starts the background worker consumers."""
        # Start consumers
        for i in range(self.max_concurrent):
            task = asyncio.create_task(self._worker_loop(i))
            self.worker_tasks.append(task)
            
        # Start producer (DB polling)
        self._producer_task = asyncio.create_task(self._producer_loop())
        
        logger.info(f"Worker Pool Manager started with {self.max_concurrent} slots.")

    async def submit_booking(self, booking_id: str, priority: int = 10):
        """
        Submit a booking task to the background queue.
        """
        if booking_id in self.active_ids:
            return # Already being processed or in queue
            
        self.active_ids.add(booking_id)
        await self.queue.put((priority, booking_id))
        logger.info(f"Booking {booking_id} queued with priority {priority}.")

    async def _producer_loop(self):
        """Background loop to poll database for pending bookings."""
        from database.session import SessionLocal
        from database.models import Booking, EscrowStatus
        
        while True:
            try:
                # Poll database for High Priority verified bookings
                db = SessionLocal()
                try:
                    # Find pending verified bookings not already in our set
                    pending_bookings = db.query(Booking).filter(
                        Booking.escrow_status == EscrowStatus.VERIFIED,
                        Booking.service_type == "AGENT_BOOKING"
                    ).order_by(Booking.priority.asc(), Booking.created_at.asc()).limit(self.max_concurrent * 2).all()
                    
                    for booking in pending_bookings:
                        if booking.id not in self.active_ids:
                            await self.submit_booking(booking.id, booking.priority)
                finally:
                    db.close()
                
                # Poll every 10 seconds (Task 46.4)
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Producer Error: {e}")
                await asyncio.sleep(10)

    async def _worker_loop(self, worker_id: int):
        while True:
            try:
                # Process from queue
                try:
                    priority, booking_id = await asyncio.wait_for(self.queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    continue

                logger.info(f"[Slot {worker_id}] Processing booking {booking_id} (Priority: {priority})")
                
                # Simulation of booking process (Agent notification/API call)
                await asyncio.sleep(2) # Simulate work
                
                self.active_ids.discard(booking_id)
                self.queue.task_done()
                logger.info(f"[Slot {worker_id}] Finished processing for {booking_id}.")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Slot {worker_id}] Error: {e}")
                # Don't discard booking_id here if we want to retry, 
                # but for now discard so it can be re-queued if needed.
                # In a real app, we'd have retry logic.
                await asyncio.sleep(2)

# Singleton instance
worker_pool = BookingWorkerPool(max_concurrent=5)
