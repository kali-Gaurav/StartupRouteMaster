import asyncio
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from services.telecom_service import telecom_service
from utils.circuit_breaker import telecom_breaker

async def verify():
    print("--- 🛑 Task 15: Telecom Circuit Breaker Verification ---")
    
    # 1. Trigger multiple failures
    print("\n[Step 1] Simulating 3 consecutive API failures...")
    for i in range(3):
        res = await telecom_service.initiate_emergency_call("FAIL_TEST", {"category": "test"})
        print(f"   Attempt {i+1} result: {res}")
        
    print(f"\n[Step 2] Verifying circuit state: {telecom_breaker.state}")
    
    if telecom_breaker.state == "OPEN":
        print("✅ SUCCESS: Circuit correctly opened after threshold reached.")
        
        # 3. Test rapid rejection
        print("\n[Step 3] Testing rapid rejection (should not even try the call)...")
        res_fast = await telecom_service.initiate_emergency_call("VALID_PHONE", {"category": "test"})
        if res_fast == False:
            print("✅ SUCCESS: Immediate fallback triggered without API call.")
            print("\n🏆 TASK 15 VERIFIED: Circuit Breaker protects the system from failing APIs.")
        else:
            print("❌ FAILURE: Circuit allowed call through while OPEN.")
    else:
        print(f"❌ FAILURE: Circuit state is {telecom_breaker.state}, expected OPEN.")

if __name__ == "__main__":
    asyncio.run(verify())
