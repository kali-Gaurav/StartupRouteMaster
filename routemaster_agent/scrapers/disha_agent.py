from playwright.async_api import Page
from datetime import datetime

class AskDishaAgent:
    DISHA_URL = "https://www.irctc.co.in/nget/train-search"

    async def verify_booking_details(self, page: Page, train_no: str, source: str, dest: str, date_str: str):
        from routemaster_agent.metrics import (
            RMA_EXTRACTION_ATTEMPTS_TOTAL,
            RMA_EXTRACTION_FAILURES_TOTAL,
            RMA_EXTRACTION_SUCCESS_TOTAL,
            RMA_EXTRACTION_DURATION_SECONDS,
        )

        proxy_id = getattr(getattr(page, 'context', None), '_rma_proxy', 'direct') or 'direct'
        source_label = 'askdisha'
        RMA_EXTRACTION_ATTEMPTS_TOTAL.labels(source=source_label, train_number=train_no, proxy_id=proxy_id).inc()
        timer = RMA_EXTRACTION_DURATION_SECONDS.labels(source=source_label, train_number=train_no, proxy_id=proxy_id).time()

        try:
            await page.goto(self.DISHA_URL)

            # open chatbot widget (selector may change on IRCTC site)
            await page.wait_for_selector("#disha-banner", timeout=10000)
            await page.click("#disha-banner")

            await page.wait_for_selector("input#disha-input", timeout=15000)

            query = f"Book ticket {source} to {dest} {date_str} on train number {train_no}"
            await page.fill("input#disha-input", query)
            await page.keyboard.press("Enter")

            await page.wait_for_selector(".disha-ticket-card", timeout=20000)

            fare = None
            avail = None
            try:
                fare = await page.inner_text(".fare-value")
            except Exception:
                fare = None
            try:
                avail = await page.inner_text(".availability-status")
            except Exception:
                avail = None

            timer.__exit__(None, None, None)
            RMA_EXTRACTION_SUCCESS_TOTAL.labels(source=source_label, train_number=train_no, proxy_id=proxy_id).inc()

            return {
                "train_no": train_no,
                "verified": True,
                "fare": fare,
                "availability": avail,
                "source_used": source,
                "dest_used": dest,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            print(f"Disha Verification Failed: {e}")
            try:
                timer.__exit__(None, None, None)
            except Exception:
                pass
            RMA_EXTRACTION_FAILURES_TOTAL.labels(source=source_label, train_number=train_no, proxy_id=proxy_id).inc()
            return {"verified": False, "error": str(e)}

    async def verify_segments(self, page: Page, train_no: str, segments: list, date_str: str):
        """Verify seat/fare for multiple source-destination segments.
        segments: list of (source_code, dest_code) tuples or dicts.
        Returns a list of verification results for each segment.
        """
        results = []
        for seg in segments:
            if isinstance(seg, dict):
                src = seg.get('source') or seg.get('from')
                dst = seg.get('dest') or seg.get('to')
            else:
                src, dst = seg
            try:
                # reuse the same page sequentially to avoid new widget state issues
                res = await self.verify_booking_details(page, train_no, src, dst, date_str)
                results.append({"source": src, "dest": dst, "result": res})
            except Exception as e:
                results.append({"source": src, "dest": dst, "error": str(e)})
        return results