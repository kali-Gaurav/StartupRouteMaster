import logging
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from database.session import SessionLocal
from database.models import SeatInventory

logger = logging.getLogger("agent.inventory_gc")

from services.agents.base_agent import BaseAgent, AgentPriority

logger = logging.getLogger("agent.inventory_gc")

class InventoryGCAgent(BaseAgent):
    """
    [G1.1.4] Autonomous Reaper Agent.
    Periodically releases 'Zombie Locks' in SeatInventory that were never finalized into bookings.
    Ensures zero-leak inventory management.
    """
    name = "InventoryGCAgent"
    description = "Reclaims expired seat locks from SeatInventory"
    category = "operations"
    priority = AgentPriority.NORMAL
    auto_schedule_interval = 60.0  # Run every minute

    async def execute(self, context: dict = None) -> dict:
        """Main execution logic for the reaper."""
        count = await self.reclaim_expired_locks()
        return {
            "status": "success",
            "summary": f"Reclaimed {count} zombie seats from expired locks."
        }

    async def reclaim_expired_locks(self) -> int:
        """
        Finds and releases SeatInventory locks that have exceeded their TTL.
        """
        db: Session = SessionLocal()
        count = 0
        try:
            now = datetime.utcnow()
            # 1. Find expired locks that aren't tied to a successful final state
            expired_rows = db.query(SeatInventory).filter(
                SeatInventory.locked_until < now
            ).with_for_update(skip_locked=True).all()

            if not expired_rows:
                return 0

            for row in expired_rows:
                # [Atomic Recovery] Increment seats back
                row.available_seats += 1
                row.locked_until = None
                row.locked_by_booking_id = None
                row.last_updated = now
                count += 1

            db.commit()
            if count > 0:
                self._log_event("reclaim", "success", f"Reclaimed {count} zombie seats.")
            return count
        
        except Exception as e:
            logger.error(f"🚨 [INVENTORY_GC] Reclamation Error: {e}")
            db.rollback()
            raise e
        finally:
            db.close()

inventory_gc_agent = InventoryGCAgent()
