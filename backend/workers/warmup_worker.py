import asyncio
import logging
import random
import os
from playwright.async_api import async_playwright
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

async def run_warmup(user_id: str):
    """
    Task 4: Session Warm-up & Cookie Farming.
    Browses IRCTC to generate trusted cookies.
    """
    chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe"
    profile_path = f"backend/browser_profiles/user_{user_id}"
    os.makedirs(profile_path, exist_ok=True)
    
    ua = UserAgent(platforms='pc').random
    
    async with async_playwright() as p:
        logger.info(f"Starting warmup for user: {user_id}")
        
        context = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            executable_path=chrome_path if os.path.exists(chrome_path) else None,
            headless=True,
            user_agent=ua,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        try:
            # 1. Visit IRCTC
            logger.info("Warmup: Navigating to IRCTC...")
            await page.goto("https://www.irctc.co.in/nget/train-search", wait_until="commit", timeout=60000)
            
            # Take screenshot for diagnosis
            os.makedirs("logs/screenshots", exist_ok=True)
            await page.screenshot(path="logs/screenshots/warmup_debug.png")
            logger.info("Warmup: Screenshot captured.")
            
            # Wait for content
            await asyncio.sleep(10)
            await page.screenshot(path="logs/screenshots/warmup_after_wait.png")
            
            # 2. Random Human Actions
            # Scroll down and up
            await page.mouse.wheel(0, random.randint(400, 800))
            await asyncio.sleep(random.uniform(2, 5))
            await page.mouse.wheel(0, -random.randint(200, 400))
            
            # 3. Visit a secondary page (e.g., Contact Us)
            try:
                await page.click("a:has-text('CONTACT US')", timeout=5000)
                await asyncio.sleep(random.uniform(5, 10))
                logger.info("Warmup: Contact page visited.")
            except:
                pass
                
            # 4. Wait to satisfy Cloudflare tracking
            wait_time = random.randint(20, 40)
            logger.info(f"Warmup: Waiting for {wait_time}s to farm cookies...")
            await asyncio.sleep(wait_time)
            
            logger.info(f"Warmup complete for user: {user_id}")
            
        except Exception as e:
            logger.error(f"Warmup failed for {user_id}: {e}")
        finally:
            await context.close()

if __name__ == "__main__":
    asyncio.run(run_warmup("default_user"))
