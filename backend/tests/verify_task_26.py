import asyncio
import sys
import os
from datetime import datetime
from database.session import SessionLocal, SessionTransit
from sqlalchemy import text
from database.models import User, SeatInventory
from api.v2.unlock import initiate_unlock
from unittest.mock import MagicMock

async def verify_task_26():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 26 (AUTO SEAT LOCK)")
    
    db_user = SessionLocal()
    db_transit = SessionTransit()
    db_transit.execute(text("PRAGMA foreign_keys = OFF"))
    
    user_id = "u26"
    trip_id = 12625
    travel_date = datetime.utcnow().date()
    coach = "SL"
    
    # 0. Setup User and Inventory
    u = User(id=user_id, email="u26@ex.com")
    db_user.merge(u)
    db_user.commit()
    
    inv = db_transit.query(SeatInventory).filter(
        SeatInventory.trip_id == trip_id,
        SeatInventory.travel_date == travel_date,
        SeatInventory.coach_type == coach
    ).first()
    
    if not inv:
        inv = SeatInventory(
            trip_id=trip_id, travel_date=travel_date, coach_type=coach,
            total_seats=100, available_seats=1, stop_time_id=99926
        )
        db_transit.add(inv)
    else:
        inv.available_seats = 1
        inv.locked_by_booking_id = None
    db_transit.commit()
    
    print("  Initial Inventory: 1 seat.")
    
    # 1. Initiate Unlock (Should trigger lock)
    print("  Initiating unlock request (calling API logic)...")
    request = MagicMock()
    res = await initiate_unlock(request, journey_id="J26", user_id=user_id, db=db_user)
    
    booking_id = res["data"]["booking_id"]
    print(f"    Booking ID created: {booking_id}")
    
    # 2. Verify Lock
    db_transit.refresh(inv)
    print(f"    Available Seats after init: {inv.available_seats}")
    print(f"    Locked by: {inv.locked_by_booking_id}")
    
    assert inv.available_seats == 0
    assert inv.locked_by_booking_id == booking_id
    
    # 3. Cleanup
    from database.models import Booking, PaymentSession, AuditLog
    db_user.query(PaymentSession).filter(PaymentSession.user_id == user_id).delete()
    db_user.query(Booking).filter(Booking.id == booking_id).delete()
    db_user.commit()
    db_transit.delete(inv)
    db_transit.commit()
    
    print("\n✅ TASK 26 FULLY VERIFIED: Seat is automatically reserved upon payment initiation.")

if __name__ == "__main__":
    asyncio.run(verify_task_26())
