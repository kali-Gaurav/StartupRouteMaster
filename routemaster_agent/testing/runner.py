import asyncio
import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from routemaster_agent.scrapers.browser import BrowserManager
from routemaster_agent.scrapers.ntes_agent import NTESAgent
from routemaster_agent.pipeline.processor import DataPipeline
from routemaster_agent.pipeline.data_cleaner import clean_schedule
from routemaster_agent.database.db import SessionLocal
from routemaster_agent.database.models import TrainStation
from routemaster_agent.pipeline.change_detector import log_change_if_any

DEFAULT_OUTPUT = "test_output"
DEFAULT_LOG_DIR = "logs"


class ValidationError(Exception):
    pass


class TestRunner:
    def __init__(
        self,
        train_numbers: List[str],
        concurrency: int = 3,
        max_attempts: int = 5,
        strict: bool = True,
        save_artifacts: bool = True,
        output_root: str = DEFAULT_OUTPUT,
        log_dir: str = DEFAULT_LOG_DIR,
    ):
        self.train_numbers = train_numbers
        self.concurrency = concurrency
        self.max_attempts = max_attempts
        self.strict = strict
        self.save_artifacts = save_artifacts
        self.output_root = Path(output_root) / datetime.utcnow().strftime("%Y%m%d")
        self.log_dir = Path(log_dir)
        self._ensure_dirs()
        self.browser_mgr = BrowserManager()
        self.ntes = NTESAgent()
        self.pipeline = DataPipeline()

    def _ensure_dirs(self):
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    async def run(self) -> Dict[str, Any]:
        browser, context = await self.browser_mgr.get_browser()
        sem = asyncio.Semaphore(self.concurrency)
        tasks = [asyncio.create_task(self._run_one(train_no, context, sem)) for train_no in self.train_numbers]
        results = await asyncio.gather(*tasks)
        # save aggregated metrics
        metrics_file = self.log_dir / f"testing_metrics_{datetime.utcnow().strftime('%Y%m%d')}.json"
        with open(metrics_file, 'a', encoding='utf-8') as mf:
            for r in results:
                mf.write(json.dumps(r, default=str) + "\n")
        await self.browser_mgr.close()
        summary = {
            "total": len(results),
            "passed": sum(1 for r in results if r.get('validation_passed')),
            "failed": sum(1 for r in results if not r.get('validation_passed')),
            "artifacts_path": str(self.output_root),
            "results": results,
        }
        return summary

    async def _run_one(self, train_no: str, context, sem: asyncio.Semaphore) -> Dict[str, Any]:
        async with sem:
            attempt = 0
            selector_failures = 0
            start_ts = time.time()
            last_error = None
            for attempt in range(1, self.max_attempts + 1):
                page = await context.new_page()
                attempt_start = time.time()
                try:
                    # extract schedule
                    schedule = await self.ntes.get_schedule(page, train_no)

                    if not schedule or not schedule.get('schedule'):
                        raise ValidationError("No schedule rows extracted")

                    # cleaning and validation
                    cleaned = clean_schedule(schedule)
                    validation_errors = self._validate_schedule(cleaned)

                    # CSV parity check
                    stations_len = len(cleaned.get('schedule') or [])
                    if stations_len < 5:
                        validation_errors.append('Too few stations (<5)')

                    # DB upsert and verify row count
                    await self.pipeline.update_database(cleaned, None)
                    # run change-detection and log if differences exist
                    try:
                        change_diff = log_change_if_any(cleaned)
                    except Exception:
                        change_diff = None

                    db_count = self._db_station_count(train_no)
                    if db_count != stations_len:
                        validation_errors.append(f"DB row count mismatch: db={db_count} vs extracted={stations_len}")

                    extraction_time = time.time() - attempt_start

                    # if any validation errors - either retry or fail depending on strictness
                    if validation_errors:
                        last_error = {'attempt': attempt, 'errors': validation_errors}
                        if self.save_artifacts:
                            await self._save_artifacts(page, train_no, attempt, validation_errors)
                        if self.strict:
                            # retry if attempts remain
                            await page.close()
                            continue
                        else:
                            # soft-accept in non-strict mode
                            result = self._make_result(train_no, attempt, stations_len, True, extraction_time, selector_failures, validation_errors, change_diff=change_diff if 'change_diff' in locals() else None)
                            await page.close()
                            return result

                    # success
                    result = self._make_result(train_no, attempt, stations_len, True, extraction_time, selector_failures, [], change_diff=change_diff if 'change_diff' in locals() else None)
                    await page.close()
                    return result

                except Exception as e:
                    last_error = {'attempt': attempt, 'exception': str(e)}
                    # capture artifacts for debugging
                    try:
                        if self.save_artifacts:
                            await self._save_artifacts(page, train_no, attempt, [str(e)])
                    except Exception:
                        pass
                    try:
                        await page.close()
                    except Exception:
                        pass
                    # reset browser/context on failure to attempt self-heal
                    try:
                        await self.browser_mgr.close()
                        # on subsequent attempts try headful + slow_mo to avoid bot-detection and aid rendering
                        if attempt >= 2:
                            browser, context = await self.browser_mgr.get_browser(headless=False, slow_mo=50)
                        else:
                            browser, context = await self.browser_mgr.get_browser()
                    except Exception:
                        pass
                    if attempt == self.max_attempts:
                        break
                    await asyncio.sleep(1 * attempt)

            extraction_time = time.time() - start_ts
            # final failed result
            return self._make_result(train_no, attempt, 0, False, extraction_time, selector_failures, [last_error], change_diff=None)

    def _validate_schedule(self, schedule_obj: Dict[str, Any]) -> List[str]:
        errors = []
        # required keys
        required = ["train_no", "name", "schedule"]
        for k in required:
            if k not in schedule_obj:
                errors.append(f"Missing key: {k}")
        stations = schedule_obj.get('schedule') or []
        # sequence continuity
        seqs = [s.get('sequence') for s in stations]
        if None in seqs:
            errors.append('Null sequence numbers present')
        else:
            # try cast to ints where possible
            try:
                seqs_int = [int(x) for x in seqs]
                if sorted(seqs_int) != list(range(1, len(seqs_int) + 1)):
                    errors.append('Sequence gap found')
            except Exception:
                errors.append('Sequence values not integer')

        # time validation
        for s in stations:
            arr = s.get('arrival')
            dep = s.get('departure')
            # destination may have null arrival/departure rules already handled in cleaner
            if arr and dep:
                try:
                    ah, am = map(int, arr.split(':'))
                    dh, dm = map(int, dep.split(':'))
                    if ah > 23 or dh > 23 or am > 59 or dm > 59:
                        errors.append(f"Invalid time format: {arr} / {dep}")
                    if ah > dh and s.get('day') is None:
                        # arrival after departure on same day is suspicious unless day increment
                        errors.append(f"Arrival after departure for station {s.get('station_code')}")
                except Exception:
                    errors.append(f"Invalid time parse for station {s.get('station_code')}: {arr} / {dep}")
            # halt minutes
            halt = s.get('halt_minutes')
            if halt is not None:
                try:
                    if int(halt) < 0:
                        errors.append(f"Negative halt for {s.get('station_code')}")
                except Exception:
                    errors.append(f"Invalid halt value for {s.get('station_code')}: {halt}")

        # days_of_run validation
        dor = schedule_obj.get('days_of_run')
        if dor is None:
            errors.append('days_of_run missing')
        else:
            if not isinstance(dor, list):
                errors.append('days_of_run not an array')
            else:
                if any(not isinstance(x, str) or not x for x in dor):
                    errors.append('days_of_run contains invalid entries')

        return errors

    async def _save_artifacts(self, page, train_no: str, attempt: int, errors: List[str]):
        base = self.output_root / train_no
        base.mkdir(parents=True, exist_ok=True)
        # HTML snapshot
        html_path = base / f"attempt_{attempt}.html"
        content = await page.content()
        html_path.write_text(content, encoding='utf-8')
        # raw DOM (full dump)
        raw_dom = base / f"raw_dom.html"
        raw_dom.write_text(content, encoding='utf-8')
        # screenshot
        png_path = base / f"attempt_{attempt}.png"
        try:
            await page.screenshot(path=str(png_path), full_page=True)
        except Exception:
            pass
        # validation errors JSON
        err_path = base / f"validation_errors_attempt_{attempt}.json"
        err_path.write_text(json.dumps(errors, indent=2, default=str), encoding='utf-8')

    def _db_station_count(self, train_no: str) -> int:
        session = SessionLocal()
        try:
            return session.query(TrainStation).filter(TrainStation.train_number == train_no).count()
        finally:
            session.close()

    def _make_result(self, train_no, attempts_used, stations_extracted, validation_passed, extraction_time, selector_failures, errors, change_diff=None):
        return {
            'train_number': train_no,
            'attempts_used': attempts_used,
            'stations_extracted': stations_extracted,
            'validation_passed': validation_passed,
            'extraction_time_seconds': round(extraction_time, 2),
            'selector_failures': selector_failures,
            'errors': errors,
            'change_diff': change_diff,
            'artifacts_path': str(self.output_root / train_no) if self.save_artifacts else None,
        }
