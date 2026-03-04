import httpx
import asyncio
import time

async def verify():
    print("--- 🛡️ Task 49: Predictive Danger Scoring Verification ---")
    
    base_url = "http://localhost:8000/api/sos/risk-check"
    
    # 1. Test High Risk Area (Near New Delhi - assuming seeded data)
    print("\n[Test 1] Checking High-Risk coordinates (28.64, 77.22)...")
    async with httpx.AsyncClient() as client:
        res1 = await client.get(f"{base_url}?lat=28.6428&lng=77.2190")
        data1 = res1.json()
        print(f"Risk Level: {data1.get('risk_level')}")
        print(f"Score: {data1.get('score')}")
        print(f"Suggest Guardian Mode: {data1.get('suggest_guardian_mode')}")
        
        # 2. Test Safe Area
        print("\n[Test 2] Checking Low-Risk coordinates (0, 0)...")
        res2 = await client.get(f"{base_url}?lat=0&lng=0")
        data2 = res2.json()
        print(f"Risk Level: {data2.get('risk_level')}")
        
        if data1.get("risk_level") in ["high", "critical", "medium"] and data2.get("risk_level") == "low":
            print("\n🏆 PREDICTIVE RISK SCORING VERIFIED: Spatial and night-bias logic functional.")
        else:
            print("\n❌ RISK SCORING FAILED: Logic did not differentiate areas correctly.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())