"""Service to run periodic performance checks and push SLA metrics (RT-110).

This module runs a short synthetic benchmark (via the existing benchmark
script) in a subprocess, parses the JSON output and exports the key SLA
measurements to Prometheus (via `backend.utils.metrics`). The last result is
kept in-memory for the admin status endpoint.
"""
import json
import time
import shlex
import subprocess
from typing import Dict, Any, Optional
from pathlib import Path

from utils import metrics

# in-memory store for last check
_last_result: Optional[Dict[str, Any]] = None


def _parse_benchmark_stdout(stdout: str) -> Dict[str, Any]:
    """Parse JSON output produced by scripts/raptor_benchmark.py."""
    try:
        data = json.loads(stdout)
    except Exception:
        # not JSON — return minimal failure
        return {"success": False, "error": "invalid_output", "raw": stdout}
    return {"success": True, "result": data}


def _update_prometheus_from_result(result: Dict[str, Any]) -> None:
    """Update Prometheus gauges from benchmark result."""
    ts = int(time.time())
    metrics.SLA_LAST_CHECK_TIMESTAMP.set(ts)

    # Default: fail
    metrics.SLA_CHECK_STATUS.set(0)

    if not result or not result.get("success"):
        metrics.SLA_CHECK_ERROR_RATE.set(1.0)
        return

    payload = result["result"]

    # The benchmark returns `median_runtime_ms` and `p95_runtime_ms` for the run
    p50 = float(payload.get("median_runtime_ms", 0.0))
    p95 = float(payload.get("p95_runtime_ms", 0.0))

    # Error rate unknown from script — assume 0 if script succeeded
    err = float(payload.get("error_rate", 0.0)) if payload.get("error_rate") is not None else 0.0

    metrics.SLA_CHECK_P50_MS.set(p50)
    metrics.SLA_CHECK_P95_MS.set(p95)
    metrics.SLA_CHECK_ERROR_RATE.set(err)

    # Simple pass/fail: pass when p95 < 100ms and error_rate < 0.01 (configurable later)
    status = 1 if (p95 < 100.0 and err <= 0.01) else 0
    metrics.SLA_CHECK_STATUS.set(status)


def run_perf_check(
    stations: int = 200,
    route_length: int = 6,
    queries: int = 200,
    ml_enabled: bool = True,
    timeout_seconds: int = 300,
) -> Dict[str, Any]:
    """Run a short performance benchmark (synchronous).

    Runs the `scripts/raptor_benchmark.py` with the provided parameters and
    updates Prometheus metrics. Returns parsed result for API consumption.
    """
    global _last_result

    script = Path(__file__).resolve().parents[1] / "scripts" / "raptor_benchmark.py"
    if not script.exists():
        _last_result = {"success": False, "error": "benchmark_script_missing"}
        _update_prometheus_from_result(_last_result)
        return _last_result

    cmd = [
        "python",
        str(script),
        "--stations", str(stations),
        "--route-length", str(route_length),
        "--queries", str(queries)
    ]
    if ml_enabled:
        cmd.append("--ml-enabled")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        parsed = _parse_benchmark_stdout(stdout if stdout else stderr)
        _last_result = parsed
        # update Prometheus metrics
        _update_prometheus_from_result(parsed)
        return parsed

    except subprocess.TimeoutExpired as e:
        _last_result = {"success": False, "error": "timeout"}
        _update_prometheus_from_result(_last_result)
        return _last_result
    except Exception as e:
        _last_result = {"success": False, "error": str(e)}
        _update_prometheus_from_result(_last_result)
        return _last_result


def get_last_result() -> Optional[Dict[str, Any]]:
    return _last_result


__all__ = ["run_perf_check", "get_last_result"]
