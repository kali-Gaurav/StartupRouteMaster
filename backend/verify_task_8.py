import sys
import os
import uuid
import asyncio
from datetime import datetime, date

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.session import SessionLocal
from database.models import BankTransaction, Booking, User, AuditLog
from services.reconciliation_service import ReconciliationService

def setup_mock_data(db):
    user_id = str(uuid.uuid4())
    user = User(id=user_id, email=f"reconcile_{user_id}@example.com", role="user")
    db.add(user)
    db.commit()

    # Generate unique base
    base_id = str(uuid.uuid4().int)[:6]
    utr_exact = f"11{base_id}1111"
    utr_fuzzy_book = f"A2{base_id}O111"
    utr_fuzzy_bank = f"A2{base_id}0111"
    utr_late = f"33{base_id}3333"
    utr_suspense = f"99{base_id}9999"

    # 1. Booking ready for EXACT match
    b_exact = Booking(id=str(uuid.uuid4()), user_id=user_id, amount_paid=100.0, utr_number=utr_exact, booking_status="pending", booking_details={})
    
    # 2. Booking ready for FUZZY match (Typo: 'O' instead of '0')
    b_fuzzy = Booking(id=str(uuid.uuid4()), user_id=user_id, amount_paid=200.0, utr_number=utr_fuzzy_book, booking_status="pending", booking_details={})
    
    # 3. Booking that was timed out, ready for AUTO-PROMOTION
    b_late = Booking(id=str(uuid.uuid4()), user_id=user_id, amount_paid=300.0, utr_number=utr_late, booking_status="cancelled", escrow_message="Session abandoned by user.", booking_details={})
    
    db.add_all([b_exact, b_fuzzy, b_late])
    db.commit()
    
    # Bank Transactions
    tx_exact = BankTransaction(id=str(uuid.uuid4()), utr=utr_exact, amount=100.0, status="PENDING")
    tx_fuzzy = BankTransaction(id=str(uuid.uuid4()), utr=utr_fuzzy_bank, amount=200.0, status="PENDING") # Contains '0' instead of 'O'
    tx_late = BankTransaction(id=str(uuid.uuid4()), utr=utr_late, amount=300.0, status="PENDING")
    tx_suspense = BankTransaction(id=str(uuid.uuid4()), utr=utr_suspense, amount=500.0, status="PENDING") # No matching booking
    
    db.add_all([tx_exact, tx_fuzzy, tx_late, tx_suspense])
    db.commit()
    
    return b_exact.id, b_fuzzy.id, b_late.id, tx_exact.id, tx_suspense.id

def verify_task_8():
    print("=== Verifying Task 8: Nightly Ledger Reconciliation ===")
    
    db = SessionLocal()
    service = ReconciliationService(db)
    
    try:
        b_exact_id, b_fuzzy_id, b_late_id, tx_exact_id, tx_suspense_id = setup_mock_data(db)
        
        # 1. Run Nightly Batch
        print("Running Nightly Batch (Tasks 8.2, 8.3, 8.4)...")
        results = service.reconcile_nightly_batch()
        print(f"Batch Results: {results}")
        
        assert results["reconciled"] == 3 # Exact, Fuzzy, and Late
        assert results["suspense"] == 1
        assert results["promoted"] == 1
        print("[OK] Batch matched exact, fuzzy, and auto-promoted late payments")
        print("[OK] Unmatched funds correctly sent to Suspense")
        
        # Verify Booking States
        db.expire_all() # Refresh session
        b_fuzzy = db.query(Booking).filter(Booking.id == b_fuzzy_id).first()
        b_late = db.query(Booking).filter(Booking.id == b_late_id).first()
        
        assert b_fuzzy.booking_status == "confirmed"
        assert b_late.booking_status == "confirmed"
        assert "Auto-promoted" in b_late.escrow_message

        # 2. Check Audit Logs (Task 8.7)
        print("Checking Immutable Audit Trail...")
        logs = db.query(AuditLog).filter(AuditLog.entity_id == b_fuzzy_id).all()
        assert len(logs) > 0
        assert any(log.action == "FUZZY_MATCH" for log in logs)
        print("[OK] Audit logs successfully recorded")

        # 3. Test P/L Generator (Task 8.5)
        print("Testing P/L Statement Generator...")
        pl = service.generate_pl_report(datetime.utcnow().date())
        print(f"P/L Report Data: {pl}")
        assert pl["reconciled_revenue"] >= 600.0 # 100 + 200 + 300
        assert pl["suspense_liability"] >= 500.0 # From our suspense transaction
        print(f"[OK] P/L Generated: Rev={pl['reconciled_revenue']}, Suspense={pl['suspense_liability']}")

        # 4. Test Rollback (Task 8.10)
        print("Testing Admin Rollback...")
        roll_res = service.rollback_transaction("admin_1", tx_exact_id, "Fraudulent user")
        assert roll_res["success"] is True
        
        db.expire_all()
        tx_rolled = db.query(BankTransaction).filter(BankTransaction.id == tx_exact_id).first()
        assert tx_rolled.status == "REVERSED"
        
        b_rolled = db.query(Booking).filter(Booking.id == b_exact_id).first()
        assert b_rolled.booking_status == "cancelled"
        print("[OK] Transaction and associated booking successfully reversed via Rollback")

        # 5. Test CSV Parsing (Task 8.8)
        print("Testing Multi-Format CSV Parser...")
        csv_data = "DATE,DESC,AMOUNT,REF\n10/10/23,UPI,450.00,111122223333"
        parsed = service.parse_bank_csv(csv_data)
        assert len(parsed) == 1
        assert parsed[0]["utr"] == "111122223333"
        assert parsed[0]["amount"] == 450.0
        print("[OK] CSV parsed successfully")

    finally:
        db.close()

    print("=== Task 8 Verification Complete ===")

if __name__ == "__main__":
    verify_task_8()
