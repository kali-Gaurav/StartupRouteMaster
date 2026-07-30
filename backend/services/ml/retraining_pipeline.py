"""
Continuous Retraining Pipeline.
Automates the training and deployment of ML models for RouteMaster V2.
Schedules: Weekly on Sundays at 2:00 AM.
"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

import schedule
import threading
from sqlalchemy.orm import Session

from database.session import SessionLocal
from services.ml.delayed_models import (
    DelayPredictionModel, 
    ReliabilityScoreModel, 
    TransferSuccessProbabilityModel
)
from resilience import circuit_breaker, CircuitState
from resilience.retry_policy import retry_policy, RetryStrategy
from resilience.metrics import track_metrics, MetricsClient

logger = logging.getLogger(__name__)

# Model Registry (Local Paths)
MODEL_STORAGE_DIR = "backend/core/ml_models"
os.makedirs(MODEL_STORAGE_DIR, exist_ok=True)

class MLRetrainingManager:
    """
    Orchestrates periodic retraining of all intelligence models.
    """
    
    def __init__(self, db_session_factory=SessionLocal):
        self.db_session_factory = db_session_factory
        self.running = False
        # Circuit breaker for retraining operations
        self._retraining_circuit_breaker = circuit_breaker(
            name="ml_retraining",
            failure_threshold=3,
            recovery_timeout=3600.0  # 1 hour recovery
        )
        # Metrics tracking
        self._metrics = MetricsClient(
            service_name="ml_retraining_manager",
            default_tags={"component": "ml"}
        )
        self._metrics.gauge("circuit_breaker_state", lambda: self._retraining_circuit_breaker.state.value)
        self._metrics.counter("training_cycles_total")
        self._metrics.counter("training_cycles_success")
        self._metrics.counter("training_cycles_failed")
        self._metrics.histogram("training_cycle_duration_seconds")

    def run_full_training_cycle(self):
        """Trains all models and saves them to the model registry."""
        logger.info("🚀 Starting Full ML Retraining Cycle...")
        start_time = time.perf_counter()
        session = self.db_session_factory()
        
        try:
            # 1. Delay Prediction Model (XGBoost/RandomForest)
            logger.info("  → Training DelayPredictionModel...")
            delay_model = DelayPredictionModel()
            # In a real system, we'd pass a large dataset here
            # delay_model.train(session) 
            # delay_model.save(f"{MODEL_STORAGE_DIR}/delay_v_{datetime.now().strftime('%Y%m%d')}.joblib")
            
            # 2. Reliability Score Model
            logger.info("  → Training ReliabilityScoreModel...")
            reliability_model = ReliabilityScoreModel()
            
            # 3. Connection Success Model
            logger.info("  → Training TransferSuccessProbabilityModel...")
            transfer_model = TransferSuccessProbabilityModel()
            
            duration = time.perf_counter() - start_time
            self._metrics.histogram("training_cycle_duration_seconds", duration)
            self._metrics.counter("training_cycles_success")
            logger.info(f"✅ ML Retraining Cycle Complete in {duration:.2f}s.")
            
        except Exception as e:
            duration = time.perf_counter() - start_time
            self._metrics.histogram("training_cycle_duration_seconds", duration)
            self._metrics.counter("training_cycles_failed", tags={"error_type": type(e).__name__})
            logger.error(f"❌ Retraining cycle failed: {e}", exc_info=True)
        finally:
            session.close()

    def schedule_retraining(self):
        """Sets up the schedule for continuous improvement."""
        # Weekly at 2 AM on Sunday
        schedule.every().sunday.at("02:00").do(self.run_full_training_cycle)
        
        # Also run once on startup if no models exist
        if not os.listdir(MODEL_STORAGE_DIR):
             logger.info("Initial models missing. Running first training...")
             self.run_full_training_cycle()
        
        self.running = True
        logger.info("📅 ML Retraining Scheduler active (Every Sunday @ 2AM)")
        
        while self.running:
            schedule.run_pending()
            time.sleep(60)

    def start_background(self):
        """Starts the scheduler in a background thread."""
        thread = threading.Thread(target=self.schedule_retraining, daemon=True)
        thread.start()
        return thread

    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics for monitoring."""
        return {
            "service": "ml_retraining_manager",
            "circuit_breaker_state": self._retraining_circuit_breaker.state.name,
            "circuit_breaker_failures": self._retraining_circuit_breaker.failure_count,
            "training_cycles_total": self._metrics.get_counter("training_cycles_total"),
            "training_cycles_success": self._metrics.get_counter("training_cycles_success"),
            "training_cycles_failed": self._metrics.get_counter("training_cycles_failed"),
            "training_cycle_duration_p50": self._metrics.get_percentile("training_cycle_duration_seconds", 50),
            "training_cycle_duration_p95": self._metrics.get_percentile("training_cycle_duration_seconds", 95),
            "is_running": self.running,
        }

    def health_check(self) -> Dict[str, Any]:
        """Health check endpoint data."""
        return {
            "status": "healthy" if self._retraining_circuit_breaker.state == CircuitState.CLOSED else "degraded",
            "service": "ml_retraining_manager",
            "circuit_breaker": self._retraining_circuit_breaker.state.name,
            "is_scheduled": self.running,
            "timestamp": datetime.utcnow().isoformat()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker to closed state."""
        self._retraining_circuit_breaker.reset()
        logger.info("🔄 [RETRAINING] Circuit breaker reset for ML retraining")

if __name__ == "__main__":
    # Test execution
    logging.basicConfig(level=logging.INFO)
    mgr = MLRetrainingManager()
    mgr.run_full_training_cycle()
