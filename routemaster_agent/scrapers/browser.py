from playwright.async_api import async_playwright

class BrowserManager:
    async def get_browser(self, headless: bool = True, slow_mo: int = 0, user_agent: str | None = None):
        """Start Playwright and return (browser, context).
        Parameters:
        - headless: whether to run headless
        - slow_mo: milliseconds to slow down Playwright actions (useful for debugging)
        - user_agent: optional UA string override
        """
        self.playwright = await async_playwright().start()
        launch_args = {"headless": headless, "args": ["--no-sandbox", "--disable-setuid-sandbox"]}
        if slow_mo and isinstance(slow_mo, int) and slow_mo > 0:
            launch_args["slow_mo"] = slow_mo

        browser = await self.playwright.chromium.launch(**launch_args)
        ua = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        context = await browser.new_context(user_agent=ua)
        # increase default timeout for slow sites
        context.set_default_timeout(30000)
        return browser, context

    async def close(self):
        try:
            await self.playwright.stop()
        except Exception:
            pass