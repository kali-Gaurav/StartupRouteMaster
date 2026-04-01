"""
The Hardened NTES Scraper Client for RouteMaster V2.
Upgraded with Browser Context Pooling, Distributed Rate Limiting, and Auto-Recovery.
[Task 15: Alerting System & Task 9: Caching Layer Alignment]
"""
import asyncio
import logging
import time
import random
import re
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any

from playwright.async_api import Page

from ..config import config
from ..models import UnifiedLiveStatus
from utils.rate_limiter import RedisTokenBucket
from core.redis import async_redis_client
from services.scraper_sentinel import scraper_sentinel

logger = logging.getLogger("provider.ntes_scraper")

# --- Optimized Constants ---
NTES_RATE_LIMIT = 2.0  # Scrapers should be much slower than APIs
NTES_BURST_LIMIT = 5
NTES_LIMIT_KEY = "rate_limit:ntes_scraper"

class NtesScraperClient:
    """
    [Task 48.1 & 48.4] Hardened NTES Scraper powered by Sentinel.
    Uses identity rotation and bandwidth-optimized headless contexts.
    """
    def __init__(self):
        self.rate_limiter = RedisTokenBucket(async_redis_client)
        self.base_url = "https://enquiry.indianrail.gov.in/mntes/"
        self._max_retries = 2

    async def _check_rate_limit(self):
        """Ensures we don't bombard NTES."""
        allowed, _ = await self.rate_limiter.is_allowed(NTES_LIMIT_KEY, NTES_RATE_LIMIT, NTES_BURST_LIMIT)
        if not allowed:
            logger.warning("NTES Scraper Rate Limit Triggered. Throttling...")
            await asyncio.sleep(2)

    async def _optimize_bandwidth(self, page: Page):
        """[Task 48.5] Disable heavy assets (Images, CSS, Fonts) for speed."""
        async def block_assets(route):
            if route.request.resource_type in ["image", "font", "stylesheet"]:
                await route.abort()
            else:
                await route.continue_()
        await page.route("**/*", block_assets)

    def _format_date(self, target_date: date) -> str:
        """Formats date as DD-Mon-YYYY (e.g., 31-Mar-2026)."""
        return target_date.strftime("%d-%b-%Y")

    async def get_live_status(self, train_number: str, journey_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
        """
        [Task 48.1 & 48.5] Scrapes live train status with Sentinel protection.
        Supports specific journey dates by selecting the appropriate instance on NTES.
        """
        if journey_date is None:
            journey_date = date.today()

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
        start_time = time.time()
        
        try:
            page = await context.new_page()
            await self._optimize_bandwidth(page)
            
            # Stealth: defined in scraper_sentinel but reinforced here
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            # 2. Navigate to NTES
            await page.goto(self.base_url, timeout=30000, wait_until="domcontentloaded")
            
            # 3. Enter Train No
            input_selector = "input#trainNo, input[name='trainNo'], input#txtTrainNo"
            await page.wait_for_selector(input_selector, timeout=10000)
            
            # Human-like typing
            for char in train_number:
                await page.type(input_selector, char, delay=random.randint(50, 150))
            
            await asyncio.sleep(random.uniform(0.5, 1.0))
            await page.keyboard.press("Enter")
            
            # 4. Handle Date Selection (NTES often shows a list of dates if multiple instances exist)
            # Or it might go directly to the status page for 'Today'.
            
            date_selector = f"text='{self._format_date(journey_date)}'"
            try:
                # Wait for date selection if it appears
                await page.wait_for_selector(".date-list, .instance-list", timeout=3000)
                await page.click(f"div:has-text('{self._format_date(journey_date)}')", timeout=2000)
            except:
                # If not found, it might have auto-selected or we are on the wrong page
                pass

            # 5. Wait for results
            # NTES results are usually in a div with id 'divRes' or class 'trainStatusBlock'
            result_selectors = [".trainStatusBlock", ".running-status-table", "#divRes", ".live-status"]
            found = False
            for selector in result_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=10000)
                    found = True
                    break
                except:
                    continue
            
            if not found:
                logger.warning(f"NTES Scraper could not find results for {train_number} on {journey_date}")
                return None

            # 6. Wait for Results (Dynamic Container found in exploration)
            await page.wait_for_selector("#runningStatusContent, #divRes", timeout=20000)
            
            # 7. Refined Extraction [Task 48.12: Subagent Refined Selectors]
            # Based on 3-column w3-row layout: [Arr | Stn/PF | Dep]
            extracted_table = await page.evaluate('''() => {
                const results = [];
                const rows = Array.from(document.querySelectorAll("#runningStatusContent .w3-row, .station-row, .stn-row"));
                
                rows.forEach(row => {
                    const cols = Array.from(row.querySelectorAll(".w3-col, div[class*='col']"));
                    if (cols.length < 3) return;
                    
                    const stationCell = cols[1]; // Middle Column
                    const stationText = stationCell?.innerText.trim() || "";
                    // ID platform by orange label background or w3-tag
                    const pfLabel = stationCell?.querySelector(".w3-tag, span[style*='background-color: orange']")?.innerText.trim() || "N/A";
                    
                    results.push({
                        "arrival": cols[0]?.innerText.trim().replace(/\n/g, " "),
                        "station": stationText.replace(pfLabel, "").trim(),
                        "platform": pfLabel,
                        "departure": cols[2]?.innerText.trim().replace(/\n/g, " "),
                    });
                });
                return results;
            }''')

            # Determine "Current Station" from the summary bar (Elite identified)
            summary_bar = await page.get_attribute("div#runningStatusContent div.w3-indigo", "innerText") or ""
            current_pos = summary_bar.strip()
            
            latency = time.perf_counter() - start_time
            logger.info(f"NTES Scraper Success: {train_number} | {latency:.2f}s | {len(extracted_table)} stops")
            
            return {
                "train_no": train_number,
                "journey_date": journey_date.isoformat(),
                "current_station": current_pos,
                "delay_info": current_pos.split("at")[-1].strip() if "at" in current_pos else "N/A",
                "full_table": extracted_table,
                "scraped_at": datetime.utcnow().isoformat(),
                "latency": latency,
                "source": "ntes_scraper_distributed"
            }

        except Exception as e:
            logger.error(f"NTES Scraper Failure for {train_number}: {e}")
            return None
        finally:
            if page:
                try: await page.close()
                except: pass
            await scraper_sentinel.release_context(entry)

    async def get_live_station(self, station_code: str, within_hours: int = 2) -> Optional[Dict[str, Any]]:
        """
        [Task 48.8] Scrapes live station status from NTES.
        Fetches all trains arriving/departing from a station within X hours.
        """
        await self._check_rate_limit()
        
        try:
            entry = await scraper_sentinel.acquire_context()
        except Exception as e:
            logger.error(f"Scraper Sentinel Capacity Reached (LiveStation): {e}")
            return None

        context = entry["context"]
        page = None
        start_time = time.time()
        
        try:
            page = await context.new_page()
            await self._optimize_bandwidth(page)

            # 1. Navigate to Live Station (often accessible via a sidebar or direct link)
            # For simplicity, we'll navigate and look for the Live Station link
            await page.goto(self.base_url, timeout=30000, wait_until="domcontentloaded")
            
            # Open Sidebar if needed, or find Live Station link
            # Based on exploration: sidebar trigger is often visible
            try:
                await page.click(".sidebar-trigger, .menu-icon", timeout=2000)
                await page.click("text='Live Station'", timeout=2000)
            except:
                # Direct navigation if possible or search on page
                pass

            # 2. Enter Station Code
            input_selector = "input#stationCode, input[name='stationCode'], input#txtStation"
            await page.wait_for_selector(input_selector, timeout=10000)
            await page.fill(input_selector, station_code)
            
            # Select Hours
            hours_selector = "select[name='hours'], select#hours"
            if await page.query_selector(hours_selector):
                await page.select_option(hours_selector, value=str(within_hours))
            
            await page.keyboard.press("Enter")
            
            # 3. Wait for Results
            await page.wait_for_selector(".live-station-results, #divRes", timeout=15000)
            
            # 4. Extract
            extracted = await page.evaluate('''() => {
                const rows = Array.from(document.querySelectorAll("table tr")).filter(r => r.cells.length > 2);
                return rows.map(row => {
                    const cols = Array.from(row.querySelectorAll("td, th"));
                    return cols.map(c => c.innerText.trim());
                });
            }''')

            latency = time.time() - start_time
            logger.info(f"NTES Live Station Success: {station_code} | {latency:.2f}s")
            
            return {
                "station_code": station_code,
                "trains": extracted,
                "scraped_at": datetime.utcnow().isoformat(),
                "latency": latency
            }

        except Exception as e:
            logger.error(f"NTES Live Station Failure: {e}")
            return None
        finally:
            if page:
                try: await page.close()
                except: pass
            await scraper_sentinel.release_context(entry)

    async def close_playwright(self):
        """Proxy call to sentinel stop if needed."""
        await scraper_sentinel.stop()

# --- Transformation Function ---

def to_unified_live_status(raw_data: Dict[str, Any], train_number: str) -> Optional[UnifiedLiveStatus]:
    """
    Transforms the raw scraped data from NTES into the canonical UnifiedLiveStatus model.
    """
    if not raw_data:
        return None

    try:
        current_station = raw_data.get("current_station", "N/A")
        delay_info = raw_data.get("delay_info", "N/A")
        scraped_at_str = raw_data.get("scraped_at")
        scraped_at = datetime.fromisoformat(scraped_at_str) if scraped_at_str else datetime.utcnow()

        delay_minutes = 0
        running_status = "Unknown"

        delay_lower = delay_info.lower()
        if "on time" in delay_lower:
            running_status = "On Time"
        elif "delayed" in delay_lower or "late" in delay_lower:
            running_status = "Delayed"
            # Attempt to parse delay minutes
            match = re.search(r'(\d+)\s*(min|hour|hr)', delay_lower)
            if match:
                val = int(match.group(1))
                if "hour" in match.group(2) or "hr" in match.group(2):
                    val *= 60
                delay_minutes = val
        elif "cancelled" in delay_lower:
            running_status = "Cancelled"
        elif "not started" in delay_lower:
            running_status = "Not Started"
        
        # Additional logic for parsing current station if 'N/A' but found in delay_info
        if current_station == "N/A" and "at" in delay_lower:
            # Example: "Train is at Palakkad (PGT)"
            stn_match = re.search(r'at\s+([A-Za-z\s]+)', delay_info)
            if stn_match:
                current_station = stn_match.group(1).strip()

        return UnifiedLiveStatus(
            train_number=train_number,
            current_station_name=current_station if current_station != "N/A" else None,
            status_as_of=scraped_at,
            delay_minutes=delay_minutes,
            running_status=running_status,
            data_source="ntes_scraper",
            confidence_score=0.85
        )

    except Exception as e:
        logger.error(f"Error transforming NTES data for {train_number}: {e}")
        return None
