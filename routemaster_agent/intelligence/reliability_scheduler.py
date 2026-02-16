import os
import time
import requests
from typing import List, Optional
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from routemaster_agent.database.db import SessionLocal
from routemaster_agent.database.models import TrainMaster, LiveStatus, ScheduleChangeLog
from routemaster_agent.intelligence.train_reliability import compute_and_store
from routemaster_agent.metrics import (
    RMA_TRAIN_RELIABILITY_COMPUTATION_SECONDS,
    RMA_TRAIN_RELIABILITY_UPDATES_TOTAL,
)

# Config
PROMETHEUS_URL = os.getenv('RMA_PROMETHEUS_URL', 'http://localhost:9090')
RELIABILITY_WINDOW_HOURS = int(os.getenv('RMA_RELIABILITY_WINDOW_HOURS', '6'))
RELIABILITY_BATCH_SIZE = int(os.getenv('RMA_RELIABILITY_BATCH_SIZE', '0'))  # 0 = all trains


def _prometheus_query(expr: str) -> Optional[dict]:
    """Simple Prometheus HTTP API query (instant).
    Returns parsed JSON if available, else None. Best-effort (timeouts tolerated).
    """
    try:
        url = PROMETHEUS_URL.rstrip('/') + '/api/v1/query'
        r = requests.get(url, params={'query': expr}, timeout=5)
        r.raise_for_status()
        data = r.json()
        if data.get('status') == 'success':
            return data.get('data')
    except Exception:
        return None
    return None


def _get_avg_extraction_confidence(train_no: str, window_hours: int = RELIABILITY_WINDOW_HOURS) -> float:
    """Try Prometheus avg_over_time; fallback to default (1.0) if unavailable."""
    try:
        expr = f'avg_over_time(rma_extraction_confidence{{train_number="{train_no}"}}[{window_hours}h])'
        res = _prometheus_query(expr)
        if res and res.get('result'):
            # take first (should be single series)
            val = float(res['result'][0]['value'][1])
            return max(0.0, min(1.0, val))
    except Exception:
        pass
    # fallback default
    return 1.0


def _get_schedule_drift_score(train_no: str) -> float:
    """Compute a simple schedule-drift score from the latest ScheduleChangeLog entry for the train.
    score = min(1.0, (added + removed + changed) / max(1, db_count))
    """
    session = SessionLocal()
    try:
        row = session.query(ScheduleChangeLog).filter(ScheduleChangeLog.train_number == train_no).order_by(ScheduleChangeLog.detected_at.desc()).first()
        if not row:
            return 0.0
        diff = row.diff or {}
        added = len(diff.get('added_stations') or [])
        removed = len(diff.get('removed_stations') or [])
        changed = len(diff.get('changed_stations') or [])
        db_count = diff.get('db_count') or 1
        score = (added + removed + changed) / max(1, db_count)
        return max(0.0, min(1.0, score))
    finally:
        session.close()


def _get_delay_probability(train_no: str) -> float:
    """Simple heuristic: look up latest TrainLiveStatus.delay_minutes and map to probability.
    delay_minutes -> probability = min(1.0, delay_minutes / 60)
    If no data, return 0.0
    """
    session = SessionLocal()
    try:
        row = session.query(LiveStatus).filter(LiveStatus.train_number == train_no).first()
        if not row:
            return 0.0
        dm = row.delay_minutes or 0
        return max(0.0, min(1.0, float(dm) / 60.0))
    finally:
        session.close()


def compute_reliability_for_train(train_no: str, *, window_hours: int = RELIABILITY_WINDOW_HOURS) -> float:
    """Compute & store reliability for a single train (returns score)."""
    timer = RMA_TRAIN_RELIABILITY_COMPUTATION_SECONDS.labels(batch='hourly').time()
    start = time.time()
    try:
        avg_conf = _get_avg_extraction_confidence(train_no, window_hours=window_hours)
        sd = _get_schedule_drift_score(train_no)
        dp = _get_delay_probability(train_no)
        score = compute_and_store(train_no, avg_extraction_confidence=avg_conf, schedule_drift_score=sd, delay_probability=dp, window_minutes=window_hours * 60)
        try:
            RMA_TRAIN_RELIABILITY_UPDATES_TOTAL.labels(batch='hourly').inc()
        except Exception:
            pass
        return score
    finally:
        try:
            timer.__exit__(None, None, None)
        except Exception:
            pass


def _fetch_all_train_numbers(limit: int = 0) -> List[str]:
    session = SessionLocal()
    try:
        q = session.query(TrainMaster.train_number)
        if limit and limit > 0:
            q = q.limit(limit)
        rows = q.all()
        return [r[0] for r in rows]
    finally:
        session.close()


def run_hourly_reliability_job(batch_size: int = RELIABILITY_BATCH_SIZE) -> int:
    """Compute reliability for all trains (or top-N). Returns number of trains updated."""
    trains = _fetch_all_train_numbers(limit=batch_size or 0)
    count = 0
    for tn in trains:
        try:
            compute_reliability_for_train(tn)
            count += 1
        except Exception:
            # continue after logging in real system
            pass
    return count


# Scheduler helper to register job within FastAPI startup
_scheduler: Optional[AsyncIOScheduler] = None


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = AsyncIOScheduler()
    # run at minute 0 of every hour
    _scheduler.add_job(run_hourly_reliability_job, trigger=CronTrigger(minute=0), id='rma_reliability_hourly')

    # daily maintenance: cleanup selector registry backups (runs at 04:00 UTC)
    try:
        from routemaster_agent.intelligence import selector_registry
        _scheduler.add_job(selector_registry.cleanup_backups, trigger=CronTrigger(hour=4, minute=0), id='rma_selector_backup_cleanup')
    except Exception:
        pass

    # optional daily sanity recompute (disabled by default)
    try:
        if os.getenv('RMA_DAILY_RELIABILITY_RECOMPUTE', 'false').lower() in ('1','true','yes'):
            _scheduler.add_job(run_hourly_reliability_job, trigger=CronTrigger(hour=2, minute=0), id='rma_daily_reliability_recompute')
    except Exception:
        pass

    _scheduler.start()
    return _scheduler


async def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
