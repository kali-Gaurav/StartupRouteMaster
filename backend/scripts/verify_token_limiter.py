import sys
import os
import time

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from utils.token_limiter import TokenLimiter
from services.cache_service import cache_service

def test_limiter():
    print("--- Token Usage Limiter Verification ---")
    session_id = "test-limiter-session"
    
    if not cache_service.is_available():
        print("[SKIP] Redis not available, skipping test.")
        return

    # Reset usage for test
    cache_service.redis.delete(f"{TokenLimiter.KEY_PREFIX}{session_id}")
    
    # 1. Check under limit
    print(f"\n[Test 1] Checking usage (0/{TokenLimiter.DAILY_LIMIT})...")
    if TokenLimiter.check_limit(session_id):
        print("[PASS] Limit check passed for new session.")
    else:
        print("[FAIL] Limit check failed for new session.")

    # 2. Update usage
    print(f"\n[Test 2] Adding 5000 tokens...")
    TokenLimiter.update_usage(session_id, 5000)
    if TokenLimiter.check_limit(session_id):
        print("[PASS] Still under limit.")
    else:
        print("[FAIL] Incorrectly blocked.")

    # 3. Reach limit
    print(f"\n[Test 3] Adding 6000 more tokens (Total 11000)...")
    TokenLimiter.update_usage(session_id, 6000)
    if not TokenLimiter.check_limit(session_id):
        print("[PASS] Limit correctly triggered.")
    else:
        print("[FAIL] Limit failed to trigger.")

if __name__ == "__main__":
    test_limiter()
