import logging
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from database.models import AuditLog

logger = logging.getLogger(__name__)

def log_audit(
    db: Session,
    entity_type: str,
    entity_id: str,
    action: str,
    old_value: str = None,
    new_value: str = None,
    performed_by: str = "SYSTEM",
    reason: str = None
):
    """
    Task 17: Audit Log for Status Changes.
    Records an immutable audit trail for financial and booking status changes.
    """
    try:
        log_entry = AuditLog(
            id=str(uuid.uuid4()),
            entity_type=entity_type,
            entity_id=str(entity_id),
            action=action,
            old_value=str(old_value) if old_value is not None else None,
            new_value=str(new_value) if new_value is not None else None,
            performed_by=performed_by,
            reason=reason,
            timestamp=datetime.utcnow()
        )
        db.add(log_entry)
        db.commit()
        logger.info(f"Audit Log: {entity_type} {entity_id} {action} by {performed_by}")
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")
        db.rollback()
