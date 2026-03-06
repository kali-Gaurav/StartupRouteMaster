import asyncio
import sys
import os
import csv
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.append(str(Path("backend").resolve()))

from database.session import SessionLocal
from database.models import Booking, EscrowStatus, BookingStatus
from scripts.reconcile_ledger import reconcile

async def verify_task_25():
    print("🧪 Verifying Task 25: Nightly Ledger Reconciliation...")
    db = SessionLocal()
    
    test_utr = "TEST_UTR_9999"
    test_amount = 540.0
    
    try:
        # 1. Create mock booking
        print("Creating mock booking in UTR_SUBMITTED state...")
        # Delete if exists
        db.query(Booking).filter(Booking.utr_number == test_utr).delete()
        
        new_booking = Booking(
            id="test-recon-id",
            pnr_number="RECONPNR",
            user_id=None,
            travel_date=datetime.now().date(),
            booking_status=BookingStatus.PENDING.value,
            escrow_status=EscrowStatus.UTR_SUBMITTED,
            amount_paid=test_amount,
            utr_number=test_utr,
            upi_tx_id="TX_RECON_123",
            created_at=datetime.utcnow(),
            booking_details={"test": "data"} # Fix: added mandatory details
        )
        db.add(new_booking)
        db.commit()
        
        # 2. Create CSV
        csv_path = "test_recon.csv"
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "UTR", "Amount", "VPA"])
            writer.writerow([datetime.now().strftime("%Y-%m-%d"), test_utr, str(test_amount), "test@upi"])
            
        # 3. Run reconciliation
        print("Running reconciliation script...")
        reconcile(csv_path)
        
        # 4. Verify status change
        db.expire_all()
        updated_booking = db.query(Booking).filter(Booking.utr_number == test_utr).first()
        print(f"Final Status: {updated_booking.escrow_status.name}")
        assert updated_booking.escrow_status == EscrowStatus.VERIFIED
        
        print("✅ Task 25 Verification SUCCESSFUL!")
        
        # Cleanup
        db.delete(updated_booking)
        db.commit()
        if os.path.exists(csv_path): os.remove(csv_path)
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(verify_task_25())
