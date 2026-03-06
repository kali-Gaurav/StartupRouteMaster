import sys
import os
import asyncio
from services.fraud_detection_service import fraud_service
from services.cache_service import cache_service

def verify_task_3():
    print("=== Verifying Task 3: Fraudulent UTR Lockout ===")
    
    user_id = "test_fraud_user_123"
    # Clear any existing locks for a clean test
    cache_service.delete(f"fraud_lockout:{user_id}")
    cache_service.delete(f"fraud_attempts:{user_id}")
    
    # 1. Test Pattern Matching
    print("Testing geometric pattern matching...")
    assert fraud_service.is_geometric_pattern("111111111111") is True
    assert fraud_service.is_geometric_pattern("123456789012") is True
    assert fraud_service.is_geometric_pattern("123412341234") is True
    assert fraud_service.is_geometric_pattern("987654321098") is True
    assert fraud_service.is_geometric_pattern("582930412834") is False
    print("[OK] Pattern Matching")

    # 2. Test Lockout after 3 failures
    print("Testing lockout mechanism...")
    
    # Attempt 1: Valid format but wrong UTR
    valid, err = fraud_service.validate_utr_advanced("582930412834", user_id)
    assert valid is True
    fraud_service.record_attempt(user_id, False) # Record failure
    
    # Attempt 2: Valid format but wrong UTR
    valid, err = fraud_service.validate_utr_advanced("192837465012", user_id)
    assert valid is True
    fraud_service.record_attempt(user_id, False) # Record failure
    
    # Attempt 3: This should trigger lockout AFTER recording
    valid, err = fraud_service.validate_utr_advanced("776655443322", user_id)
    assert valid is True
    fraud_service.record_attempt(user_id, False) # Record failure (3rd failure)
    
    # Attempt 4: Should be blocked
    valid, err = fraud_service.validate_utr_advanced("123456789012", user_id)
    assert valid is False
    assert "locked" in err.lower()
    print(f"[OK] Lockout triggered: {err}")

    # 3. Test Velocity Limit
    user_id_v = "test_velocity_user"
    cache_service.delete(f"fraud_lockout:{user_id_v}")
    cache_service.delete(f"fraud_velocity:{user_id_v}")
    
    print("Testing velocity limits...")
    for i in range(5):
        fraud_service.record_attempt(user_id_v, False)
        
    is_blocked, reason = fraud_service.check_lockout(user_id_v)
    assert is_blocked is True
    assert "temporarily locked" in reason.lower()
    print("[OK] Velocity limit triggered")

    print("=== Task 3 Verification Complete ===")

if __name__ == "__main__":
    verify_task_3()
