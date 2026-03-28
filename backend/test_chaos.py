import asyncio
import httpx
import time
from httpx import Response

async def run_tests():
    print("🚀 [TEST 1] Testing Database Decapitation (Ghost Mode)")
    
    # Check initial health
    async with httpx.AsyncClient() as client:
        try:
            r1 = await client.get("http://localhost:8000/healthz/ready")
            print(f"Initial Health: {r1.json()}")
        except Exception as e:
            print(f"Error connecting to server: {e}")
            return
            
        print("\n💥 Arming DB Severance Chaos Trap (if available) / Faking state...")
        # Since we modified the orchestrator to check `text("SELECT 1")`, we can just 
        # force the `nexus_boot.state` via direct modification for the test using an internal test hook,
        # but since we're testing the API, we can forcefully make the API think we are SEVERED.
        
        # We can trigger SEVERED by arming `cache_l2` and `db_main` if they exist
        try:
            r_arm = await client.post("http://localhost:8000/nexus/chaos/arm/db_main", params={"error_rate": 1.0})
            print(f"Chaos Arm DB Response: {r_arm.status_code}")
        except: pass
        
        try:
            r_arm2 = await client.post("http://localhost:8000/nexus/chaos/arm/cache_l2", params={"error_rate": 1.0})
            print(f"Chaos Arm Redis Response: {r_arm2.status_code}")
        except: pass

        # Wait
        print("Waiting 16 seconds for Orchestrator Ghost Mode Monitor to detect outage...")
        for i in range(16):
            await asyncio.sleep(1)
            
        # Check Healthz Fallback
        r_health = await client.get("http://localhost:8000/healthz/ready")
        print(f"\n👻 Post-Crash Health Check (/healthz/ready): {r_health.json()}")
        
        # Check Write Blockade (Read-Only API Lockout)
        print("\n🛡️ Testing Write Blockade (POST /api/some_protected_route)")
        r_write = await client.post("http://localhost:8000/api/some_protected_route")
        print(f"Write Attempt Status: {r_write.status_code}")
        try:
            print(f"Write Attempt Response: {r_write.json()}")
        except: pass

if __name__ == "__main__":
    asyncio.run(run_tests())
