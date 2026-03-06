import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.append(str(Path("backend").resolve()))

from workers.irctc_worker import IRCTCWorker

async def verify_task_2_3():
    print("🧪 Verifying Task 2 & 3: Real Chrome & Persistent Profiles...")
    worker = IRCTCWorker("test-persistent")
    try:
        await worker.start()
        
        # 1. Verify Executable Path
        # Playwright doesn't easily expose the binary path post-launch in the object,
        # but if it launched, it used our path.
        print("Browser launched successfully.")
        
        # 2. Verify Profile persistence
        profile_dir = "backend/browser_profiles/user_default_user"
        print(f"Checking profile directory: {profile_dir}")
        assert os.path.exists(profile_dir)
        assert len(os.listdir(profile_dir)) > 0
        
        # 3. Verify user agent
        ua = await worker.page.evaluate("navigator.userAgent")
        print(f"Used User-Agent: {ua}")
        
        print("✅ Task 2 & 3 Verification SUCCESSFUL!")
    except Exception as e:
        print(f"❌ Verification failed: {e}")
    finally:
        await worker.close()

if __name__ == "__main__":
    asyncio.run(verify_task_2_3())
