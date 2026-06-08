"""
Inventory Service - Seat allocation and availability management.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from database.models import SeatInventory, Booking

logger = logging.getLogger("inventory_service")


@dataclass
class SeatAllocation:
    """Result of seat allocation."""
    status: str  # "allocated", "waitlist", "failed"
    seat_ids: List[str]
    price: float
    waitlist_position: Optional[int] = None
    error: Optional[str] = None


class InventoryService:
    """Seat inventory management service."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_availability(
        self,
        train_number: str,
        from_station: str,
        to_station: str,
        travel_date: str,
        class_type: str = "SL"
    ) -> Dict[str, Any]:
        """
        Get seat availability for a route.
        
        Returns availability status and count for each class.
        """
        try:
            result = await self.db.execute(
                select(SeatInventory).where(
                    and_(
                        SeatInventory.train_number == train_number,
                        SeatInventory.from_station_code == from_station,
                        SeatInventory.to_station_code == to_station,
                        SeatInventory.journey_date == travel_date,
                        SeatInventory.class_type == class_type
                    )
                )
            )
            result = result.scalar_one_or_none()
            
            if result:
                return {
                    "available": result.available_seats,
                    "waitlist": result.waitlist_count,
                    "status": self._get_status_text(result.available_seats),
                    "class_type": class_type
                }
            
            return {
                "available": 0,
                "waitlist": 0,
                "status": "UNKNOWN",
                "class_type": class_type
            }
            
        except Exception as e:
            logger.error(f"Error getting availability: {e}")
            return {"error": str(e)}
    
    async def allocate_seats(
        self,
        train_number: str,
        from_station: str,
        to_station: str,
        travel_date: str,
        class_type: str,
        num_seats: int,
        berth_preferences: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Allocate seats for booking.
        
        Returns allocation result with seat IDs or waitlist position.
        """
        try:
            # Get inventory record
            inventory = await self.db.execute(
                select(SeatInventory).where(
                    and_(
                        SeatInventory.train_number == train_number,
                        SeatInventory.from_station_code == from_station,
                        SeatInventory.to_station_code == to_station,
                        SeatInventory.journey_date == travel_date,
                        SeatInventory.class_type == class_type
                    )
                ).with_for_update()
            )
            inventory = inventory.scalar_one_or_none()
            
            if not inventory:
                # Create inventory record if not exists
                inventory = SeatInventory(
                    id=f"{train_number}:{from_station}:{to_station}:{travel_date}:{class_type}",
                    train_number=train_number,
                    from_station_code=from_station,
                    to_station_code=to_station,
                    journey_date=travel_date,
                    class_type=class_type,
                    quota="GN",
                    total_seats=24,
                    available_seats=24,
                    status_text="AVAILABLE"
                )
                self.db.add(inventory)
                await self.db.flush()
                await self.db.refresh(inventory)
            
            # Check availability
            if inventory.available_seats >= num_seats:
                # Allocate seats
                seat_ids = [f"{train_number}-{class_type}-{i}" for i in range(num_seats)]
                
                inventory.available_seats -= num_seats
                if inventory.available_seats == 0:
                    inventory.status_text = "SOLD OUT"
                elif inventory.available_seats < 5:
                    inventory.status_text = "LIMITED"
                
                await self.db.flush()
                
                return {
                    "status": "allocated",
                    "seat_ids": seat_ids,
                    "price": 500 * num_seats  # Simplified pricing
                }
            else:
                # Add to waitlist
                position = inventory.waitlist_count + 1
                inventory.waitlist_count = position
                await self.db.flush()
                
                return {
                    "status": "waitlist",
                    "seat_ids": [],
                    "price": 500 * num_seats,
                    "waitlist_position": position
                }
                
        except Exception as e:
            logger.error(f"Error allocating seats: {e}")
            return {"status": "failed", "error": str(e)}
    
    async def lock_seats(
        self,
        seat_ids: List[str],
        booking_id: str,
        lock_duration: int = 30
    ) -> bool:
        """
        Lock allocated seats for payment timeout.
        
        Args:
            seat_ids: List of seat IDs to lock
            booking_id: Booking ID for reference
            lock_duration: Lock duration in minutes
            
        Returns:
            True if successful
        """
        try:
            for seat_id in seat_ids:
                # Update inventory record
                result = await self.db.execute(
                    select(SeatInventory).where(
                        SeatInventory.locked_by_booking_id == seat_id
                    ).with_for_update()
                )
                result = result.scalar_one_or_none()
                
                if result:
                    result.locked_by_booking_id = booking_id
                    result.locked_until = datetime.now(timezone.utc) + timedelta(minutes=lock_duration)
            
            await self.db.flush()
            return True
            
        except Exception as e:
            logger.error(f"Error locking seats: {e}")
            return False
    
    async def confirm_seats(self, booking_id: str) -> bool:
        """Confirm seat allocation after successful payment."""
        try:
            booking = await self.db.get(Booking, booking_id)
            if not booking:
                return False
            
            # Clear seat lock
            result = await self.db.execute(
                select(SeatInventory).where(
                    SeatInventory.locked_by_booking_id == booking_id
                ).with_for_update()
            )
            result = result.scalar_one_or_none()
            
            if result:
                result.locked_by_booking_id = None
                result.locked_until = None
            
            await self.db.flush()
            return True
            
        except Exception as e:
            logger.error(f"Error confirming seats: {e}")
            return False
    
    async def release_seats(self, booking_id: str) -> bool:
        """Release seats on booking cancellation."""
        try:
            booking = await self.db.get(Booking, booking_id)
            if not booking:
                return False
            
            # Release locked seats
            result = await self.db.execute(
                select(SeatInventory).where(
                    SeatInventory.locked_by_booking_id == booking_id
                ).with_for_update()
            )
            result = result.scalar_one_or_none()
            
            if result:
                result.locked_by_booking_id = None
                result.locked_until = None
                result.available_seats += len(booking.seats_allocated or [])
                result.status_text = "AVAILABLE"
            
            await self.db.flush()
            return True
            
        except Exception as e:
            logger.error(f"Error releasing seats: {e}")
            return False
    
    async def process_waitlist(
        self,
        train_number: str,
        from_station: str,
        to_station: str,
        travel_date: str,
        class_type: str
    ) -> List[str]:
        """
        Process waitlist when seats become available.
        
        Returns list of booking IDs to confirm.
        """
        try:
            # Get inventory
            inventory = await self.db.execute(
                select(SeatInventory).where(
                    and_(
                        SeatInventory.train_number == train_number,
                        SeatInventory.from_station_code == from_station,
                        SeatInventory.to_station_code == to_station,
                        SeatInventory.journey_date == travel_date,
                        SeatInventory.class_type == class_type
                    )
                ).with_for_update()
            )
            inventory = inventory.scalar_one_or_none()
            
            if not inventory or inventory.waitlist_count == 0:
                return []
            
            # Get waitlisted bookings
            waitlisted_bookings = await self.db.execute(
                select(Booking).where(
                    and_(
                        Booking.train_number == train_number,
                        Booking.from_station_code == from_station,
                        Booking.to_station_code == to_station,
                        Booking.travel_date == travel_date,
                        Booking.class_type == class_type,
                        Booking.booking_status == "waitlist"
                    )
                ).order_by(Booking.created_at)
            )
            waitlisted_bookings = waitlisted_bookings.scalars().all()
            
            # Confirm bookings based on available seats
            to_confirm = []
            for booking in waitlisted_bookings:
                if inventory.available_seats > 0:
                    inventory.available_seats -= 1
                    booking.booking_status = "confirmed"
                    booking.waitlist_position = None
                    to_confirm.append(booking.id)
                else:
                    break
            
            inventory.waitlist_count = len(waitlisted_bookings) - len(to_confirm)
            await self.db.flush()
            
            return to_confirm
            
        except Exception as e:
            logger.error(f"Error processing waitlist: {e}")
            return []
    
    def _get_status_text(self, available: int) -> str:
        """Get availability status text."""
        if available == 0:
            return "SOLD OUT"
        elif available < 5:
            return "LIMITED"
        else:
            return "AVAILABLE"


# Legacy singleton instance (deprecated, use get_inventory_service instead)
inventory_service = None

def get_inventory_service(db: AsyncSession) -> InventoryService:
    """Get or create inventory service instance."""
    return InventoryService(db)