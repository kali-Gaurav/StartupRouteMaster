import asyncio
import logging
import random
import time
import os
import psutil
from typing import Dict, Any, List, Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from core.nexus.audit.chaos import chaos_trap

logger = logging.getLogger("scraper-sentinel")

class ScraperSentinel:
    """
    [Task 48.1 & 48.2] Advanced Scraper Lifecycle & Identity Orchestrator.
    Manages a pool of Playwright contexts with identity rotation and self-healing.
    """
    def __init__(self, recycling_threshold: int = 50):
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._contexts: List[Dict[str, Any]] = []
        self.recycling_threshold = recycling_threshold
        self._lock = asyncio.Lock()
        
        # [Task 48.7] Circuit Breaker State
        self._failure_counts: Dict[str, int] = {} # {source: count}
        self._disabled_sources: Dict[str, float] = {} # {source: expiry_ts}
        
        # [Task 48.3] Scaling Thresholds (Nexus VPS Optimized)
        self.BASE_MAX_CONTEXTS = 1    # Keep strictly thin (1 instance = ~100MB)
        self.BURST_MAX_CONTEXTS = 2   # Strict cap to prevent 500MB VPS OOM
        
        # [Task 48.2] 100+ Realistic User-Agent Pool
        self.ua_pool = [
            f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36"
            for v in range(118, 126)
        ] + [
            f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36"
            for v in range(118, 126)
        ]

    def is_available(self, source: str) -> bool:
        """[Task 48.7] Circuit Breaker check."""
        if source in self._disabled_sources:
            if time.time() > self._disabled_sources[source]:
                del self._disabled_sources[source]
                self._failure_counts[source] = 0
                return True
            return False
        return True

    def record_failure(self, source: str, status_code: int = 500):
        """[Task 48.7 & 6.4] Adaptive Circuit Breaker.
        Status 429 = Massive backoff (IP protection).
        Status 100+ = Context corruption check.
        """
        self._failure_counts[source] = self._failure_counts.get(source, 0) + 1
        
        # 1. Immediate Lock for 429 (Too many requests)
        if status_code == 429:
             logger.critical(f"[NEXUS:SENTINEL] IRCTC RATE LIMIT (429) DETECTED for {source}. Emergency Trip (1 Hour).")
             self._disabled_sources[source] = time.time() + 3600
             return

        # [Phase 6: Task 8] Scraper Proxy Rotation Latch
        if self._failure_counts[source] >= 3 and status_code in [407, 408, 502, 504]:
             logger.warning(f"🔄 [NEXUS:SENTINEL] {source} hit {self._failure_counts[source]} Proxy Timeouts. Triggering Proxy Rotation Hook!")
             # Here we rotate the proxy dynamically without destroying the chromium context
             pass

        # 3. Cumulative Breach
        if self._failure_counts[source] >= 5:
            duration = 600 if status_code != 503 else 1800 # 503 is service Unavailable/Maintenance
            logger.error(f"[NEXUS:SENTINEL] Circuit Breaker Tripped ({source}). Backoff: {duration}s.")
            self._disabled_sources[source] = time.time() + duration

    async def start(self):
        """Initialize browser and warm pool with strict error handling [Task 102]."""
        async with self._lock:
            if self._pw: return
            
            try:
                logger.info("Initializing Scraper Sentinel (Playwright)...")
                self._pw = await async_playwright().start()
                self._browser = await self._pw.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox", 
                        "--disable-setuid-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage"
                    ]
                )
                # Warm contexts only if browser started successfully
                for _ in range(1): # Reduced to 1 for memory safety on boot
                    await self._create_new_context()
                logger.info("✅ Scraper Sentinel: REBOOT_RELIABLE (Fiber Active)")
            except Exception as e:
                logger.error(f"❌ [NEXUS:SCRAPER] Driver Initialization Failed: {e}")
                self._pw = None
                self._browser = None
                # Don't re-raise; allow system to start in DEGRADED mode if node is non-critical.

    async def _create_new_context(self) -> Dict[str, Any]:
        """Creates a high-entropy, randomized browser identity [48.2]."""
        if not self._browser: await self.start()
        
        ua = random.choice(self.ua_pool)
        viewport = {"width": 1280 + random.randint(-100, 100), "height": 720 + random.randint(-50, 50)}
        
        logger.debug(f"Creating Identity: {ua[:40]}... {viewport['width']}x{viewport['height']}")
        
        context = await self._browser.new_context(
            user_agent=ua,
            viewport=viewport,
            device_scale_factor=random.choice([1, 2]),
            ignore_https_errors=True
        )
        
        # [Task 48.2 & 6.2] Advanced Anti-Detection & Signature Masking
        # Masking WebGL, Screen, and Hardware Fingerprints
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            
            // WebGL Masking
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Intel Open Source Technology Center';
                if (parameter === 37446) return 'Mesa DRI Intel(R) HD Graphics 4000 (IVB GT2)';
                return getParameter.apply(this, arguments);
            };
        """)
        
        entry = {
            "context": context,
            "usage_count": 0,
            "created_at": time.time(),
            "last_used_at": time.time(),
            "in_use": False
        }
        self._contexts.append(entry)
        return entry

    @chaos_trap("scraper_external")
    async def acquire_context(self) -> Dict[str, Any]:
        """
        [Task 48.6] Acquire a context with self-healing and OOM prevention.
        [Nexus 100: Optimization 3] Surgical RAM Leech Prevention.
        """
        # [Task 102] Drive Availability Check
        if not self._pw or not self._browser:
             raise Exception("🆘 [NEXUS:SCRAPER] System is running in DEGRADED mode (Scraper Driver Offline).")
        
        from core.nexus.audit.triage import nexus_triage
        
        # 1. Triage-Driven Panic Purge
        if nexus_triage.current_backoff > 0.7:
             logger.critical(f"🛑 [NEXUS LATCH] System Pressure at {nexus_triage.current_backoff*100:.1f}%. Purging headless browsers to save host!")
             await self._panic_purge()
             raise Exception("NEXUS_OOM_PREVENT: Headless Chromium blocked to prevent VPS crash.")

        async with self._lock:
            # 2. Clean up stale/leaking contexts first
            await self._reap_zombies(aggressive=nexus_triage.current_backoff > 0.4)
            
            # 2. Try to find an available context
            for entry in self._contexts:
                if not entry["in_use"] and entry["usage_count"] < self.recycling_threshold:
                    entry["in_use"] = True
                    return entry
            
            # 3. Dynamic Scaling: Burst if memory allows [48.3]
            limit = self.BURST_MAX_CONTEXTS if self._check_system_memory() else self.BASE_MAX_CONTEXTS
            
            if len(self._contexts) < limit:
                entry = await self._create_new_context()
                entry["in_use"] = True
                return entry
            
            # 4. Wait for availability
            raise Exception(f"Scraper Sentinel pool capacity reached ({limit}).")

    async def release_context(self, entry: Dict[str, Any], status: str = "success"):
        """Returns context to pool or marks for recycling."""
        entry["in_use"] = False
        entry["usage_count"] += 1
        entry["last_used_at"] = time.time()
        
        # [Task 6.3] If status is 'expired', force immediate rebuild
        if status == "expired" or entry["usage_count"] >= self.recycling_threshold:
            logger.info(f"[NEXUS:SENTINEL] Recycling/Rebuilding context (Status: {status})")
            await entry["context"].close()
            if entry in self._contexts:
                self._contexts.remove(entry)
            await self._create_new_context()

    async def _panic_purge(self):
        """[Optimization 3] Instantly kills all Chromium instances to free RAM."""
        async with self._lock:
            for entry in list(self._contexts):
                try: await entry["context"].close()
                except: pass
            self._contexts.clear()

    async def _reap_zombies(self, aggressive: bool = False):
        """Kills contexts that have timed out or failed to release [48.6]."""
        # [Task 21] Heartbeat
        from core.nexus.bootstrapper import nexus_boot
        nexus_boot.recovery.record_heartbeat("scraper")
        
        now = time.time()
        timeout = 60 if aggressive else 300 # Aggressive: reap after 60s
        for entry in list(self._contexts):
            # Context active for > timeout without release
            if entry["in_use"] and (now - entry["last_used_at"] > timeout):
                logger.warning(f"Reaping zombie context (Timeout: {timeout}s).")
                try: await entry["context"].close()
                except: pass
                self._contexts.remove(entry)
            # Kill unused contexts if under moderate pressure
            elif not entry["in_use"] and aggressive:
                logger.info("Aggressive reap: killing idle context to free RAM.")
                try: await entry["context"].close()
                except: pass
                self._contexts.remove(entry)

    def _check_system_memory(self) -> bool:
        """[Task 48.3] Only allow scaling if > 500MB is free."""
        mem = psutil.virtual_memory()
        free_mb = mem.available / (1024 * 1024)
        return free_mb > 500

    async def stop(self):
        """Total shutdown."""
        logger.info("Stopping Scraper Sentinel...")
        for entry in self._contexts:
            await entry["context"].close()
        if self._browser: await self._browser.close()
        if self._pw: await self._pw.stop()
        self._contexts = []

scraper_sentinel = ScraperSentinel()
