import asyncio
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from routemaster_agent.proxy import ProxyManager


class ProxyMonitor:
    def __init__(self, interval: int = 300, timeout: int = 5, fail_threshold: float = 0.5, log_dir: str = 'logs'):
        self.interval = interval
        self.timeout = timeout
        self.fail_threshold = fail_threshold
        self._task: Optional[asyncio.Task] = None
        self._stopped = False
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    async def _run_loop(self):
        pm = ProxyManager()
        while not self._stopped:
            if pm.has_proxies():
                try:
                    results = pm.health_check_all(timeout=self.timeout)
                    ts = datetime.utcnow().isoformat()
                    entry = {'timestamp': ts, 'results': results}
                    fpath = self.log_dir / f'proxy_health_{datetime.utcnow().strftime("%Y%m%d")}.json'
                    with open(fpath, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(entry, default=str) + "\n")

                    # assess failures
                    total = len(results)
                    failed = sum(1 for r in results if not r.get('ok'))
                    fail_rate = failed / total if total else 0.0
                    # update ProxyManager status per-proxy so manager can auto-disable when threshold exceeded
                    for r in results:
                        try:
                            proxy_url = r.get('proxy')
                            ok = bool(r.get('ok'))
                            latency = r.get('latency')
                            status_code = r.get('status_code')
                            error = r.get('error')
                            pm.set_status(proxy_url, ok=ok, latency=latency, status_code=status_code, error=error)
                        except Exception:
                            continue
                    if total and fail_rate >= self.fail_threshold:
                        # persist an alert to DB for operators
                        try:
                            from routemaster_agent.database.db import SessionLocal
                            from routemaster_agent.database.models import Alert
                            session = SessionLocal()
                            a = Alert(source='proxy_monitor', train_number=None, level='critical', message=f'Proxy failure rate high: {failed}/{total}', meta={'fail_rate': fail_rate, 'details': results, 'timestamp': ts})
                            session.add(a)
                            session.commit()
                        except Exception:
                            pass
                        finally:
                            try:
                                session.close()
                            except Exception:
                                pass
                except Exception:
                    pass
            await asyncio.sleep(self.interval)

    def start(self):
        if self._task is None:
            self._stopped = False
            loop = asyncio.get_event_loop()
            self._task = loop.create_task(self._run_loop())

    async def stop(self):
        self._stopped = True
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=2.0)
            except Exception:
                self._task.cancel()
            self._task = None
