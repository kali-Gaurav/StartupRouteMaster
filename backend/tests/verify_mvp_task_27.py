import asyncio
import sys
import os
from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus, AuditLog
from api.v2.agent import claim_booking
from fastapi import HTTPException

async def verify_task_27():
    import logging
    logging.basicConfig(level=logging.INFO)
    print("\n>>> STARTING VERIFICATION: MVP TASK 27 (AGENT CONCURRENCY)")
    
    db = SessionLocal()
    from sqlalchemy import text
    db.execute(text("PRAGMA foreign_keys = OFF"))
    
    booking_id = "B27_CONC_TEST"
    
    # 0. Setup
    db.query(Booking).filter(Booking.id == booking_id).delete()
    db.query(AuditLog).filter(AuditLog.entity_id == booking_id).delete()
    db.commit()

    # Create 20 mock agents and ensure they have NO other bookings
    for i in range(20):
        agent_id = f"AGENT_TEST_{i}"
        db.query(Booking).filter(Booking.agent_id == agent_id).delete()
        u = User(id=agent_id, email=f"a27_{i}@ex.com", role="agent", is_available=True)
        db.merge(u)
    db.commit()
        
    b1 = Booking(
        id=booking_id, user_id="u27", 
        service_type="AGENT_BOOKING", 
        escrow_status=EscrowStatus.VERIFIED,
        booking_details={}
    )
    db.merge(b1)
    db.commit()
    
    print(f"  Setup: Booking {booking_id} ready. 20 agents ready to race.")

    # 1. Execute Simultaneous Claims
    print("  Launching 20 simultaneous claims...")
    
    async def call_claim(agent_id):
        # Must use fresh session per agent to simulate real concurrency
        from database.session import SessionLocal
        with SessionLocal() as local_db:
            try:
                return await claim_booking(booking_id, agent_id, local_db)
            except HTTPException as e:
                return e

    # Staggered by 5ms to ensure they hit the server nearly at once but sequentially in the event loop
    tasks = [call_claim(f"AGENT_TEST_{i}") for i in range(20)]
    results = await asyncio.gather(*tasks)
    
    # 2. Analyze Results
    success_count = 0
    conflict_count = 0
    
    for r in results:
        # Check if the result is a dict with status success
        if isinstance(r, dict) and r.get("status") == "success":
            success_count += 1
        elif isinstance(r, HTTPException):
            if r.status_code == 409:
                conflict_count += 1
            else:
                print(f"    Unexpected HTTP Error: {r.status_code} - {r.detail}")
        else:
            print(f"    Unexpected Result Type: {type(r)}")
            
    print(f"    Winners: {success_count}, Losers (Conflict 409): {conflict_count}")
    
    # CRITICAL ASSERTION: Exactly ONE winner
    assert success_count == 1
    assert conflict_count == 19
    print("    ✅ SUCCESS: Atomic locking verified. No double-allocation.")

    # 3. Final Check in DB
    b1_final = db.query(Booking).filter(Booking.id == booking_id).first()
    print(f"    Winning Agent in DB: {b1_final.agent_id}")
    assert b1_final.agent_id.startswith("AGENT_TEST_")
    assert b1_final.escrow_status == EscrowStatus.BOOKING_INITIATED

    # 4. Cleanup
    db.query(Booking).filter(Booking.id == booking_id).delete()
    for i in range(20):
        db.query(User).filter(User.id == f"AGENT_TEST_{i}").delete()
    db.query(AuditLog).filter(AuditLog.entity_id == booking_id).delete()
    db.commit()
    
    print("\n✅ ALL MVP TASK 27 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_27())
