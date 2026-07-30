import asyncio
import uuid
from database.session import SessionUser, init_db
from database.models import User, IdentityFingerprint, FraudAlert
from services.fraud_service import fraud_service

async def verify_task_45():
    print("🧪 Starting Verification for Task 45: Project Shield S2...")
    await init_db()
    
    with SessionUser() as db:
        # 1. Create Mock User
        user_id = str(uuid.uuid4())
        user = User(id=user_id, email=f"fraud_test_{user_id[:4]}@example.com")
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"✅ Created Mock User: {user.email}")

        # 2. Case: Valid Fingerprinting
        print("👤 Testing Identity Fingerprinting...")
        ip = "192.168.1.1"
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
        
        score = fraud_service.validate_identity(db, user, ip, ua)
        print(f"📊 Initial Risk Score: {score} (Expected 0.0)")
        assert score == 0.0
        assert user.last_fingerprint is not None

        # 3. Case: Sybil Attack (Too many users same device)
        print("🕵️ Simulating Sybil Attack (3+ Users on same IP/UA)...")
        for i in range(4):
            temp_user = User(id=str(uuid.uuid4()), email=f"attacker_{i}@example.com")
            db.add(temp_user)
            db.commit()
            # Link to SAME fingerprint
            fp = IdentityFingerprint(
                user_id=temp_user.id,
                fingerprint_hash=user.last_fingerprint,
                ip_address=ip,
                user_agent=ua
            )
            db.add(fp)
            db.commit()
            
        # Re-check main user
        score_sybil = fraud_service.validate_identity(db, user, ip, ua)
        print(f"📊 Risk Score after Sybil injection: {score_sybil} (Expected 1.0)")
        assert score_sybil == 1.0

        # 4. Verify Alert Generation
        alerts = db.query(FraudAlert).filter(FraudAlert.user_id == user.id).all()
        print(f"📜 Fraud Alerts Found: {len(alerts)} (Expected 1: SYBIL_ATTACK)")
        assert len(alerts) >= 1
        assert alerts[0].alert_type == "SYBIL_ATTACK"

    print("\n✅ TASK 45 VERIFIED: Security Fingerprinting and Sybil Protection is Active.")

if __name__ == "__main__":
    asyncio.run(verify_task_45())
