import logging
import random
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from database.session import SessionLocal
from database.models import MerchantVPA

logger = logging.getLogger(__name__)

class MerchantVPAService:
    """
    Task 1: Multi-Merchant VPA Load Balancing.
    Rotates VPAs based on daily volume limits and health.
    """

    def get_next_vpa(self) -> Dict[str, Any]:
        """
        Rotates between active VPAs that haven't hit their daily limit.
        Weighted by remaining capacity.
        """
        db = SessionLocal()
        try:
            # Task 1.5: Daily Reset Check
            # (In a real prod environment, this would be a Cron, but we can do a lazy check here)
            self._check_and_reset_daily_volumes(db)

            available_vpas = db.query(MerchantVPA).filter(
                MerchantVPA.is_active == True,
                MerchantVPA.current_daily_volume < MerchantVPA.daily_limit
            ).all()

            if not available_vpas:
                logger.error("CRITICAL: All Merchant VPAs have hit their daily limits or are inactive!")
                # Fallback to the first one even if limit hit (emergency)
                first = db.query(MerchantVPA).first()
                return {"vpa": first.vpa, "name": first.name}

            # Weighted choice based on remaining quota
            # Higher remaining quota = higher chance of being selected
            weights = []
            for v in available_vpas:
                remaining = v.daily_limit - v.current_daily_volume
                weights.append(max(1.0, remaining)) # Ensure at least 1.0 weight

            selected = random.choices(available_vpas, weights=weights, k=1)[0]
            
            logger.info(f"Selected VPA: {selected.vpa} (Daily Volume: {selected.current_daily_volume}/{selected.daily_limit})")
            return {
                "vpa": selected.vpa,
                "name": selected.name
            }
        finally:
            db.close()

    def record_volume(self, vpa: str, amount: float):
        """
        Updates the current daily volume for a VPA when a booking is VERIFIED.
        Also records a snapshot for trend charting (Task 6.3).
        """
        db = SessionLocal()
        try:
            merchant = db.query(MerchantVPA).filter(MerchantVPA.vpa == vpa).first()
            if merchant:
                merchant.current_daily_volume += amount
                
                # Subtask 6.3: Record Volume Snapshot
                from database.models import MerchantVPAVolumeSnapshot
                snapshot = MerchantVPAVolumeSnapshot(
                    vpa=vpa,
                    volume=merchant.current_daily_volume
                )
                db.add(snapshot)
                
                db.commit()
                logger.info(f"Updated VPA {vpa} volume: +{amount} (New Total: {merchant.current_daily_volume})")
        except Exception as e:
            logger.error(f"Error recording VPA volume: {e}")
            db.rollback()
        finally:
            db.close()

    def get_vpa_history(self, vpa: str, limit: int = 24) -> List[Dict[str, Any]]:
        """
        Fetch historical volume snapshots for a specific VPA.
        """
        db = SessionLocal()
        try:
            from database.models import MerchantVPAVolumeSnapshot
            history = db.query(MerchantVPAVolumeSnapshot).filter(
                MerchantVPAVolumeSnapshot.vpa == vpa
            ).order_by(MerchantVPAVolumeSnapshot.timestamp.desc()).limit(limit).all()
            
            return [
                {"volume": h.volume, "timestamp": h.timestamp.isoformat()}
                for h in reversed(history)
            ]
        finally:
            db.close()

    def _check_and_reset_daily_volumes(self, db: Session):
        """
        Lazy reset: If last_reset_at is not today, reset all volumes.
        """
        today = date.today()
        # Find any merchant not reset today
        needs_reset = db.query(MerchantVPA).filter(
            MerchantVPA.last_reset_at < datetime.combine(today, datetime.min.time())
        ).first()

        if needs_reset:
            logger.info("New day detected. Resetting all Merchant VPA daily volumes.")
            db.query(MerchantVPA).update({
                MerchantVPA.current_daily_volume: 0.0,
                MerchantVPA.last_reset_at: datetime.utcnow()
            })
            db.commit()

merchant_vpa_service = MerchantVPAService()
