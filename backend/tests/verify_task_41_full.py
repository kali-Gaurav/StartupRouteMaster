import asyncio
from datetime import datetime, timedelta
from sqlalchemy import text
from database.session import get_async_db
from database.models import User, Subscription
from services.subscription_service import SubscriptionService
from core.container import container

async def full_cycle_verification():
    # 1. Initialize Container
    await container.get("db") 
    
    # 2. Setup DB Session (Manually handling async generator)
    db_gen = get_async_db()
    db = await db_gen.__anext__()
    
    try:
        # Create test user
        new_user = User(email="verify_test@routemaster.com", phone_number="9999999999")
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        print(f"✅ Created test user: {new_user.id}")

        # 3. Upgrade to PRO
        SubscriptionService.upgrade_user(db, new_user.id, "PRO", months=1)
        sub = SubscriptionService.get_user_subscription(db, new_user.id)
        
        # Verify Tier Engine
        print(f"Verifying: Tier={sub.plan_tier}, Is_Pro={sub.is_pro}")
        assert sub.plan_tier == "PRO"
        assert sub.is_pro is True
        
        # 4. Verify Pricing Gate
        is_pro = (sub.is_pro and (not sub.expires_at or sub.expires_at > datetime.utcnow()))
        print(f"Pricing Gate Check: is_pro={is_pro}")
        assert is_pro is True
        
        # 5. Simulate Expiry
        sub.expires_at = datetime.utcnow() - timedelta(days=1)
        await db.commit()
        await db.refresh(sub)
        
        # 6. Verify Reversion
        is_pro_after_expiry = SubscriptionService.is_active_pro(sub)
        print(f"Expiry Reversion Check: Is_Active={is_pro_after_expiry}")
        assert is_pro_after_expiry is False
        
        print("✅ Task 41 Full Cycle Verified Successfully.")
        
    finally:
        # Cleanup
        await db_gen.aclose()

if __name__ == "__main__":
    asyncio.run(full_cycle_verification())
