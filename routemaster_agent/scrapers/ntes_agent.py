import asyncio
from playwright.async_api import Page
from datetime import datetime
import requests
from bs4 import BeautifulSoup

class NTESAgent:
    BASE_URL = "https://enquiry.indianrail.gov.in/mntes/"

    async def get_schedule(self, page: Page, train_no: str):
        from routemaster_agent.metrics import (
            RMA_EXTRACTION_ATTEMPTS_TOTAL,
            RMA_EXTRACTION_FAILURES_TOTAL,
            RMA_EXTRACTION_SUCCESS_TOTAL,
            RMA_EXTRACTION_DURATION_SECONDS,
            RMA_STATIONS_EXTRACTED_TOTAL,
            RMA_VALIDATION_FAILURES_TOTAL,
        )

        proxy_id = getattr(getattr(page, 'context', None), '_rma_proxy', 'direct') or 'direct'
        source_label = 'ntes_schedule'
        RMA_EXTRACTION_ATTEMPTS_TOTAL.labels(source=source_label, train_number=train_no, proxy_id=proxy_id).inc()
        timer = RMA_EXTRACTION_DURATION_SECONDS.labels(source=source_label, train_number=train_no, proxy_id=proxy_id).time()
        try:
            await page.goto(self.BASE_URL)
            await page.click("text=Train Schedule")

            # Type train number like a human (typeahead on site requires events)
            filled = False
            try:
                await page.wait_for_selector("input#trainNo, input[name='trainNo']", timeout=5000)
                selector = "input#trainNo" if await page.query_selector("input#trainNo") else "input[name='trainNo']"
                await page.click(selector)
                await page.type(selector, train_no, delay=120)
                filled = True
                # wait for typeahead suggestions and accept first if available
                try:
                    await page.wait_for_selector('.tt-menu', timeout=2500)
                    await page.keyboard.press('ArrowDown')
                    await page.keyboard.press('Enter')
                except Exception:
                    pass
            except Exception:
                try:
                    await page.fill("input#trainNo", train_no)
                    filled = True
                except Exception:
                    try:
                        await page.fill("input[name='trainNo']", train_no)
                        filled = True
                    except Exception:
                        filled = False

            # Ensure page JS handler receives the value (best-effort)
            try:
                await page.evaluate("(function(){ if(typeof showTrainSchedule==='function') showTrainSchedule('B'); })();")
            except Exception:
                pass

            # Click Get Schedule (button can be an input[type=button])
            try:
                await page.click("input[value='Get Schedule']")
            except Exception:
                try:
                    await page.click("input.custom-btn[name='help']")
                except Exception:
                    pass

            # Wait for schedule rows to appear (long timeout)
            await page.wait_for_selector("table.table-striped tbody tr", timeout=30000)

            # Extract Metadata (selector may vary)
            train_name = ""
            try:
                train_name = await page.inner_text("#trainNameElement")
            except Exception:
                train_name = ""

            rows = await page.query_selector_all("table.table-striped tbody tr")
            stations = []

            for row in rows:
                cols = await row.query_selector_all("td")
                if len(cols) > 3:
                    seq = None
                    try:
                        seq = (await cols[0].inner_text()).strip()
                    except Exception:
                        seq = None

                    stations.append({
                        "sequence": seq,
                        "station_code": (await cols[1].inner_text()).strip(),
                        "station_name": (await cols[2].inner_text()).strip(),
                        "day": (await cols[3].inner_text()).strip() if len(cols) > 3 else None,
                        "arrival": (await cols[4].inner_text()).strip() if len(cols) > 4 else None,
                        "departure": (await cols[5].inner_text()).strip() if len(cols) > 5 else None,
                        "halt": (await cols[6].inner_text()).strip() if len(cols) > 6 else None,
                        "distance": (await cols[7].inner_text()).strip() if len(cols) > 7 else None,
                        "platform": (await cols[8].inner_text()).strip() if len(cols) > 8 else None,
                    })

            # If no stations found via expected selector, try selector-adaptation heuristics
            if not stations:
                try:
                    from routemaster_agent.scrapers.selector_adapt import extract_table_heuristic
                    stations = await extract_table_heuristic(page)
                except Exception:
                    stations = []

            # fallback: server-side fetch + parse when Playwright doesn't find rows
            if not stations:
                try:
                    url = f"{self.BASE_URL}q?opt=TrainServiceSchedule&subOpt=show&trainNo={train_no}"
                    # use rotating proxy + UA for server-side fallback if configured
                    from routemaster_agent.proxy import ProxyManager, get_random_ua
                    pm = ProxyManager()
                    proxies = pm.get_requests_proxies() if pm.has_proxies() else None
                    headers = {"User-Agent": get_random_ua()}
                    r = requests.get(url, timeout=20, proxies=proxies, headers=headers)
                    if r.status_code == 200:
                        soup = BeautifulSoup(r.text, 'html.parser')
                        tbl = soup.select_one('table.table-striped')
                        if tbl:
                            for tr in tbl.select('tbody tr'):
                                tds = [td.get_text(strip=True) for td in tr.select('td')]
                                if len(tds) > 3:
                                    stations.append({
                                        'sequence': tds[0] if len(tds) > 0 else None,
                                        'station_code': tds[1] if len(tds) > 1 else None,
                                        'station_name': tds[2] if len(tds) > 2 else None,
                                        'day': tds[3] if len(tds) > 3 else None,
                                        'arrival': tds[4] if len(tds) > 4 else None,
                                        'departure': tds[5] if len(tds) > 5 else None,
                                        'halt': tds[6] if len(tds) > 6 else None,
                                        'distance': tds[7] if len(tds) > 7 else None,
                                        'platform': tds[8] if len(tds) > 8 else None,
                                    })
                except Exception:
                    pass
            # best-effort train-level metadata
            source = stations[0]['station_name'] if stations else None
            destination = stations[-1]['station_name'] if stations else None

            # days/type/total travel time may be available elsewhere on the page; attempt gentle reads
            days_of_run = []
            train_type = None
            total_time = None
            try:
                meta_text = await page.inner_text('body')
                # naive extraction - look for patterns like "Days: Mon,Tue"
                m = None
            except Exception:
                meta_text = ''

            # instrument: station count
            try:
                RMA_STATIONS_EXTRACTED_TOTAL.labels(source=source_label, train_number=train_no).inc(len(stations))
            except Exception:
                pass

            timer.__exit__(None, None, None)
            RMA_EXTRACTION_SUCCESS_TOTAL.labels(source=source_label, train_number=train_no, proxy_id=proxy_id).inc()

            return {
                "train_no": train_no,
                "name": train_name,
                "source": source,
                "destination": destination,
                "type": train_type,
                "days_of_run": days_of_run,
                "total_travel_time": total_time,
                "schedule": stations,
                "fetched_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            print(f"Error fetching schedule for {train_no}: {e}")
            try:
                timer.__exit__(None, None, None)
            except Exception:
                pass
            RMA_EXTRACTION_FAILURES_TOTAL.labels(source=source_label, train_number=train_no, proxy_id=proxy_id).inc()
            RMA_VALIDATION_FAILURES_TOTAL.labels(source=source_label, train_number=train_no).inc()
            return None

    async def get_live_status(self, page: Page, train_no: str):
        from routemaster_agent.metrics import (
            RMA_EXTRACTION_ATTEMPTS_TOTAL,
            RMA_EXTRACTION_FAILURES_TOTAL,
            RMA_EXTRACTION_SUCCESS_TOTAL,
            RMA_EXTRACTION_DURATION_SECONDS,
        )

        proxy_id = getattr(getattr(page, 'context', None), '_rma_proxy', 'direct') or 'direct'
        source_label = 'ntes_live'
        RMA_EXTRACTION_ATTEMPTS_TOTAL.labels(source=source_label, train_number=train_no, proxy_id=proxy_id).inc()
        timer = RMA_EXTRACTION_DURATION_SECONDS.labels(source=source_label, train_number=train_no, proxy_id=proxy_id).time()
        try:
            await page.goto(self.BASE_URL)
            await page.click("text=Spot Your Train")

            await page.fill("input[name='trainNo']", train_no)
            await page.click("button:has-text('Show Status')")

            await page.wait_for_selector(".trainStatusBlock", timeout=15000)

            current_stn = ""
            delay = ""
            try:
                current_stn = await page.inner_text(".currentStation")
            except Exception:
                current_stn = ""

            try:
                delay = await page.inner_text(".delayInfo")
            except Exception:
                delay = ""

            timer.__exit__(None, None, None)
            RMA_EXTRACTION_SUCCESS_TOTAL.labels(source=source_label, train_number=train_no, proxy_id=proxy_id).inc()

            return {
                "train_no": train_no,
                "current_station": current_stn,
                "delay": delay,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            print(f"NTES live-status error for {train_no}: {e}")
            try:
                timer.__exit__(None, None, None)
            except Exception:
                pass
            RMA_EXTRACTION_FAILURES_TOTAL.labels(source=source_label, train_number=train_no, proxy_id=proxy_id).inc()
            return None

    async def get_live_status(self, page: Page, train_no: str):
        try:
            await page.goto(self.BASE_URL)
            await page.click("text=Spot Your Train")

            await page.fill("input[name='trainNo']", train_no)
            await page.click("button:has-text('Show Status')")

            await page.wait_for_selector(".trainStatusBlock", timeout=15000)

            current_stn = ""
            delay = ""
            try:
                current_stn = await page.inner_text(".currentStation")
            except Exception:
                current_stn = ""

            try:
                delay = await page.inner_text(".delayInfo")
            except Exception:
                delay = ""

            return {
                "train_no": train_no,
                "current_station": current_stn,
                "delay": delay,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            print(f"NTES live-status error for {train_no}: {e}")
            return None