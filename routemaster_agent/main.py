from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import asyncio

from routemaster_agent.scrapers.browser import BrowserManager
from routemaster_agent.scrapers.ntes_agent import NTESAgent
from routemaster_agent.scrapers.disha_agent import AskDishaAgent
from routemaster_agent.pipeline.processor import DataPipeline
from cache import cache

app = FastAPI(title="RouteMaster AI Agent")

class RouteRequest(BaseModel):
    train_number: str
    source_code: str
    dest_code: str
    travel_date: str  # "today", "tomorrow" or "DD-MM-YYYY"


class EnrichRequest(BaseModel):
    train_numbers: List[str]
    date: Optional[str] = "today"
    use_disha: Optional[bool] = True
    per_segment: Optional[bool] = False
    concurrency: Optional[int] = 5


@app.post("/api/unlock-route-details")
async def unlock_route(request: RouteRequest, background_tasks: BackgroundTasks):
    """
    1. Fetches Schedule + Live Status (NTES)
    2. Verifies Seat/Fare (Ask Disha)
    3. Returns enriched data for Frontend to display
    """
    browser_mgr = BrowserManager()
    browser, context = await browser_mgr.get_browser()
    page = await context.new_page()

    ntes = NTESAgent()
    disha = AskDishaAgent()
    pipeline = DataPipeline()

    try:
        # sequential use of the same Page for stability
        schedule = await ntes.get_schedule(page, request.train_number)
        live_status = await ntes.get_live_status(page, request.train_number)

        booking_info = await disha.verify_booking_details(
            page,
            request.train_number,
            request.source_code,
            request.dest_code,
            request.travel_date,
        )

        # persist DB asynchronously (do not block response)
        # pipeline.update_database is async -> schedule it with create_task
        background_tasks.add_task(asyncio.create_task, pipeline.update_database(schedule, live_status))

        return {
            "status": "success",
            "train_number": request.train_number,
            "schedule": schedule,
            "live_status": live_status,
            "verification": booking_info,
            "action": "redirect_to_irctc",
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

    finally:
        await browser_mgr.close()


@app.post("/api/enrich-trains")
async def enrich_trains(req: EnrichRequest, background_tasks: BackgroundTasks):
    """Enrich a list of trains: fetch schedule, live status, optional Disha verification,
    save JSON/CSV, and upsert DB. Returns aggregated cleaned results."""
    # check cache
    cache_key = f"enrich:{','.join(sorted(req.train_numbers))}:{req.date}:{req.use_disha}:{req.per_segment}"
    cached = cache.get(cache_key)
    if cached:
        return {"cached": True, "result": cached}

    browser_mgr = BrowserManager()
    browser, context = await browser_mgr.get_browser()
    ntes = NTESAgent()
    disha = AskDishaAgent()
    pipeline = DataPipeline()

    sem = asyncio.Semaphore(req.concurrency or 5)
    results = []

    async def _fetch_one(train_no: str):
        async with sem:
            page = await context.new_page()
            max_retries = 3
            backoff = 1
            for attempt in range(1, max_retries + 1):
                try:
                    schedule = await ntes.get_schedule(page, train_no)
                    live = await ntes.get_live_status(page, train_no)

                    verification = None
                    if req.use_disha and schedule:
                        # per-segment or full route
                        if req.per_segment and schedule.get('schedule'):
                            stations = schedule.get('schedule') or []
                            segs = []
                            for i in range(len(stations) - 1):
                                src = stations[i].get('station_code') or stations[i].get('station_name')
                                dst = stations[i+1].get('station_code') or stations[i+1].get('station_name')
                                segs.append((src, dst))
                            verification = await disha.verify_segments(page, train_no, segs, req.date)
                        else:
                            src = schedule.get('source') or (schedule.get('schedule') or [])[0].get('station_code')
                            dst = schedule.get('destination') or (schedule.get('schedule') or [])[-1].get('station_code')
                            verification = await disha.verify_booking_details(page, train_no, src, dst, req.date)

                    # persist per-train
                    await pipeline.update_database(schedule, live)

                    await page.close()
                    return {"train": train_no, "schedule": schedule, "live": live, "verification": verification, "ok": True}
                except Exception as e:
                    try:
                        await page.close()
                    except Exception:
                        pass
                    if attempt == max_retries:
                        return {"train": train_no, "error": str(e), "ok": False}
                    await asyncio.sleep(backoff)
                    backoff *= 2

    tasks = [asyncio.create_task(_fetch_one(tn)) for tn in req.train_numbers]
    gathered = await asyncio.gather(*tasks)

    # Save batch files
    schedules_list = [g.get('schedule') for g in gathered if g.get('schedule')]
    lives_list = [g.get('live') for g in gathered if g.get('live')]
    pipeline.save_batch_schedules(schedules_list)
    pipeline.save_batch_live(lives_list)

    # store in cache and return
    cache.set(cache_key, gathered)

    await browser_mgr.close()

    return {"cached": False, "results": gathered}


# --- Testing endpoint -------------------------------------------------
from routemaster_agent.testing.runner import TestRunner
import os

@app.post('/api/admin/run-rma-tests')
async def run_rma_tests(payload: dict):
    """Run QA test suite for RMA scraper. Body: {train_numbers, concurrency, strict}
    Returns aggregated summary and artifacts path.
    """
    train_numbers = payload.get('train_numbers') or ["11603", "12345", "12951", "15640"]
    concurrency = int(payload.get('concurrency', 3))
    strict = bool(payload.get('strict', True))

    tester = TestRunner(train_numbers=train_numbers, concurrency=concurrency, strict=strict)
    summary = await tester.run()
    return summary


@app.post('/api/admin/detect-changes')
async def detect_schedule_changes(payload: dict):
    """Fetch latest schedules for provided trains, run change-detection and log diffs.
    Body: {"train_numbers": [..]}
    """
    train_numbers = payload.get('train_numbers') or []
    if not train_numbers:
        return {"error": "no train_numbers provided"}

    browser_mgr = BrowserManager()
    browser, context = await browser_mgr.get_browser()
    ntes = NTESAgent()
    results = []
    for tn in train_numbers:
        page = await context.new_page()
        try:
            raw = await ntes.get_schedule(page, tn)
            if not raw:
                results.append({"train": tn, "error": "no schedule extracted"})
                await page.close()
                continue
            from routemaster_agent.pipeline.data_cleaner import clean_schedule
            from routemaster_agent.pipeline.change_detector import compare_schedule_to_db, log_change_if_any
            cleaned = clean_schedule(raw)
            diff = compare_schedule_to_db(cleaned)
            logged = log_change_if_any(cleaned)
            results.append({"train": tn, "diff": diff, "logged": logged})
        except Exception as e:
            results.append({"train": tn, "error": str(e)})
        finally:
            try:
                await page.close()
            except Exception:
                pass

    await browser_mgr.close()
    return {"results": results}


@app.post("/api/batch-enrich-schedule")
async def batch_schedule(train_numbers: List[str], background_tasks: BackgroundTasks):
    """Backward-compatible simple batch endpoint (keeps previous behavior)."""
    for tn in train_numbers:
        background_tasks.add_task(asyncio.create_task, _background_fetch_and_store(tn))

    return {"message": "Batch processing started"}


async def _background_fetch_and_store(train_number: str):
    browser_mgr = BrowserManager()
    browser, context = await browser_mgr.get_browser()
    page = await context.new_page()
    try:
        ntes = NTESAgent()
        pipeline = DataPipeline()
        schedule = await ntes.get_schedule(page, train_number)
        live = await ntes.get_live_status(page, train_number)
        await pipeline.update_database(schedule, live)
    finally:
        await browser_mgr.close()
