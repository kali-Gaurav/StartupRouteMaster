import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.append(str(Path("backend").resolve()))

# Set Windows Selector Loop Policy for stability
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from workers.irctc_worker import IRCTCWorker

async def run_diagnostics():
    print("🧠 Starting High-Intelligence Pipeline Diagnostics...")
    worker = IRCTCWorker("diag-123")
    
    steps = [
        ("🚀 Browser Launch", worker.start),
        ("🥷 Stealth Integrity", verify_stealth_node),
        ("🌐 IRCTC Connectivity", lambda: worker.page.goto("https://www.irctc.co.in/nget/train-search", wait_until="commit")),
        ("🔍 Input Field Visibility", verify_dom_node),
    ]
    
    for name, func in steps:
        try:
            print(f"Checking {name}...")
            await func() if asyncio.iscoroutinefunction(func) else func()
            print(f"✅ {name}: PASSED")
        except Exception as e:
            print(f"❌ {name}: FAILED | Error: {e}")
            break
            
    await worker.close()
    print("\n🏁 Diagnostics Complete.")

async def verify_stealth_node(worker=None):
    # This function is used inside the loop, we get worker from closure if needed
    pass 

async def verify_dom_node():
    # Logic to find a real field
    pass

# Refined Diagnostic script with real checks
async def main():
    worker = IRCTCWorker("diag-test")
    try:
        # Step 1: Launch
        await worker.start()
        
        # Step 2: Stealth Check
        is_webdriver = await worker.page.evaluate("navigator.webdriver")
        assert is_webdriver is False, "Stealth Failed: navigator.webdriver detected!"
        
        # Step 3: Navigation
        print("Navigating to IRCTC...")
        await worker.page.goto("https://www.irctc.co.in/nget/train-search", wait_until="domcontentloaded", timeout=60000)
        
        # Step 4: DOM Interaction
        print("Checking for Login Button...")
        login_btn = await worker.page.wait_for_selector("a.search_btn.loginText", timeout=15000)
        assert login_btn is not None, "DOM Failed: Login button not found!"
        
        print("✅ PIPELINE INTEGRITY VERIFIED: 100% Operational.")
        
    except Exception as e:
        print(f"❌ PIPELINE ERROR: {e}")
    finally:
        await worker.close()

if __name__ == "__main__":
    asyncio.run(main())
