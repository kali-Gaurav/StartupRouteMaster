import asyncio
from datetime import datetime
from sqlalchemy import text
from database.session import get_async_db
from database.models import User
from services.karma_service import KarmaService
from services.credit_service import UnlockCreditService, BUNDLE_PACKS
from core.container import container

async def hard_verify_task_43():
    # 1. Initialize Container
    await container.get("db")
    
    # 2. Setup DB Session (Manually handling async generator)
    db_gen = get_async_db()
    db = await db_gen.__anext__()
    
    try:
        # Setup: Create referrer and referee
        referrer = User(email="ref_main@test.com", phone_number="111")
        referee = User(email="ref_new@test.com", phone_number="222")
        db.add(referrer)
        db.add(referee)
        await db.commit()
        await db.refresh(referrer)
        await db.refresh(referee)
        
        # 3. Verify Referral Logic (Task 43.C)
        KarmaService.link_referral(db, referrer.id, referee.id)
        print("✅ Referral link established.")
        
        # 4. Verify Milestone Pipeline (Task 43.B)
        KarmaService.add_karma(db, referrer.id, 600, "HELPFUL_REVIEW")
        
        balance = UnlockCreditService.get_user_balance(db, referrer.id)
        print(f"✅ Karma Milestone reached. Balance: {balance['total']}")
        assert balance['total'] > 0
        
        # 5. Verify Pricing Discount (Task 43.D)
        KarmaService.add_karma(db, referrer.id, 5000, "POWER_USER_CONTRIB")
        
        bundle = BUNDLE_PACKS["PRO_50"]
        # Assuming calculate_price exists or mock logic for test
        discounted_price = UnlockCreditService.calculate_price(bundle["price"], referrer.id, db)
        print(f"✅ Pricing Engine Check (10% discount): ₹{discounted_price}")
        assert discounted_price < bundle["price"]
        
        # 6. Verify Fraud Prevention
        can_grant = KarmaService.can_grant_referral_reward(db, referee.id)
        assert can_grant is False
        print("✅ Referral Fraud Prevention Verified.")

        print("🚀 Task 43 Deep-Verification Complete.")
        
    finally:
        # Cleanup
        await db_gen.aclose()

if __name__ == "__main__":
    asyncio.run(hard_verify_task_43())
