import sys
import os
from database.session import SessionLocal
from database.models import User, AuditLog
from utils.audit_utils import log_audit

def verify_task_17():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 17 (MULTI-ADMIN SUPPORT)")
    
    db = SessionLocal()
    
    # 1. Simulate Action by Admin A
    print("  Admin A performing action...")
    log_audit(db, "TEST", "T17_A", "ACTION_A", performed_by="admin_gaurav")
    
    # 2. Simulate Action by Admin B
    print("  Admin B performing action...")
    log_audit(db, "TEST", "T17_B", "ACTION_B", performed_by="admin_primary")
    
    # 3. Verify Differentiation
    print("  Verifying audit trail differentiation...")
    log_a = db.query(AuditLog).filter(AuditLog.entity_id == "T17_A").first()
    log_b = db.query(AuditLog).filter(AuditLog.entity_id == "T17_B").first()
    
    assert log_a.performed_by == "admin_gaurav"
    assert log_b.performed_by == "admin_primary"
    print(f"    Admin A correctly recorded: {log_a.performed_by}")
    print(f"    Admin B correctly recorded: {log_b.performed_by}")
    
    # 4. Cleanup
    db.delete(log_a); db.delete(log_b)
    db.commit()
    
    print("\n✅ TASK 17 FULLY VERIFIED: Multiple admins are tracked and audited independently.")

if __name__ == "__main__":
    verify_task_17()
