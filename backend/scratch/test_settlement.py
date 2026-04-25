import asyncio
import logging
from database.session import SessionLocal
from database.models import Booking, Wallet
from services.settlement_service import SettlementService
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test.settlement")

async def test_settlement_payout():
    logger.info("🧪 [TEST] Starting Settlement Auto-Payout Verification...")
    
    # [FIX] Initialize Database Pools before JIT access
    from database.session import initialize_database_pools
    await initialize_database_pools()
    
    from database.models import User
    
    from sqlalchemy import text
    
    with SessionLocal() as db:
        # 0. Create dummy users (using raw SQL to bypass naming drift)
        agent_id = "test_agent_101"
        user_id = "test_user_99"
        
        for uid in [agent_id, user_id]:
            res = db.execute(text("SELECT id FROM users WHERE id = :uid"), {"uid": uid}).fetchone()
            if not res:
                db.execute(text("INSERT INTO users (id) VALUES (:uid)"), {"uid": uid})
        db.commit()

        # 1. Create a dummy wallet if not exists
        wallet = db.query(Wallet).filter_by(user_id=agent_id).first()
        if not wallet:
            wallet = Wallet(user_id=agent_id, total_earned=0, balance=0)
            db.add(wallet)
            db.commit()
            logger.info(f"Created test agent wallet for {agent_id}")

        # 2. Create a COMPLETED booking
        booking = Booking(
            user_id="test_user",
            agent_id=agent_id,
            amount_paid=6000.0, # Should trigger 7% commission
            booking_status="COMPLETED",
            created_at=datetime.utcnow(),
            metadata={}
        )
        db.add(booking)
        db.commit()
        logger.info(f"Created COMPLETED booking {booking.id} for ₹6000")

        # 3. Trigger Settlement
        svc = SettlementService()
        await svc.process_completed_trip_settlement(db, str(booking.id))
        
        # 4. Verify Results
        db.refresh(wallet)
        db.refresh(booking)
        
        expected_commission = 6000 * 0.07 # 420
        logger.info(f"📊 Results: Wallet Balance: ₹{wallet.balance} | Payout Ref: {booking.booking_details.get('payout_ref') if booking.booking_details else 'N/A'}")
        
        if wallet.balance == expected_commission and booking.booking_details and booking.booking_details.get("settled"):
            logger.info("✅ SUCCESS: Settlement Payout Verified with Multi-Tier Logic!")
        else:
            logger.error(f"❌ FAILURE: Verification mismatch. Expected ₹{expected_commission}, got ₹{wallet.balance}")

if __name__ == "__main__":
    asyncio.run(test_settlement_payout())
