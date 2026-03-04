import sys
import os
import time

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from utils.chat_cache import ChatCache
from services.cache_service import cache_service

def test_cache():
    print("--- Chat Cache Verification ---")
    
    if not cache_service.is_available():
        print("[SKIP] Redis not available, skipping test.")
        return

    message = "What are the rules for ticket cancellation?"
    response_data = {"reply": "Cancellation rules vary by class...", "intent": "info"}
    
    # Reset cache for test
    key = f"{ChatCache.KEY_PREFIX}{ChatCache._get_hash(message)}"
    cache_service.redis.delete(key)
    
    # 1. First attempt (Miss)
    print(f"\n[Test 1] Checking cache for new message...")
    cached = ChatCache.get(message)
    if cached is None:
        print("[PASS] Cache miss as expected.")
    else:
        print("[FAIL] Unexpected cache hit.")

    # 2. Set cache
    print(f"\n[Test 2] Setting cache for message...")
    ChatCache.set(message, response_data)
    
    # 3. Second attempt (Hit)
    print(f"\n[Test 3] Checking cache again...")
    cached = ChatCache.get(message)
    if cached and cached["reply"] == response_data["reply"]:
        print("[PASS] Cache hit! Data retrieved correctly.")
    else:
        print("[FAIL] Cache retrieval failed.")

if __name__ == "__main__":
    test_cache()
