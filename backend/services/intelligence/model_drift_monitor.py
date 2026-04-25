import logging
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session
from database.models import SearchAccuracyMetric, ModelDriftEvent

logger = logging.getLogger("intelligence.drift")

class ModelDriftMonitor:
    """
    [Group 4] Closed-Loop 'Drift' Watchdog.
    Monitors SearchAccuracyMetric for statistical performance degradation.
    """
    def __init__(self, db: Session):
        self.db = db
        self.ACCURACY_THRESHOLD = 0.85 # 85% Match rate required

    async def check_for_drift(self, window_hours: int = 24):
        """
        Calculates recent accuracy and logs drift if performance drops.
        """
        threshold_time = datetime.utcnow() - timedelta(hours=window_hours)
        
        # 1. Total Samples in window
        total = self.db.query(func.count(SearchAccuracyMetric.id)).filter(
            SearchAccuracyMetric.measured_at >= threshold_time
        ).scalar()

        if total < 50:
            logger.info("📡 [DRIFT] Insufficient samples for drift analysis.")
            return

        # 2. Match Count
        matches = self.db.query(func.count(SearchAccuracyMetric.id)).filter(
            SearchAccuracyMetric.measured_at >= threshold_time,
            SearchAccuracyMetric.is_match == True
        ).scalar()

        accuracy = matches / total
        logger.info(f"📊 [DRIFT] Current Search Accuracy: {accuracy:.1%}")

        # 3. Detect Drift
        if accuracy < self.ACCURACY_THRESHOLD:
            logger.warning(f"🚨 [DRIFT] Performance degradation detected! Accuracy: {accuracy:.1%}")
            
            event = ModelDriftEvent(
                model_name="AVAILABILITY_SCORER_V1",
                metric_type="SEARCH_ACCURACY",
                baseline_value=0.92, # Historical baseline
                current_value=accuracy,
                deviation=0.92 - accuracy,
                severity="CRITICAL" if accuracy < 0.70 else "WARNING"
            )
            self.db.add(event)
            self.db.commit()
            
            # Here we would trigger re-calibration logic or alert hooks
            await self._trigger_recalibration(event)

    async def _trigger_recalibration(self, event: ModelDriftEvent):
        """[Group 3] Autonomous Drift Correction."""
        logger.info(f"🔧 [DRIFT] Initiating autonomous re-calibration for {event.model_name}...")
        
        # Signal the RouteScorer to enter conservative mode
        from services.multi_layer_cache import multi_layer_cache
        await multi_layer_cache.set_raw("SCORER_CONSERVATIVE_MODE", "TRUE", ttl=3600)
        
        event.status = "RECALIBRATING"
        self.db.commit()

def get_drift_monitor(db: Session):
    return ModelDriftMonitor(db)
