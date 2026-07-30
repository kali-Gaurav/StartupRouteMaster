import sys
import os
from database.session import SessionLocal
from database.models import AuditLog
from utils.audit_utils import log_audit

def verify_task_16():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 16 (AUDIT LOGS)")
    
    db = SessionLocal()
    entity_id = "TASK_16_VERIFY"
    
    # 1. Test Centralized Logging
    print("  Recording test audit entry...")
    log_audit(
        db, 
        entity_type="SYSTEM_TEST", 
        entity_id=entity_id, 
        action="VERIFY_INFRA", 
        performed_by="ADMIN_16",
        reason="Automated verification of Task 16."
    )
    
    # 2. Verify Persistence
    print("  Checking database for entry...")
    entry = db.query(AuditLog).filter(AuditLog.entity_id == entity_id).first()
    
    assert entry is not None
    assert entry.performed_by == "ADMIN_16"
    assert "Automated verification" in entry.reason
    print(f"    Persistence: OK (Log ID: {entry.id})")
    
    # 3. Cleanup
    db.delete(entry)
    db.commit()
    
    print("\n✅ TASK 16 FULLY VERIFIED: Centralized auditing correctly records admin actions.")

if __name__ == "__main__":
    verify_task_16()
