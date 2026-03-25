import asyncio
import uuid
from database.session import SessionUser, init_db
from database.models import User, CreditTransaction
from services.credit_service import credit_service
from services.subscription_service import subscription_service

async def verify_task_42():
    print("🧪 Starting Verification for Task 42: Credit/Token Economy...")
    await init_db()
    
    with SessionUser() as db:
        # 1. Create Mock User
        user_id = str(uuid.uuid4())
        user = User(id=user_id, email=f"credit_test_{user_id[:4]}@example.com")
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"✅ Created Mock User: {user.email}")

        # 2. Case: Initial Balance should be 0
        bal = credit_service.get_user_balance(db, user_id)
        print(f"📊 Initial Balance: {bal['total']}")
        assert bal["total"] == 0

        # 3. Case: Top-up (Starter Pack - 5 Credits)
        print("💰 Testing Top-up (5 Credits)...")
        # Simulate payment verification
        credit_service.top_up_credits(db, user_id, "STARTER_5", "PAY_MOCK_1")
        bal_after = credit_service.get_user_balance(db, user_id)
        print(f"📊 Balance after Top-up: {bal_after['total']} (Expected 6, including 1 First-purchase bonus)")
        assert bal_after["total"] == 6 # 5 Paid + 1 Bonus
        assert bal_after["paid"] == 5
        assert bal_after["bonus"] == 1

        # 4. Case: Consume 1 Credit
        print("🎟️ Consuming 1 Credit for a mock booking...")
        success = credit_service.consume_credit(db, user_id, "BOOK_MOCK_1")
        bal_final = credit_service.get_user_balance(db, user_id)
        print(f"📊 Final Balance after Consumption: {bal_final['total']} (Expected 5)")
        assert success == True
        assert bal_final["total"] == 5
        assert bal_final["bonus"] == 0 # Bonus should be consumed first
        assert bal_final["paid"] == 5

        # 5. Verify Transaction Ledger
        txs = db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id).all()
        print(f"📜 Transaction Ledger Count: {len(txs)} (Expected 3: Purchase, Bonus, Consumption)")
        assert len(txs) == 3

    print("\n✅ TASK 42 VERIFIED: Credit/Token Economy Logic is Fully Functional.")

if __name__ == "__main__":
    asyncio.run(verify_task_42())
