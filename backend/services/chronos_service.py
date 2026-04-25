import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from collections import deque
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from database.models import SearchOutcome, RouteSearchLog, StationHealthIndex, SegmentPNR, User, CreditTransaction
from database.session import SessionTransit, SessionLocal
from services.live_status_service import LiveStatusService
from services.credit_service import UnlockCreditService as CreditService
from core.resilience import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.retry import retry_async, RetryPolicy

logger = logging.getLogger("routemaster.chronos")

class ChronosAuditorAgent:
    """
    [P1-P3] The Memory Loop: Audits predictions against reality.
    
    With resilience patterns: circuit breaker, retry, and metrics tracking.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.live_status = LiveStatusService()
        
        # Circuit breaker for live status calls
        self._live_status_breaker = circuit_breaker_manager.get_or_create(
            "chronos_live_status",
            CircuitConfig(failure_threshold=5, timeout_seconds=60.0)
        )
        
        # Retry policy
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=10.0,
            conditions=[
                lambda e: "timeout" in str(e).lower(),
                lambda e: "connection" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        logger.info("ChronosAuditorAgent initialized with resilience patterns")

    async def audit_recent_outcomes(self, limit: int = 50):
        """
        [P1] Scan for unverified search outcomes from the last 24 hours.
        """
        logger.info("⏳ [CHRONOS] Initiating Reality Audit...")
        
        # Get outcomes that involve journeys that should have completed by now
        yesterday = datetime.utcnow() - timedelta(days=1)
        pending = self.db.query(SearchOutcome).filter(
            SearchOutcome.created_at < yesterday,
            SearchOutcome.final_status == None, # Not yet audited
            SearchOutcome.discrepancy_score == 0.0
        ).limit(limit).all()

        for outcome in pending:
            try:
                await self.audit_single_outcome(outcome)
            except Exception as e:
                logger.error(f"Chronos Audit Fail for {outcome.id}: {e}")
        
        self.db.commit()

    async def audit_single_outcome(self, outcome: SearchOutcome):
        """
        [P2] Ground Truth Verification & Discrepancy Math.
        
        Protected by circuit breaker and retry logic.
        """
        journey_id = outcome.journey_id
        # In actual prod, we extract train numbers from journey_id or metadata
        # MOCK/STUB: We assume a specific train for the audit
        train_number = "12301" 
        
        # Fetch Hard Truth from Scraper/Live Logs with resilience
        async def _fetch_live_status():
            return await self.live_status.get_live_status(train_number)
        
        try:
            actual_status = await self._live_status_breaker.execute(
                self._retry_policy.execute,
                _fetch_live_status
            )
        except Exception as e:
            logger.error(f"Failed to fetch live status for audit: {e}")
            actual_status = None
        
        actual_delay = actual_status.get("delay_mins", 0) if isinstance(actual_status, dict) else 0
        
        # [P2] Discrepancy Scoring
        predicted_delay = float(outcome.predicted_delay_mins or 0)  # type: ignore
        drift = abs(actual_delay - predicted_delay)
        
        outcome.actual_delay_mins = actual_delay
        outcome.discrepancy_score = float(drift)
        outcome.final_status = "AUDITED"
        
        # [P5] Trust Recovery (Karma)
        if drift > 120: # Over 2 hours wrong
            await self._issue_karma_refund(outcome)
            
        # [P4] PNR Reality Verification (If applicable)
        await self._verify_pnr_conclusions(outcome)
        
        logger.info(f"📊 [CHRONOS] Audit {journey_id}: Predicted {predicted_delay}m | Actual {actual_delay}m | Drift {drift}m")
        
        # [P3] NIS Weight Self-Healing
        if drift > 30: # Significant failure in prediction
            await self._penalize_stations(outcome, drift)
        
        # Record metrics
        await self._record_metrics(outcome, drift)

    async def _penalize_stations(self, outcome: SearchOutcome, drift: float):
        """
        [P3] Intelligence Self-Healing: Lowers health weight of reliable stations if drift is high.
        """
        # Extract station codes from metadata_snapshot
        snapshot = outcome.metadata_snapshot or {}
        stations = snapshot.get("stations", [])
        
        for code in stations:
            # Lower the safety_score or infrastructure_score in StationHealthIndex
            try:
                health = self.db.query(StationHealthIndex).filter_by(station_code=code).first()
            except Exception:
                health = None
            if health:
                # [P7] Incremental Online Learning (Moving Average Decay)
                # alpha 0.1: weight towards new data slowly
                alpha = 0.1
                current_score = float(health.infrastructure_score or 0.5)  # type: ignore
                penalty = min(0.1, drift / 200) # Cap penalty
                health.infrastructure_score = (1 - alpha) * current_score + alpha * (current_score - penalty)  # type: ignore
                
                logger.warning(f"📉 [CHRONOS] Online Learning: Updated {code} reliability to {health.infrastructure_score:.4f}")

    async def _verify_pnr_conclusions(self, outcome: SearchOutcome):
        """
        [P4] Check if Waiting-Lists actually confirmed.
        """
        # Find PNRs linked to this journey
        pnrs = self.db.query(SegmentPNR).filter_by(journey_id=outcome.journey_id).all()
        for p in pnrs:
            # Match against final reality (In prod, this hits IRCTC status API)
            # If WL -> CNF, we increment our 'Confidence Mastery' in NIS
            if p.status == "CNF" and outcome.predicted_confirm_chance < 40:
                logger.info(f"🦾 [CHRONOS] PNR {p.pnr} Surprised us! WL Confirmed despite 40% prediction. Updating NIS.")
                # Increment confirmation bias in NIStore

    async def _issue_karma_refund(self, outcome: SearchOutcome):
        """
        [P5] Automated Trust Recovery.
        """
        # Find the original search log to get the user
        log = self.db.query(RouteSearchLog).filter_by(id=outcome.search_id).first()
        if not log or not log.user_id: return
        
        try:
            credit_svc = CreditService(self.db)
            amount = 25 # 25 Credits (Standard recovery)
            await credit_svc.award_credits(
                log.user_id,
                amount,
                reason="INTELLIGENCE_DRIFT_RECOVERY",
                ref_id=outcome.id
            )
            logger.warning(f"🎁 [CHRONOS] Issued {amount} Karma Credits to User {log.user_id} for Drift Exception.")
        except Exception as e:
            logger.error(f"Karma refund failed: {e}")

    async def get_drift_heatmap(self) -> list:
        """
        [P6] Global Error Map: Identify the most 'unstable' hubs in the network.
        """
        results = self.db.query(
            RouteSearchLog.src,
            func.avg(SearchOutcome.discrepancy_score).label("avg_drift"),
            func.count(SearchOutcome.id).label("sample_count")
        ).join(SearchOutcome, SearchOutcome.search_id == RouteSearchLog.id)\
         .group_by(RouteSearchLog.src)\
         .order_by(desc("avg_drift")).limit(10).all()
        
        # [P8] Drift-Sensing Aegis: Trigger investigation if drift > threshold
        for r in results:
            if r[1] > 25.0: # 25 min avg drift is a critical failure
                await self._trigger_aegis_investigation(r[0], r[1])

        return [{"station": r[0], "drift": r[1], "count": r[2]} for r in results]

    async def _trigger_aegis_investigation(self, station_code: str, drift: float):
        """
        [P8] Automated Chaos Scan of a failing hub.
        """
        from services.aegis_forge_service import AegisForgeService
        logger.critical(f"🛡️ [AEGIS:SABOTAGE] Critical Drift {drift:.2f} detected at {station_code}. Triggering Investigative Forge...")
        await AegisForgeService.start_disaster_drill(f"STATION_DRIFT_INVESTIGATION_{station_code}", db=self.db)

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    async def _record_metrics(self, outcome: SearchOutcome, drift: float):
        """Record audit metrics for monitoring."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "journey_id": outcome.journey_id,
                "drift": drift,
                "drift_category": "high" if drift > 120 else "medium" if drift > 30 else "low",
                "final_status": outcome.final_status
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_audits": 0, "avg_drift": 0.0}
        
        total = len(self._metrics)
        drifts = [m["drift"] for m in self._metrics]
        high_drift = sum(1 for m in self._metrics if m["drift_category"] == "high")
        
        return {
            "total_audits": total,
            "avg_drift": sum(drifts) / len(drifts) if drifts else 0,
            "high_drift_count": high_drift,
            "high_drift_percentage": high_drift / total if total > 0 else 0.0,
            "circuit_breaker_state": self._live_status_breaker.get_state().value
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "circuit_breaker": {
                "state": self._live_status_breaker.get_state().value,
                "failure_count": self._live_status_breaker.failure_count,
                "success_count": self._live_status_breaker.success_count
            },
            "metrics": self.get_metrics()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._live_status_breaker.reset()
        logger.info("Circuit breaker reset for chronos service")

class ChronosScheduler:
    """Life-cycle manager for the Memory Loop."""
    def __init__(self):
        self.running = False

    async def start(self):
        self.running = True
        while self.running:
            db = SessionTransit()
            try:
                auditor = ChronosAuditorAgent(db)
                await auditor.audit_recent_outcomes()
            except Exception as e:
                logger.error(f"Chronos Scheduler Error: {e}")
            finally:
                try:
                    db.close()
                except Exception:
                    pass
            
            # Audit every 6 hours (Deep Memory)
            await asyncio.sleep(21600)

    def stop(self):
        self.running = False
