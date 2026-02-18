import os
import itertools
import random
from typing import List, Optional, Dict
import time
import requests

# instrumentation
from metrics import (
    RMA_PROXY_REQUESTS_TOTAL,
    RMA_PROXY_FAILURES_TOTAL,
    RMA_PROXY_DISABLED_TOTAL,
    RMA_PROXY_HEALTH_SCORE,
)

# Small user-agent list for rotation; can be overridden via RMA_UA_LIST env var
_DEFAULT_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
]


def _load_ua_list() -> List[str]:
    env = os.getenv("RMA_UA_LIST")
    if env:
        return [u.strip() for u in env.split(',') if u.strip()]
    return _DEFAULT_UAS


class ProxyManager:
    """Round-robin proxy manager with per-proxy health tracking.

    Proxies may be provided via `RMA_PROXY_LIST` (comma-separated) or `RMA_PROXY_FILE`.
    The manager keeps a status map per proxy and will skip disabled proxies when returning the next proxy.
    """
    def __init__(self, disable_failures: int = 3):
        self.disable_failures = int(os.getenv('RMA_PROXY_DISABLE_FAILURES', str(disable_failures)))
        self.proxies = self._load_proxies()
        # status: url -> {enabled, last_checked, ok, latency, status_code, error, fail_count, success_count}
        self.status = {p: {'enabled': True, 'last_checked': None, 'ok': None, 'latency': None, 'status_code': None, 'error': None, 'fail_count': 0, 'success_count': 0} for p in self.proxies}
        self._cycle = itertools.cycle(self.proxies) if self.proxies else None

    def _load_proxies(self) -> List[str]:
        env = os.getenv("RMA_PROXY_LIST")
        if env:
            return [p.strip() for p in env.split(',') if p.strip()]
        path = os.getenv("RMA_PROXY_FILE")
        if path and os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return [l.strip() for l in f if l.strip()]
        return []

    def has_proxies(self) -> bool:
        return bool(self.proxies)

    def _next_enabled(self) -> Optional[str]:
        if not self._cycle:
            return None
        # iterate up to len(proxies) times to find an enabled one
        for _ in range(len(self.proxies)):
            candidate = next(self._cycle)
            st = self.status.get(candidate, {})
            if st.get('enabled', True):
                return candidate
        return None

    def get_next_proxy(self) -> Optional[str]:
        return self._next_enabled()

    def get_requests_proxies(self, proxy_url: Optional[str] = None) -> Optional[Dict[str, str]]:
        url = proxy_url or self.get_next_proxy()
        if not url:
            return None
        return {"http": url, "https": url}

    def set_status(self, proxy_url: str, ok: bool, latency: float = None, status_code: int = None, error: str = None):
        if proxy_url not in self.status:
            # unknown proxy - add it
            self.status[proxy_url] = {'enabled': True, 'last_checked': None, 'ok': None, 'latency': None, 'status_code': None, 'error': None, 'fail_count': 0, 'success_count': 0}
            if proxy_url not in self.proxies:
                self.proxies.append(proxy_url)
                self._cycle = itertools.cycle(self.proxies)
        st = self.status[proxy_url]
        st['last_checked'] = __import__('datetime').datetime.utcnow().isoformat()
        st['ok'] = bool(ok)
        st['latency'] = latency
        st['status_code'] = status_code
        st['error'] = error
        if ok:
            st['success_count'] = st.get('success_count', 0) + 1
            st['fail_count'] = 0
        else:
            st['fail_count'] = st.get('fail_count', 0) + 1
            # auto-disable when fail_count exceeds threshold
            if st['fail_count'] >= self.disable_failures:
                st['enabled'] = False
                try:
                    RMA_PROXY_DISABLED_TOTAL.labels(proxy=proxy_url).inc()
                except Exception:
                    pass
        # update health score gauge
        try:
            succ = st.get('success_count', 0) or 0
            fail = st.get('fail_count', 0) or 0
            total = succ + fail
            score = (succ / total) if total else (1.0 if st.get('ok') else 0.0)
            RMA_PROXY_HEALTH_SCORE.labels(proxy=proxy_url).set(round(score, 2))
        except Exception:
            pass

    def disable_proxy(self, proxy_url: str):
        if proxy_url in self.status:
            self.status[proxy_url]['enabled'] = False

    def enable_proxy(self, proxy_url: str):
        if proxy_url in self.status:
            self.status[proxy_url]['enabled'] = True
            self.status[proxy_url]['fail_count'] = 0

    def get_status(self) -> Dict[str, Dict[str, object]]:
        return self.status

    def check_proxy(self, proxy_url: str, timeout: int = 5) -> Dict[str, object]:
        """Perform a lightweight health check for a single proxy by requesting a lightweight endpoint.

        Returns a dict with keys: proxy, ok (bool), status_code (int|None), latency (float|None), error (str|None)
        """
        proxies = self.get_requests_proxies(proxy_url)
        start = time.time()
        # record that we attempted a proxied request
        try:
            RMA_PROXY_REQUESTS_TOTAL.labels(proxy=proxy_url).inc()
        except Exception:
            pass
        try:
            # use httpbin for predictable response; fallback to google if blocked
            resp = requests.get("https://httpbin.org/get", proxies=proxies, timeout=timeout)
            latency = time.time() - start
            ok = resp.status_code >= 200 and resp.status_code < 400
            # record failures
            if not ok:
                try:
                    RMA_PROXY_FAILURES_TOTAL.labels(proxy=proxy_url).inc()
                except Exception:
                    pass
            return {"proxy": proxy_url, "ok": ok, "status_code": resp.status_code, "latency": round(latency, 2), "error": None}
        except Exception as e:
            latency = time.time() - start
            try:
                RMA_PROXY_FAILURES_TOTAL.labels(proxy=proxy_url).inc()
            except Exception:
                pass
            return {"proxy": proxy_url, "ok": False, "status_code": None, "latency": round(latency, 2), "error": str(e)}

    def health_check_all(self, timeout: int = 5) -> List[Dict[str, object]]:
        """Run health check for all configured proxies and return list of results."""
        results = []
        for p in list(self.proxies):
            results.append(self.check_proxy(p, timeout=timeout))
        return results


# UA helper
def get_random_ua() -> str:
    uas = _load_ua_list()
    return random.choice(uas)
