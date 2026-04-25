import logging
import asyncio
import time
from typing import Dict, Any, Optional
from datetime import datetime
from database.session import SessionLocal
from services.finance.reconciliation_orchestrator import get_reconciliation_orchestrator
from services.recovery_service import smart_retry_hub
from resilience.circuit_breaker import circuit_breaker, CircuitState
from resilience.retry_policy import retry_policy, RetryStrategy
from resilience.metrics import track_metrics, MetricsClient

logger = logging.getLogger("finance.ingestion")

# Mock Event Queue for Project Sentinel S3
bank_event_queue = asyncio.Queue()

class IngestionWorker:
    """
    [Group 4] Event-Driven Bank Ingestion Worker.
    Decouples bank webhook processing from the API layer.
    Ensures that high-volume payment streams are processed reliably.
    """
    def __init__(self):
        self.is_running = False
        # Circuit breaker for bank event processing
        self._circuit_breaker = circuit_breaker(
            name="bank_event_processing",
            failure_threshold=5,
            recovery_timeout=60.0
        )
        # Retry policy for transient failures
        self._retry_policy = retry_policy(
            max_attempts=3,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            base_delay=1.0,
            max_delay=30.0
        )
        # Metrics tracking
        self._metrics = MetricsClient(
            service_name="finance_ingestion_worker",
            default_tags={"component": "ingestion"}
        )
        self._metrics.gauge("circuit_breaker_state", lambda: self._circuit_breaker.state.value)
        self._metrics.counter("events_processed_total")
        self._metrics.counter("events_failed_total")
        self._metrics.histogram("event_processing_duration_seconds")

    @circuit_breaker(name="bank_event_processing")
    @retry_policy(name="bank_event_processing")
    async def start(self):
        """Starts the ingestion consumer loop."""
        logger.info("🚀 [INGEST] Bank Ingestion Worker Online.")
        self.is_running = True
        
        while self.is_running:
            try:
                # 1. Fetch event from queue (Simulated Kafka/MQ)
                event = await bank_event_queue.get()
                
                # 2. Process via SmartRetryHub + Orchestrator
                await self._process_with_resilience(event)
                
                # Mark as processed
                bank_event_queue.task_done()
                
            except Exception as e:
                logger.error(f"Ingestion Loop Error: {e}")
                await asyncio.sleep(1)

    @track_metrics(service="finance_ingestion_worker", operation="process_event")
    async def _process_with_resilience(self, event: Dict[str, Any]):
        """Wraps the reconciliation logic in a smart-retry hub."""
        start_time = time.perf_counter()
        db = SessionLocal()
        try:
            orchestrator = get_reconciliation_orchestrator(db)
            
            # task_id derived from UTR for tracking
            task_id = f"recon_{event.get('utr')}"
            
            # Wrap execution to handle transient DB locks or provider issues
            await smart_retry_hub.execute_with_retry(
                task_id,
                orchestrator.process_bank_event,
                db,
                utr=event["utr"],
                amount=event["amount"],
                sender_info=event.get("sender_info", {})
            )
            
            duration = time.perf_counter() - start_time
            self._metrics.histogram("event_processing_duration_seconds", duration)
            self._metrics.counter("events_processed_total", tags={"status": "success"})
            logger.info(f"✅ [INGEST] Processed event for UTR {event.get('utr')} in {duration:.3f}s")
            
        except Exception as e:
            duration = time.perf_counter() - start_time
            self._metrics.histogram("event_processing_duration_seconds", duration)
            self._metrics.counter("events_failed_total", tags={"error_type": type(e).__name__})
            logger.error(f"Fail-point in resilient ingestion: {e}")
            raise
        finally:
            db.close()

    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics for monitoring."""
        return {
            "service": "finance_ingestion_worker",
            "circuit_breaker_state": self._circuit_breaker.state.name,
            "circuit_breaker_failures": self._circuit_breaker.failure_count,
            "events_processed": self._metrics.get_counter("events_processed_total"),
            "events_failed": self._metrics.get_counter("events_failed_total"),
            "processing_duration_p50": self._metrics.get_percentile("event_processing_duration_seconds", 50),
            "processing_duration_p95": self._metrics.get_percentile("event_processing_duration_seconds", 95),
        }

    def health_check(self) -> Dict[str, Any]:
        """Health check endpoint data."""
        return {
            "status": "healthy" if self._circuit_breaker.state == CircuitState.CLOSED else "degraded",
            "service": "finance_ingestion_worker",
            "circuit_breaker": self._circuit_breaker.state.name,
            "is_running": self.is_running,
            "queue_size": bank_event_queue.qsize(),
            "timestamp": datetime.utcnow().isoformat()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker to closed state."""
        self._circuit_breaker.reset()
        logger.info("🔄 [INGEST] Circuit breaker reset for bank event processing")

    async def push_event(self, utr: str, amount: float, sender_info: Dict[str, Any]):
        """Public bridge to push into the processing stream."""
        await bank_event_queue.put({
            "utr": utr,
            "amount": amount,
            "sender_info": sender_info
        })
        logger.info(f"📥 [INGEST] Event queued for UTR {utr}")

# Global singleton
ingestion_worker = IngestionWorker()
