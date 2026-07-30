import httpx
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional
from database.config import Config
from resilience import circuit_breaker, CircuitState
from resilience.retry_policy import retry_policy, RetryStrategy
from resilience.metrics import track_metrics, MetricsClient

logger = logging.getLogger("routemaster_client")

RMA_URL = Config.RMA_URL if hasattr(Config, 'RMA_URL') else 'http://routemaster_agent:8008'

# Module-level resilience components
_routemaster_circuit_breaker = circuit_breaker(
    name="routemaster_client",
    failure_threshold=5,
    recovery_timeout=60.0
)
_routemaster_retry_policy = retry_policy(
    max_attempts=3,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    base_delay=1.0,
    max_delay=30.0
)
_routemaster_metrics = MetricsClient(
    service_name="routemaster_client",
    default_tags={"component": "client"}
)
_routemaster_metrics.gauge("circuit_breaker_state", lambda: _routemaster_circuit_breaker.state.value)
_routemaster_metrics.counter("enrich_requests_total")
_routemaster_metrics.counter("enrich_requests_success")
_routemaster_metrics.counter("enrich_requests_failed")
_routemaster_metrics.counter("reliability_queries_total")
_routemaster_metrics.counter("reliability_queries_success")
_routemaster_metrics.counter("reliability_queries_failed")
_routemaster_metrics.histogram("enrich_request_duration_seconds")
_routemaster_metrics.histogram("reliability_query_duration_seconds")

@track_metrics(service="routemaster_client", operation="enrich_trains_remote")
@_routemaster_circuit_breaker
@_routemaster_retry_policy
async def enrich_trains_remote(train_numbers, date='today', use_disha=True, per_segment=False, concurrency=5):
    """
    Enrich trains data via remote RouteMaster agent.
    """
    start_time = time.perf_counter()
    payload = {
        'train_numbers': train_numbers,
        'date': date,
        'use_disha': use_disha,
        'per_segment': per_segment,
        'concurrency': concurrency
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{RMA_URL}/api/enrich-trains", json=payload)
            resp.raise_for_status()
            result = resp.json()
            
            duration = time.perf_counter() - start_time
            _routemaster_metrics.histogram("enrich_request_duration_seconds", duration)
            _routemaster_metrics.counter("enrich_requests_success", tags={"train_count": str(len(train_numbers))})
            logger.info(f"✅ [ROUTEMASTER] Enriched {len(train_numbers)} trains in {duration:.3f}s")
            return result
    except Exception as e:
        duration = time.perf_counter() - start_time
        _routemaster_metrics.histogram("enrich_request_duration_seconds", duration)
        _routemaster_metrics.counter("enrich_requests_failed", tags={"error_type": type(e).__name__})
        logger.error(f"❌ [ROUTEMASTER] Failed to enrich trains: {e}")
        raise


def get_train_reliabilities(train_ids: list) -> dict:
    """
    Read latest train reliability scores from `train_reliability_index` (shared DB).
    
    Returns a mapping train_number -> reliability_score (0.0-1.0).
    Fail-open behavior: missing/unavailable entries return 1.0 (no penalty).
    """
    start_time = time.perf_counter()
    if not train_ids:
        return {}

    try:
        # Query the shared DB table populated by `routemaster_agent`.
        from database import engine
        from sqlalchemy import text, bindparam

        stmt = text("""
        SELECT tr.train_number, tr.reliability_score
        FROM train_reliability_index tr
        JOIN (
            SELECT train_number, MAX(computed_at) AS m
            FROM train_reliability_index
            WHERE train_number IN :ids
            GROUP BY train_number
        ) sub ON sub.train_number = tr.train_number AND tr.computed_at = sub.m
        """).bindparams(bindparam("ids", expanding=True))

        with engine.connect() as conn:
            rows = conn.execute(stmt, {"ids": train_ids}).fetchall()
            result = {row[0]: row[1] for row in rows}

        # Return requested order, defaulting to neutral (1.0)
        reliability_map = {tid: result.get(tid, 1.0) for tid in train_ids}
        
        duration = time.perf_counter() - start_time
        _routemaster_metrics.histogram("reliability_query_duration_seconds", duration)
        _routemaster_metrics.counter("reliability_queries_success", tags={"train_count": str(len(train_ids))})
        logger.debug(f"🔍 [ROUTEMASTER] Queried reliability for {len(train_ids)} trains in {duration:.3f}s")
        
        return reliability_map
    except Exception as e:
        duration = time.perf_counter() - start_time
        _routemaster_metrics.histogram("reliability_query_duration_seconds", duration)
        _routemaster_metrics.counter("reliability_queries_failed", tags={"error_type": type(e).__name__})
        logger.error(f"❌ [ROUTEMASTER] Failed to query train reliabilities: {e}")
        # Fail-open for safety (agent data unavailable or table missing)
        return {tid: 1.0 for tid in train_ids}

def get_metrics() -> Dict[str, Any]:
    """Get service metrics for monitoring."""
    return {
        "service": "routemaster_client",
        "circuit_breaker_state": _routemaster_circuit_breaker.state.name,
        "circuit_breaker_failures": _routemaster_circuit_breaker.failure_count,
        "enrich_requests_total": _routemaster_metrics.get_counter("enrich_requests_total"),
        "enrich_requests_success": _routemaster_metrics.get_counter("enrich_requests_success"),
        "enrich_requests_failed": _routemaster_metrics.get_counter("enrich_requests_failed"),
        "reliability_queries_total": _routemaster_metrics.get_counter("reliability_queries_total"),
        "reliability_queries_success": _routemaster_metrics.get_counter("reliability_queries_success"),
        "reliability_queries_failed": _routemaster_metrics.get_counter("reliability_queries_failed"),
        "enrich_request_duration_p50": _routemaster_metrics.get_percentile("enrich_request_duration_seconds", 50),
        "enrich_request_duration_p95": _routemaster_metrics.get_percentile("enrich_request_duration_seconds", 95),
        "reliability_query_duration_p50": _routemaster_metrics.get_percentile("reliability_query_duration_seconds", 50),
        "reliability_query_duration_p95": _routemaster_metrics.get_percentile("reliability_query_duration_seconds", 95),
    }

def health_check() -> Dict[str, Any]:
    """Health check endpoint data."""
    return {
        "status": "healthy" if _routemaster_circuit_breaker.state == CircuitState.CLOSED else "degraded",
        "service": "routemaster_client",
        "circuit_breaker": _routemaster_circuit_breaker.state.name,
        "routemaster_url": RMA_URL,
        "timestamp": datetime.utcnow().isoformat()
    }

def reset_circuit_breaker():
    """Reset the circuit breaker to closed state."""
    _routemaster_circuit_breaker.reset()
    logger.info("🔄 [ROUTEMASTER] Circuit breaker reset for routemaster client")
