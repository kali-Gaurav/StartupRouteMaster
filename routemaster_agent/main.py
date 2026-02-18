import sys
import os

# Add parent directory to path so 'routemaster_agent' module is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Also add current directory for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional
import asyncio
from prometheus_client import generate_latest

from scrapers.browser import BrowserManager
from scrapers.ntes_agent import NTESAgent
from scrapers.disha_agent import AskDishaAgent
from pipeline.processor import DataPipeline
from cache import cache
from monitoring.proxy_monitor import ProxyMonitor
from command_interface import CommandInterface
from ai.agent_state_manager import agent_state_manager
from scheduler import AutonomousScheduler

app = FastAPI(title="RouteMaster AI Agent")
_proxy_monitor: Optional[ProxyMonitor] = None

# Initialize AI components
command_interface = CommandInterface(app)
autonomous_scheduler = AutonomousScheduler()

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
async def unlock_route(request: RouteRequest):
    """
    1. Fetches Schedule + Live Status (NTES)
    2. Verifies Seat/Fare (Ask Disha)
    3. Returns enriched data for Frontend to display
    """
    browser_mgr = BrowserManager()
    browser, context = await browser_mgr.get_browser(headless=False, slow_mo=100)
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

        # persist to DB (wait for completion)
        await pipeline.update_database(schedule, live_status)

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
    browser, context = await browser_mgr.get_browser(headless=False, slow_mo=100)
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
from routemaster_agent.proxy import ProxyManager

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


@app.on_event('startup')
async def _rma_startup():
    """Start background monitors (proxy health) and periodic reliability job when the app starts."""
    global _proxy_monitor
    try:
        _proxy_monitor = ProxyMonitor(interval=int(os.getenv('RMA_PROXY_CHECK_INTERVAL', '300')), timeout=int(os.getenv('RMA_PROXY_CHECK_TIMEOUT', '5')), fail_threshold=float(os.getenv('RMA_PROXY_FAIL_THRESHOLD', '0.5')))
        _proxy_monitor.start()
    except Exception:
        _proxy_monitor = None

    # start hourly reliability scheduler (best-effort)
    try:
        from routemaster_agent.intelligence.reliability_scheduler import start_scheduler
        start_scheduler()
    except Exception:
        pass


@app.on_event('shutdown')
async def _rma_shutdown():
    global _proxy_monitor
    try:
        if _proxy_monitor:
            await _proxy_monitor.stop()
    except Exception:
        pass

    # stop reliability scheduler if running
    try:
        from routemaster_agent.intelligence.reliability_scheduler import stop_scheduler
        await stop_scheduler()
    except Exception:
        pass


@app.post('/api/admin/detect-changes')
async def detect_schedule_changes(payload: dict):
    """Fetch latest schedules for provided trains, run change-detection and log diffs.
    Body: {"train_numbers": [..]}
    """
    train_numbers = payload.get('train_numbers') or []
    if not train_numbers:
        return {"error": "no train_numbers provided"}

    browser_mgr = BrowserManager()
    browser, context = await browser_mgr.get_browser(headless=False, slow_mo=100)
    ntes = NTESAgent()
    results = []
    for tn in train_numbers:
        print(f"[{tn}] Processing...")
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


# --- Admin: reliability recompute ---------------------------------
@app.post('/api/admin/reliability/recompute')
async def admin_recompute_reliability(payload: dict):
    """Recompute reliability for a list of trains.

    Payload: {"trains": ["12345", "12951"]}
    If `trains` omitted or empty, returns a 400 error to avoid accidental full recompute.
    """
    trains = payload.get('trains') or []
    if not trains:
        return {"error": "no trains provided"}, 400

    from routemaster_agent.intelligence.reliability_scheduler import compute_reliability_for_train
    results = {}
    for tn in trains:
        try:
            score = compute_reliability_for_train(tn)
            results[tn] = {"score": score}
        except Exception as e:
            results[tn] = {"error": str(e)}
    return {"results": results}


@app.post('/api/admin/reliability/get')
async def get_train_reliabilities_endpoint(payload: dict):
    """Get reliability scores for a list of trains.

    Payload: {"trains": ["12345", "12951"]}
    Returns: {"12345": 0.85, "12951": 0.92}
    """
    trains = payload.get('trains') or []
    if not trains:
        return {"error": "no trains provided"}, 400

    from routemaster_agent.intelligence.train_reliability import get_train_reliabilities
    try:
        results = get_train_reliabilities(trains)
        return results
    except Exception as e:
        return {"error": str(e)}, 500


# Alerts API (for dashboard retrieval)
@app.get('/api/admin/rma-alerts')
async def list_rma_alerts(limit: int = 50, unresolved_only: bool = True):
    """Return recent RMA alerts for dashboard consumption."""
    from routemaster_agent.database.db import SessionLocal
    from routemaster_agent.database.models import Alert
    session = SessionLocal()
    try:
        q = session.query(Alert).order_by(Alert.created_at.desc())
        if unresolved_only:
            q = q.filter(Alert.resolved == False)
        rows = q.limit(limit).all()
        result = [
            {
                'id': r.id,
                'source': r.source,
                'train_number': r.train_number,
                'level': r.level,
                'message': r.message,
                'metadata': r.meta,
                'created_at': r.created_at.isoformat() if r.created_at else None,
                'resolved': r.resolved,
                'resolved_at': r.resolved_at.isoformat() if r.resolved_at else None
            }
            for r in rows
        ]
        return {'alerts': result}
    finally:
        session.close()


@app.get('/api/admin/proxy-health')
async def proxy_health(run_check: bool = True, timeout: int = 5):
    """Return configured proxies and optionally run live health checks.

    Query params:
    - run_check (bool): whether to perform active HTTP checks (default true)
    - timeout (int): per-proxy timeout seconds
    """
    pm = ProxyManager()
    if not pm.has_proxies():
        return {"enabled": False, "proxies": []}

    if not run_check:
        return {"enabled": True, "status": pm.get_status()}

    try:
        results = pm.health_check_all(timeout=timeout)
        # update status map
        for r in results:
            proxy_url = r.get('proxy')
            pm.set_status(proxy_url, ok=bool(r.get('ok')), latency=r.get('latency'), status_code=r.get('status_code'), error=r.get('error'))
    except Exception as e:
        return {"enabled": True, "error": str(e), "status": pm.get_status()}

    return {"enabled": True, "results": results, "status": pm.get_status()}


@app.get('/api/admin/proxy-metrics')
async def proxy_metrics(format: str = 'prometheus'):
    """Return proxy metrics in either 'prometheus' (text/plain) or 'json'.

    Metrics include per-proxy enabled (0/1), fail_count, success_count, last_checked, latency, ok (0/1).
    """
    from fastapi.responses import PlainTextResponse
    pm = ProxyManager()
    status = pm.get_status()
    aggregate = {
        'total_proxies': len(status),
        'enabled': sum(1 for s in status.values() if s.get('enabled')),
        'disabled': sum(1 for s in status.values() if not s.get('enabled')),
    }
    if format == 'json':
        return {'aggregate': aggregate, 'status': status}

    # prometheus exposition
    lines = []
    # gauges
    lines.append(f'rma_proxies_total {aggregate["total_proxies"]}')
    lines.append(f'rma_proxies_enabled {aggregate["enabled"]}')
    lines.append(f'rma_proxies_disabled {aggregate["disabled"]}')
    for proxy, st in status.items():
        name = proxy.replace('://', '_').replace('/', '_').replace(':', '_')
        enabled = 1 if st.get('enabled') else 0
        ok = 1 if st.get('ok') else 0
        fail_count = st.get('fail_count', 0) or 0
        success_count = st.get('success_count', 0) or 0
        latency = st.get('latency') or 0
        # expose simple metrics with proxy label
        lines.append(f'rma_proxy_enabled{{proxy="{proxy}"}} {enabled}')
        lines.append(f'rma_proxy_ok{{proxy="{proxy}"}} {ok}')
        lines.append(f'rma_proxy_fail_count{{proxy="{proxy}"}} {fail_count}')
        lines.append(f'rma_proxy_success_count{{proxy="{proxy}"}} {success_count}')
        lines.append(f'rma_proxy_latency_seconds{{proxy="{proxy}"}} {latency}')

    body = "\n".join(lines) + "\n"
    return PlainTextResponse(content=body, media_type='text/plain')


@app.get('/metrics')
async def metrics_endpoint():
    """Prometheus exposition endpoint for RouteMaster agent metrics."""
    data = generate_latest()
    return Response(content=data, media_type='text/plain; version=0.0.4')


@app.post('/api/admin/rma-alerts/{alert_id}/resolve')
async def resolve_rma_alert(alert_id: int):
    from routemaster_agent.database.db import SessionLocal
    from routemaster_agent.database.models import Alert
    from datetime import datetime
    session = SessionLocal()
    try:
        a = session.query(Alert).filter(Alert.id == alert_id).first()
        if not a:
            return {'error': 'not found'}
        a.resolved = True
        a.resolved_at = datetime.utcnow()
        session.commit()
        return {'ok': True, 'id': alert_id}
    finally:
        session.close()


@app.post("/api/batch-enrich-schedule")
async def batch_schedule(train_numbers: List[str]):
    """Backward-compatible simple batch endpoint (processes trains and waits for completion)."""
    results = []
    for tn in train_numbers:
        result = await _background_fetch_and_store(tn)
        results.append(result)

    return {"message": "Batch processing completed", "results": results}


async def _background_fetch_and_store(train_number: str):
    browser_mgr = BrowserManager()
    browser, context = await browser_mgr.get_browser(headless=False, slow_mo=100)
    page = await context.new_page()
    try:
        ntes = NTESAgent()
        pipeline = DataPipeline()
        print(f"[{train_number}] Fetching schedule...")
        schedule = await ntes.get_schedule(page, train_number)
        print(f"[{train_number}] Fetching live status...")
        live = await ntes.get_live_status(page, train_number)
        print(f"[{train_number}] Saving to database...")
        await pipeline.update_database(schedule, live)
        print(f"[{train_number}] Complete!")
        return {"train": train_number, "status": "success", "schedule": bool(schedule), "live": bool(live)}
    except Exception as e:
        print(f"[{train_number}] Error: {e}")
        return {"train": train_number, "status": "error", "error": str(e)}
    finally:
        await browser_mgr.close()


@app.on_event("startup")
async def startup_event():
    """Initialize AI components on startup."""
    await command_interface.initialize()
    await autonomous_scheduler.initialize()
    autonomous_scheduler.start()
    agent_state_manager.load_state_from_file()  # Load previous state


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    autonomous_scheduler.stop()
    await command_interface.shutdown()
    agent_state_manager.save_state_to_file()  # Save state for recovery


if __name__ == "__main__":
    import uvicorn
    import os
    
    host = os.getenv("RMA_HOST", "0.0.0.0")
    port = int(os.getenv("RMA_PORT", "8000"))
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )
