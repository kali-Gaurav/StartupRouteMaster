"""
Inventory Service - Phase 5 Seat Locking
Handles atomic reservation and release of train seat inventory.
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from database.models import SeatInventory, AuditLog
from typing import Optional

logger = logging.getLogger(__name__)

class InventoryService:
    @staticmethod
    def reserve_seat_temporary(
        db: Session, 
        trip_id: int, 
        travel_date: datetime.date, 
        coach_type: str,
        booking_id: str,
        lock_minutes: int = 15
    ) -> bool:
        """
        Subtask 45.2: Atomically decrement available seats and set a lock.
        Uses optimistic concurrency or SELECT FOR UPDATE if needed.
        """
        try:
            # 1. Find the inventory record
            inventory = db.query(SeatInventory).filter(
                SeatInventory.trip_id == trip_id,
                SeatInventory.travel_date == travel_date,
                SeatInventory.coach_type == coach_type
            ).with_for_update().first() # [45.6] Atomic lock
            
            if not inventory:
                logger.warning(f"No inventory record found for Trip {trip_id} on {travel_date}")
                return False
                
            # 2. Check availability (Including existing temporary locks)
            # For simplicity, we assume available_seats is the net amount
            if inventory.available_seats <= 0:
                return False
                
            # 3. Reserve
            inventory.available_seats -= 1
            inventory.locked_until = datetime.utcnow() + timedelta(minutes=lock_minutes)
            inventory.locked_by_booking_id = booking_id
            inventory.last_updated = datetime.utcnow()
            
            # 4. Audit
            audit = AuditLog(
                entity_type="Inventory",
                entity_id=inventory.id,
                action="SEAT_LOCKED_TEMPORARY",
                old_value=str(inventory.available_seats + 1),
                new_value=str(inventory.available_seats),
                performed_by="SYSTEM_INVENTORY",
                reason=f"Booking {booking_id} locked 1 seat."
            )
            db.add(audit)
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error reserving seat: {e}")
            db.rollback()
            return False

    @staticmethod
    def release_expired_locks(db: Session) -> int:
        """
        Subtask 45.3: Restore seats for expired locks.
        """
        now = datetime.utcnow()
        expired = db.query(SeatInventory).filter(
            SeatInventory.locked_until != None,
            SeatInventory.locked_until < now
        ).all()
        
        count = 0
        for inv in expired:
            inv.available_seats += 1
            inv.locked_until = None
            inv.locked_by_booking_id = None
            count += 1
            
        if count > 0:
            db.commit()
            logger.info(f"Released {count} expired seat locks.")
        return count
