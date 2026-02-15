from playwright.async_api import async_playwright
from routemaster_agent.proxy import ProxyManager, get_random_ua
import os

class BrowserManager:
    async def get_browser(self, headless: bool = True, slow_mo: int = 0, user_agent: str | None = None):
        """Start Playwright and return (browser, context).
        Supports optional proxy and UA rotation via env vars:
        - RMA_USE_PROXY (true/false)
        - RMA_PROXY_LIST or RMA_PROXY_FILE
        - RMA_UA_LIST
        """
        pm = ProxyManager()
        use_proxy = os.getenv('RMA_USE_PROXY', 'false').lower() in ('1', 'true', 'yes')
        proxy_server = pm.get_next_proxy() if (use_proxy and pm.has_proxies()) else None

        self.playwright = await async_playwright().start()
        launch_args = {"headless": headless, "args": ["--no-sandbox", "--disable-setuid-sandbox"]}
        if slow_mo and isinstance(slow_mo, int) and slow_mo > 0:
            launch_args["slow_mo"] = slow_mo
        if proxy_server:
            launch_args["proxy"] = {"server": proxy_server}

        browser = await self.playwright.chromium.launch(**launch_args)
        ua = user_agent or get_random_ua()
        context = await browser.new_context(user_agent=ua)
        # attach metadata for instrumentation (proxy/ua used)
        try:
            context._rma_proxy = proxy_server
        except Exception:
            context._rma_proxy = None
        try:
            context._rma_ua = ua
        except Exception:
            context._rma_ua = None
        # increase default timeout for slow sites
        context.set_default_timeout(30000)
        return browser, context

    async def close(self):
        try:
            await self.playwright.stop()
        except Exception:
            pass