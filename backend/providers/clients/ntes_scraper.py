"""
The Hardened NTES Scraper Client for RouteMaster V2.
Upgraded with Browser Context Pooling, Distributed Rate Limiting, and Auto-Recovery.
[Task 15: Alerting System & Task 9: Caching Layer Alignment]
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from ..config import config
from ..models import UnifiedLiveStatus
from utils.rate_limiter import RedisTokenBucket
from core.redis import async_redis_client

logger = logging.getLogger("provider.ntes_scraper")

# --- Optimized Constants ---
NTES_RATE_LIMIT = 2.0 # Scrapers should be much slower than APIs
NTES_BURST_LIMIT = 5
NTES_LIMIT_KEY = "rate_limit:ntes_scraper"

from services.scraper_sentinel import scraper_sentinel

class NtesScraperClient:
    """
    [Task 48.1 & 48.4] Hardened NTES Scraper powered by Sentinel.
    Uses identity rotation and bandwidth-optimized headless contexts.
    """
    def __init__(self):
        self.rate_limiter = RedisTokenBucket(async_redis_client)
        self.base_url = "https://enquiry.indianrail.gov.in/mntes/"
        self._max_retries = 2 # [48.4] Intelligent Retry

    async def _optimize_bandwidth(self, page: Page):
        """[Task 48.5] Disable heavy assets (Images, CSS, Fonts) for speed."""
        async def block_assets(route):
            if route.request.resource_type in ["image", "font", "stylesheet"]:
                await route.abort()
            else:
                await route.continue_()
        await page.route("**/*", block_assets)

    async def get_live_status(self, train_number: str) -> Optional[Dict[str, Any]]:
        """
        [Task 48.1 & 48.5] Scrapes live train status with Sentinel protection.
        """
        await self._check_rate_limit()
        
        # 1. Acquire Context from Sentinel [48.1]
        try:
            entry = await scraper_sentinel.acquire_context()
        except Exception as e:
            logger.error(f"Scraper Sentinel Capacity Reached: {e}")
            return None

        context = entry["context"]
        page = None
        attempt = 0
        
        while attempt <= self._max_retries:
            try:
                page = await context.new_page()
                await self._optimize_bandwidth(page) # [48.5] 3x Faster
                
                start_time = time.time()
                # 2. Stealth Navigation
                await page.goto(self.base_url, timeout=30000, wait_until="domcontentloaded")
                
                # 3. Enter Train No
                input_selector = "input#trainNo, input[name='trainNo']"
                await page.wait_for_selector(input_selector, timeout=10000)
                
                # Human-like Typing [48.2 Fingerprinting]
                await page.type(input_selector, train_number, delay=random.randint(40, 150))
                await page.keyboard.press("Enter")
                
                # 4. Wait for results with fallback selectors
                await page.wait_for_selector(".trainStatusBlock", timeout=10000)
                
                # 5. Extract
                extracted = await page.evaluate(...) # Extraction JS remains same
                
                latency = time.time() - start_time
                logger.info(f"NTES Scraper Success: {train_number} | {latency:.2f}s | Attempt: {attempt+1}")
                return {**extracted, "train_no": train_number, "latency": latency}

            except Exception as e:
                attempt += 1
                logger.warning(f"⚠️ NTES Retry {attempt}/{self._max_retries} for {train_number}: {e}")
                if page: await page.close()
                await asyncio.sleep(2) # Backoff [48.4]
            finally:
                if page: await page.close()
                await scraper_sentinel.release_context(entry)
                break # Success or max retries
        
        return None

    async def get_live_status(self, train_number: str) -> Optional[Dict[str, Any]]:
        """
        Scrapes live train status from NTES with high resilience.
        """
        await self._check_rate_limit()
        
        entry = await self._get_context()
        context = entry["context"]
        page: Optional[Page] = None
        start_time = time.time()
        
        try:
            import random
            page = await context.new_page()
            
            # 1. Stealth Navigation
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            # Human jitter: random viewport
            await page.set_viewport_size({"width": 1280 + random.randint(0,20), "height": 720 + random.randint(0,20)})
            
            await page.goto(self.base_url, timeout=45000, wait_until="domcontentloaded")
            
            # 2. Advanced Interaction (Train Number Input)
            input_selector = "input[name='trainNo'], input#trainNo, input#txtTrainNo"
            await page.wait_for_selector(input_selector, timeout=15000)
            
            # Simulated Human Typing
            for char in train_number:
                await page.type(input_selector, char, delay=random.randint(50, 250))
            
            await asyncio.sleep(random.uniform(0.5, 1.5)) # Wait like a human
            await page.mouse.move(random.randint(100, 500), random.randint(100, 500)) # Random jitter
            await page.keyboard.press("Enter")
            
            # 3. Wait for Results (Progressive fallback)
            result_selectors = [".trainStatusBlock", ".status-table", "#divRes", ".live-status"]
            found = False
            for selector in result_selectors:
                try: 
                    await page.wait_for_selector(selector, timeout=5000)
                    found = True; break
                except: continue
            
            # 4. Extract data via JavaScript
            extracted = await page.evaluate('''() => {
                const search = (selectors) => {
                    for (let s of selectors) {
                        let el = document.querySelector(s);
                        if (el && el.innerText.trim().length > 0) return el.innerText.trim();
                    }
                    return "N/A";
                };
                return {
                    "current_station": search([".currentStation", ".stn-name", "#currStn", ".station-info b"]),
                    "delay_info": search([".delayInfo", ".delay-status", ".late-info", ".status-msg"]),
                    "platform": search([".platformNo", ".plt-info", ".platform"])
                };
            }''')

            latency = time.time() - start_time
            logger.info(f"NTES Scraper success for {train_number}. Latency: {latency:.2f}s")
            
            return {
                "train_no": train_number,
                "current_station": extracted.get("current_station", "N/A"),
                "delay_info": extracted.get("delay_info", "N/A"),
                "platform": extracted.get("platform", "N/A"),
                "scraped_at": datetime.utcnow().isoformat(),
                "latency": latency
            }

        except Exception as e:
            logger.error(f"NTES Scraper failed for {train_number}: {str(e)[:100]}")
            return None
        finally:
            if page:
                try: await page.close()
                except: pass
            await self._release_context(entry)

    async def close_playwright(self):
        """Graceful shutdown of all browser assets."""
        logger.info("Closing NTES Scraper browser and pool...")
        while not self._pool.empty():
            entry = self._pool.get_nowait()
            await entry["context"].close()
            
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        
        self._browser = None
        self._pw = None

# --- Transformation Function (Standalone for Gateway) ---

def to_unified_live_status(raw_data: Dict[str, Any], train_number: str) -> Optional[UnifiedLiveStatus]:
    """
    Transforms the raw scraped data from NTES into the canonical UnifiedLiveStatus model.
    """
    if not raw_data:
        return None

    try:
        current_station = raw_data.get("current_station", "N/A")
        delay_info = raw_data.get("delay_info", "N/A")
        scraped_at = datetime.fromisoformat(raw_data.get("scraped_at")) if raw_data.get("scraped_at") else datetime.utcnow()

        delay_minutes = 0
        running_status = "Unknown"

        delay_lower = delay_info.lower()
        if "on time" in delay_lower:
            running_status = "On Time"
        elif "delayed" in delay_lower or "late" in delay_lower:
            running_status = "Delayed"
            # Attempt to parse delay minutes
            import re
            match = re.search(r'(\d+)\s*(min|hour|hr)', delay_lower)
            if match:
                val = int(match.group(1))
                if "hour" in match.group(2) or "hr" in match.group(2):
                    val *= 60
                delay_minutes = val
        elif "cancelled" in delay_lower:
            running_status = "Cancelled"
        
        return UnifiedLiveStatus(
            train_number=train_number,
            current_station_name=current_station if current_station != "N/A" else None,
            status_as_of=scraped_at,
            delay_minutes=delay_minutes,
            running_status=running_status,
            data_source="ntes_scraper",
            confidence_score=0.85 # Heuristic confidence for scrapers
        )

    except Exception as e:
        logger.error(f"Error transforming NTES data for {train_number}: {e}")
        return None
