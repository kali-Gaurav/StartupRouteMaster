import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from database.models import Subscription, AuditLog

logger = logging.getLogger("reconciliation-service")

class ReconciliationService:
    """[Task 41.F] Automated Financial Reconciliation Service."""

    @staticmethod
    def audit_discrepancies(db: Session) -> Dict[str, Any]:
        """
        Cross-references Subscription current state with the AuditLog.
        Detects 'ghost' PRO status where AuditLog doesn't support the current tier.
        """
        subscriptions = db.query(Subscription).all()
        discrepancies = []
        
        for sub in subscriptions:
            # Check if any upgrade log exists for this subscription
            last_audit = db.query(AuditLog).filter(
                AuditLog.entity_id == sub.id,
                AuditLog.action == "TIER_UPGRADE"
            ).order_by(AuditLog.timestamp.desc()).first()
            
            if sub.plan_tier != "FREE" and not last_audit:
                discrepancies.append({
                    "user_id": sub.user_id,
                    "tier": sub.plan_tier,
                    "issue": "Tier mismatch: No corresponding AuditLog found."
                })
        
        return {"discrepancies_found": len(discrepancies), "details": discrepancies}

    @staticmethod
    def calculate_mrr(db: Session) -> float:
        """[Task 41.H] Aggregates Monthly Recurring Revenue from AuditLogs."""
        # Simplified: Sum of all upgrades in the last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        logs = db.query(AuditLog).filter(
            AuditLog.action == "TIER_UPGRADE",
            AuditLog.timestamp >= thirty_days_ago
        ).all()
        
        # This is a simplified MRR calculator based on upgrade frequency.
        # In a real app, integrate with Stripe/UPI settlement data.
        return len(logs) * 499.0 # Assuming flat PRO fee for example
