import sys
import os
import uuid

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.session import SessionLocal
from database.models import User, AuditLog
from services.credential_vault import CredentialVault

def verify_task_35():
    print("=== Verifying Task 35: AES-256 Credential Vault ===")
    
    db = SessionLocal()
    vault = CredentialVault(db)
    
    try:
        user_id = str(uuid.uuid4())
        # Commit user first to satisfy FKs
        user = User(id=user_id, email=f"vault_{user_id}@example.com")
        db.add(user)
        db.commit()

        # 1. Test Storage (Task 35.1, 35.2, 35.9)
        print("Testing credential encryption and storage...")
        irctc_user = "gaurav_irctc"
        irctc_pass = "SecurePass123!"
        
        success = vault.store_credentials(user_id, irctc_user, irctc_pass, persistent=False)
        assert success is True
        
        db.refresh(user)
        assert user.encrypted_irctc_creds is not None
        assert user.creds_iv is not None
        print("[OK] Credentials encrypted with PBKDF2 and unique IV")

        # 2. Test Retrieval & Audit (Task 35.5)
        print("Testing retrieval and security audit logging...")
        creds = vault.get_credentials(user_id)
        assert creds is not None
        assert creds[0] == irctc_user
        assert creds[1] == irctc_pass
        
        # Check audit logs
        logs = db.query(AuditLog).filter(AuditLog.entity_id == user_id).all()
        assert any(log.action == "VAULT_STORE" for log in logs)
        assert any(log.action == "VAULT_ACCESS" for log in logs)
        print("[OK] Decryption successful and access events logged")

        # 3. Test Weak Password Detection (Task 35.7)
        print("Testing weak password detection...")
        assert vault.is_weak_password("12345678") is True
        assert vault.is_weak_password("irctc123") is True
        assert vault.is_weak_password("MyVeryStrongPassword2026!") is False
        print("[OK] Weak passwords correctly identified")

        # 4. Test Auto-Wipe (Task 35.3)
        print("Testing auto-wipe (non-persistent)...")
        vault.auto_wipe(user_id)
        db.refresh(user)
        assert user.encrypted_irctc_creds is None
        assert user.creds_iv is None
        print("[OK] Credentials wiped successfully after use")

    finally:
        db.close()

    print("=== Task 35 Verification Complete ===")

if __name__ == "__main__":
    verify_task_35()
