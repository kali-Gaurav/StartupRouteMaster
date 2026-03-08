import asyncio
import sys
import os
from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus
from services.multi_layer_cache import multi_layer_cache
from api.v2.booking import submit_utr
from schemas.booking import SubmitUtrSchema
from unittest.mock import MagicMock
from fastapi import HTTPException

async def verify_task_23():
    print("\n>>> STARTING VERIFICATION: MVP TASK 23 (UTR DISTRIBUTED LOCK)")
    
    db = SessionLocal()
    from sqlalchemy import text
    db.execute(text("PRAGMA foreign_keys = OFF"))
    
    booking_id = "B23_LOCK_TEST"
    user_id = "u23"
    utr = "999988887777"
    
    # 0. Setup
    await multi_layer_cache.initialize()
    if multi_layer_cache.redis:
        await multi_layer_cache.redis.delete(f"lock:utr:{utr}")
        
    db.query(User).filter(User.id == user_id).delete()
    db.commit()
    
    u = User(id=user_id, email="u23@ex.com")
    db.add(u)
    
    b1 = Booking(
        id=booking_id, user_id=user_id, 
        service_type="UNLOCK", 
        escrow_status=EscrowStatus.CREATED,
        amount_paid=49.0,
        booking_details={}
    )
    db.merge(b1)
    db.commit()
    
    payload = SubmitUtrSchema(utr_number=utr)
    background_tasks = MagicMock()
    request = MagicMock()

    # 1. Simulate Concurrency
    print("  Simulating 5 concurrent UTR submissions for same number...")
    
    async def call_submit(delay):
        await asyncio.sleep(delay)
        try:
            # We must use a NEW DB session per task to simulate different threads/workers
            from database.session import SessionLocal
            with SessionLocal() as local_db:
                # Refresh user in new session
                local_user = local_db.query(User).filter(User.id == user_id).first()
                return await submit_utr(request, payload, background_tasks, booking_id, local_db, local_user)
        except HTTPException as e:
            return e

    # Staggered starts (0ms, 1ms, 2ms...)
    tasks = [call_submit(i * 0.001) for i in range(5)]
    results = await asyncio.gather(*tasks)
    
    # 2. Analyze Results
    success_count = 0
    lock_count = 0
    
    for r in results:
        if isinstance(r, dict) and r.get("status") == "UTR_SUBMITTED":
            success_count += 1
        elif isinstance(r, HTTPException) and r.status_code == 429:
            lock_count += 1
            
    print(f"    Success: {success_count}, Locked: {lock_count}")
    
    # EXACTLY one should succeed in the race
    assert success_count == 1
    assert lock_count == 4
    print("    SUCCESS: Only one request won the race. Others were blocked.")

    # 3. Cleanup
    db.query(Booking).filter(Booking.id == booking_id).delete()
    db.query(User).filter(User.id == user_id).delete()
    db.commit()
    
    print("\n✅ ALL MVP TASK 23 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_23())
