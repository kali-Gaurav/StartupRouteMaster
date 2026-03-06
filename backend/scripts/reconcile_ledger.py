import sys
import os
import csv
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.session import SessionLocal
from database.models import Booking, EscrowStatus

def reconcile(csv_path: str):
    """
    Matches Bank CSV UTRs with Database records.
    CSV Format expected: Date, UTR, Amount, VPA
    """
    print(f"🔍 Starting Reconciliation for: {csv_path}")
    db = SessionLocal()
    
    stats = {"matched": 0, "mismatch_amount": 0, "not_found": 0}
    
    try:
        with open(csv_path, mode='r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                utr = row['UTR'].strip()
                bank_amount = float(row['Amount'])
                
                # Find booking by UTR
                booking = db.query(Booking).filter(Booking.utr_number == utr).first()
                
                if booking:
                    if abs(booking.amount_paid - bank_amount) < 0.01:
                        print(f"✅ MATCH: UTR {utr} | Amount {bank_amount}")
                        # If it was only UTR_SUBMITTED, we can auto-verify it here if needed
                        if booking.escrow_status == EscrowStatus.UTR_SUBMITTED:
                            booking.escrow_status = EscrowStatus.VERIFIED
                            booking.escrow_message = "Verified via Bank Ledger Reconciliation."
                        stats["matched"] += 1
                    else:
                        print(f"⚠️ MISMATCH: UTR {utr} | Bank: {bank_amount} | DB: {booking.amount_paid}")
                        stats["mismatch_amount"] += 1
                else:
                    print(f"❌ NOT FOUND: UTR {utr} in Database.")
                    stats["not_found"] += 1
        
        db.commit()
        print(f"\n📈 Summary: {stats}")
        
    except Exception as e:
        print(f"🔥 Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    # Create dummy CSV for testing if it doesn't exist
    test_csv = "bank_statement_mock.csv"
    if not os.path.exists(test_csv):
        with open(test_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "UTR", "Amount", "VPA"])
            writer.writerow([datetime.now().strftime("%Y-%m-%d"), "123456789012", "540.00", "user@upi"])
    
    reconcile(test_csv)
