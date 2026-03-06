import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path("backend").resolve()))

from workers.irctc_worker import IRCTCWorker

async def verify_task_1():
    print("🧪 Verifying Task 1: Playwright Stealth & Fingerprinting...")
    worker = IRCTCWorker("test-stealth")
    try:
        await worker.start()
        
        # 1. Verify Stealth
        is_webdriver = await worker.page.evaluate("navigator.webdriver")
        print(f"navigator.webdriver: {is_webdriver}")
        assert is_webdriver is False or is_webdriver is None
        
        # 2. Verify Plugins (Should not be empty in a real-looking browser)
        plugin_count = await worker.page.evaluate("navigator.plugins.length")
        print(f"navigator.plugins count: {plugin_count}")
        assert plugin_count > 0
        
        # 3. Verify User-Agent randomization
        ua = await worker.page.evaluate("navigator.userAgent")
        print(f"Current User-Agent: {ua}")
        assert "Headless" not in ua
        
        print("✅ Task 1 Verification SUCCESSFUL!")
    except Exception as e:
        print(f"❌ Verification failed: {e}")
    finally:
        await worker.close()

if __name__ == "__main__":
    asyncio.run(verify_task_1())
