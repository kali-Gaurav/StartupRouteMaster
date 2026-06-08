import uvicorn
import asyncio
import json
import time
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from database.session import get_db
from core.infrastructure.system_monitor import system_monitor
from resilience import circuit_breaker, CircuitState
from resilience.retry_policy import retry_policy, RetryStrategy
from resilience.metrics import track_metrics, MetricsClient
from typing import Dict, Any

app = FastAPI(title="RouteMaster Analytics Microservice")

STREAM_NAME = "analytics:events"

# Service-level resilience components
_analytics_circuit_breaker = circuit_breaker(
    name="analytics_stream_processing",
    failure_threshold=10,
    recovery_timeout=120.0
)
_analytics_retry_policy = retry_policy(
    max_attempts=3,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    base_delay=0.5,
    max_delay=10.0
)
_analytics_metrics = MetricsClient(
    service_name="analytics_microservice",
    default_tags={"component": "analytics"}
)
_analytics_metrics.gauge("circuit_breaker_state", lambda: _analytics_circuit_breaker.state.value)
_analytics_metrics.counter("events_received_total")
_analytics_metrics.counter("events_processed_total")
_analytics_metrics.counter("events_failed_total")
_analytics_metrics.histogram("event_processing_duration_seconds")

async def process_event(event: dict):
    """Deep analytics processing (e.g., aggregation, anomaly search)."""
    etype = event.get("type", "unknown")
    logger.info(f"📊 Processing Analytics Event: {etype}")
    # Simulate DB persistence or ML aggregation
    await asyncio.sleep(0.05)
    return {"processed": etype, "status": "success"}

@track_metrics(service="analytics_microservice", operation="process_event")
@_analytics_circuit_breaker
@_analytics_retry_policy
async def process_event_with_resilience(event: dict):
    """Resilient event processing with metrics and circuit breaker."""
    start_time = time.perf_counter()
    try:
        result = await process_event(event)
        duration = time.perf_counter() - start_time
        _analytics_metrics.histogram("event_processing_duration_seconds", duration)
        _analytics_metrics.counter("events_processed_total", tags={"status": "success"})
        logger.info(f"✅ [ANALYTICS] Processed event {event.get('type')} in {duration:.3f}s")
        return result
    except Exception as e:
        duration = time.perf_counter() - start_time
        _analytics_metrics.histogram("event_processing_duration_seconds", duration)
        _analytics_metrics.counter("events_failed_total", tags={"error_type": type(e).__name__})
        logger.error(f"❌ [ANALYTICS] Failed to process event: {e}")
        raise 

async def analytics_worker():
    """
    Task 7.5: Redis-Streams Consumer (Message Queue).
    Asynchronously processes events produced by the Gateway.
    """
    from core.infrastructure.lifespan import get_redis
    redis = await get_redis()
    if not redis:
        logger.error("❌ Analytics Worker: Redis unavailable.")
        return

    # Create group if not exists
    try:
        await redis.xgroup_create(STREAM_NAME, "analytics_group", mkstream=True)
    except: pass

    logger.info("👷 Analytics Worker Started. Listening for events...")
    while True:
        try:
            # Read from stream
            messages = await redis.xreadgroup("analytics_group", "worker_1", {STREAM_NAME: ">"}, count=10, block=2000)
            for _, msgs in messages:
                for msg_id, data in messages:
                    event = json.loads(data[b"payload"])
                    _analytics_metrics.counter("events_received_total", tags={"type": event.get("type", "unknown")})
                    await process_event_with_resilience(event)
                    await redis.xack(STREAM_NAME, "analytics_group", msg_id)
        except Exception as e:
            logger.error(f"Analytics Worker Error: {e}")
            await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    # Task 7.6: Auto-Registration with Heartbeat
    from core.integration.discovery import ServiceRegistry
    from core.infrastructure.lifespan import get_redis
    redis = await get_redis()
    if redis:
        registry = ServiceRegistry(redis)
        async def heartbeat():
             while True:
                 await registry.register("analytics", "analytics-node-1", "127.0.0.1", 8004)
                 await asyncio.sleep(10)
        asyncio.create_task(heartbeat())
        asyncio.create_task(analytics_worker())
    
    print("🚀 Analytics Microservice, Worker & Heartbeat Online.")

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "analytics"}

@app.get("/metrics")
async def metrics():
    """Get service metrics for monitoring."""
    return {
        "service": "analytics_microservice",
        "circuit_breaker_state": _analytics_circuit_breaker.state.name,
        "circuit_breaker_failures": _analytics_circuit_breaker.failure_count,
        "events_received": _analytics_metrics.get_counter("events_received_total"),
        "events_processed": _analytics_metrics.get_counter("events_processed_total"),
        "events_failed": _analytics_metrics.get_counter("events_failed_total"),
        "processing_duration_p50": _analytics_metrics.get_percentile("event_processing_duration_seconds", 50),
        "processing_duration_p95": _analytics_metrics.get_percentile("event_processing_duration_seconds", 95),
    }

@app.post("/circuit-breaker/reset")
async def reset_circuit_breaker():
    """Reset the circuit breaker to closed state."""
    _analytics_circuit_breaker.reset()
    logger.info("🔄 [ANALYTICS] Circuit breaker reset")
    return {"status": "reset", "circuit_breaker_state": _analytics_circuit_breaker.state.name}

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("routemaster.analytics")
    uvicorn.run(app, host="0.0.0.0", port=8004)
