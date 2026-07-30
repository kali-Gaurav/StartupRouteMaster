"""
Audit Utils - Task 16: Admin Action Audit Logs
Standardized utility for recording system and admin actions.
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from database.models import AuditLog

logger = logging.getLogger(__name__)

def log_audit(
    db: Session,
    entity_type: str,
    entity_id: str,
    action: str,
    performed_by: str,
    old_value: str = None,
    new_value: str = None,
    reason: str = None
):
    """
    [16.3] Standardized audit logging.
    Records actions like UTR_VERIFY, CONFIG_CHANGE, etc.
    """
    try:
        audit = AuditLog(
            entity_type=entity_type,
            entity_id=str(entity_id),
            action=action,
            performed_by=performed_by,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            timestamp=datetime.utcnow()
        )
        db.add(audit)
        db.commit()
        logger.info(f"Audit: {action} on {entity_type}:{entity_id} by {performed_by}")
    except Exception as e:
        logger.error(f"Failed to record audit log: {e}")
        db.rollback()
