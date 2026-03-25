import asyncio
from datetime import datetime, timedelta
from sqlalchemy import text
from database.session import get_async_db
from database.models import User, Subscription
from services.subscription_service import SubscriptionService
from core.container import container

async def verify_state_consistency():
    # 1. Initialize Container (Required for DB access)
    await container.get("db") 
    
    # 2. Setup Test User
    async for db in get_async_db():
        # Corrected: Use text() for raw SQL
        result = await db.execute(text("SELECT * FROM users WHERE email = 'test_user@routemaster.com'"))
        user = result.scalar()
        if not user:
            print("Test user not found, skipping.")
            return
        
        # 3. Set to PRO
        SubscriptionService.upgrade_user(db, user.id, "PRO", months=1)
        sub = SubscriptionService.get_user_subscription(db, user.id)
        
        # 4. Check Consistency
        print(f"Verifying: Tier={sub.plan_tier}, Is_Pro={sub.is_pro}, Expiry={sub.expires_at}")
        assert sub.is_pro is True
        assert sub.plan_tier == "PRO"
        
        # 5. Simulate Expiry
        sub.expires_at = datetime.utcnow() - timedelta(days=1)
        await db.commit()
        await db.refresh(sub)
        
        # 6. Check Reversion Logic
        is_active = SubscriptionService.is_active_pro(sub)
        print(f"Reversion Check: Is_Active={is_active}")
        assert is_active is False
        
        print("✅ State Consistency Verified.")

if __name__ == "__main__":
    asyncio.run(verify_state_consistency())
