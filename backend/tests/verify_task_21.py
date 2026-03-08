import asyncio
import sys
import os
from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus
from api.v2.agent import get_agent_queue

async def verify_task_21():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 21 (AGENT DASHBOARD API)")
    
    db = SessionLocal()
    
    # 0. Setup test data with different priorities
    u = User(id="u21", email="u21@ex.com")
    db.merge(u)
    
    # Priority 10 (Normal)
    b1 = Booking(id="B21_NORMAL", user_id="u21", service_type="AGENT_BOOKING", escrow_status=EscrowStatus.VERIFIED, priority=10, booking_details={})
    # Priority 5 (High)
    b2 = Booking(id="B21_HIGH", user_id="u21", service_type="AGENT_BOOKING", escrow_status=EscrowStatus.VERIFIED, priority=5, booking_details={})
    # Priority 0 (Tatkal)
    b3 = Booking(id="B21_TATKAL", user_id="u21", service_type="AGENT_BOOKING", escrow_status=EscrowStatus.VERIFIED, priority=0, booking_details={})
    
    db.merge(b1); db.merge(b2); db.merge(b3)
    db.commit()
    
    # 1. Fetch Queue
    print("  Fetching agent queue...")
    queue = await get_agent_queue(db=db)
    
    # 2. Verify Ordering (Subtask 21.2)
    print(f"    Queue Count: {len(queue)}")
    order = [b.id for b in queue if b.id.startswith("B21")]
    print(f"    Order: {order}")
    
    # Should be Tatkal -> High -> Normal
    assert order == ["B21_TATKAL", "B21_HIGH", "B21_NORMAL"]
    
    # 3. Cleanup
    db.query(Booking).filter(Booking.id.in_(["B21_NORMAL", "B21_HIGH", "B21_TATKAL"])).delete()
    db.commit()
    
    print("\n✅ TASK 21 FULLY VERIFIED: Agent queue is correctly prioritized (Tatkal first).")

if __name__ == "__main__":
    asyncio.run(verify_task_21())
