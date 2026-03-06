import sys
import os
import asyncio
from services.fraud_detection_service import fraud_service
from services.cache_service import cache_service

def verify_task_3_gaps():
    print("=== Verifying Task 3 Gaps: Geo-Fencing, Honeypots, and IP Tracking ===")
    
    user_id = "test_gap_user"
    ip_india = "103.21.244.0" # Example local/Indian IP
    ip_foreign = "54.21.10.10" # Example blocked foreign IP
    
    cache_service.delete(f"fraud_lockout:{user_id}")
    cache_service.delete(f"fraud_lockout:IP:{ip_foreign}")
    
    # 1. Test Geo-fencing
    print("Testing Geo-fencing (Foreign IP)...")
    valid, err = fraud_service.validate_utr_advanced("123456789012", user_id, ip_address=ip_foreign)
    assert valid is False
    assert "restricted to Indian IP" in err
    print("[OK] Geo-fencing blocked foreign IP")

    # 2. Test Honeypot
    print("Testing Honeypot UTR...")
    valid, err = fraud_service.validate_utr_advanced("111111111111", user_id, ip_address=ip_india)
    assert valid is False
    assert "permanently flagged" in err
    
    # Verify the user is now locked out
    is_blocked, reason = fraud_service.check_lockout(user_id)
    assert is_blocked is True
    print("[OK] Honeypot triggered and locked account")

    # 3. Test Admin Clear
    print("Testing Admin Lockout Clear...")
    fraud_service.clear_lockout(user_id)
    is_blocked, reason = fraud_service.check_lockout(user_id)
    assert is_blocked is False
    print("[OK] Admin successfully cleared lockout")

    print("=== Task 3 Gaps Verification Complete ===")

if __name__ == "__main__":
    verify_task_3_gaps()
