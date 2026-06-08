import asyncio
import uuid
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import AsyncSessionUser, init_db
from database.models import User, Profile
from database.config import Config

async def seed_data():
    """Task 8: Local Mock Seeding Script."""
    print(f"🚀 Seeding database in {Config.ENVIRONMENT} mode...")
    
    # Initialize tables
    await init_db()
    
    async with AsyncSessionUser() as session:
        # 1. Create Admin User
        admin_email = "admin@routemaster.ai"
        existing_admin = await session.execute(
            "SELECT id FROM users WHERE email = :email", {"email": admin_email}
        )
        if not existing_admin.first():
            admin_id = str(uuid.uuid4())
            admin = User(
                id=admin_id,
                email=admin_email,
                full_name="Super Admin",
                role="admin",
                firebase_uid="mock-admin-id"
            )
            session.add(admin)
            
            profile = Profile(
                id=str(uuid.uuid4()),
                user_id=admin_id,
                name="Super Admin",
                karma_score=1000
            )
            session.add(profile)
            print("✅ Admin user created.")
        else:
            print("ℹ️ Admin user already exists.")

        # 2. Create Mock Test User
        test_email = "test@user.com"
        existing_test = await session.execute(
            "SELECT id FROM users WHERE email = :email", {"email": test_email}
        )
        if not existing_test.first():
            user_id = str(uuid.uuid4())
            user = User(
                id=user_id,
                email=test_email,
                full_name="Test Passenger",
                role="user",
                firebase_uid="mock-test-id"
            )
            session.add(user)
            
            profile = Profile(
                id=str(uuid.uuid4()),
                user_id=user_id,
                name="Test Passenger",
                blood_group="O+",
                karma_score=100
            )
            session.add(profile)
            print("✅ Test user created.")
        else:
            print("ℹ️ Test user already exists.")

        await session.commit()
    
    print("✨ Seeding complete!")

if __name__ == "__main__":
    if Config.ENVIRONMENT == "production":
        confirm = input("⚠️ CRITICAL: You are in PRODUCTION mode. Seed anyway? (y/N): ")
        if confirm.lower() != 'y':
            print("Aborted.")
            sys.exit(0)
            
    asyncio.run(seed_data())
