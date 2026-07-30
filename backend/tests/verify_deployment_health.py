import asyncio
import httpx
import sys
import time
from datetime import datetime

async def verify_boot_readiness(url="http://localhost:8000/healthz/ready", max_retries=10):
    """
    [Task 76] Verifies that the RouteMaster V3 Spine reaches READY or GHOST_MODE.
    Fails the deployment if the server remains OFFLINE or in SAFE_MODE.
    """
    print(f"🛡️ [{datetime.now().isoformat()}] Deployment Watchdog: Checking Boot Readiness...")
    
    async with httpx.AsyncClient() as client:
        for attempt in range(1, max_retries + 1):
            try:
                response = await client.get(url, timeout=5.0)
                data = response.json()
                
                status = data.get("status")
                print(f"Attempt {attempt}/{max_retries}: Received status '{status}'")
                
                if status in ["ready", "ready_ghost_mode"]:
                    print(f"✅ Success: Server is {status.upper()}.")
                    return True
                
                if status == "not_ready":
                    reason = data.get("reason", "Unknown")
                    print(f"⚠️ Server is NOT_READY. Reason: {reason}")
                    
            except httpx.RequestError as e:
                print(f"Attempt {attempt}/{max_retries}: Waiting for server... ({e})")
            
            await asyncio.sleep(2)
            
    print("❌ Critical: Deployment Timed Out. Server failed to reach READY state.")
    return False

if __name__ == "__main__":
    success = asyncio.run(verify_boot_readiness())
    if not success:
        sys.exit(1)
    sys.exit(0)
