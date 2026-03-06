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
                        if booking.escrow_status == EscrowStatus.UTR_SUBMITTED:
                            booking.escrow_status = EscrowStatus.VERIFIED
                            booking.escrow_message = "Verified via Bank Ledger Reconciliation."
                        stats["matched"] += 1
                    else:
                        print(f"⚠️ MISMATCH (Partial Payment): UTR {utr} | Bank: {bank_amount} | DB: {booking.amount_paid}")
                        stats["mismatch_amount"] += 1
                        # Handle Partial Payment (Gap 5)
                        if bank_amount > 0:
                            from database.models import RefundQueue
                            # Push the received amount to the refund queue because it didn't match the required amount
                            refund = RefundQueue(
                                booking_id=booking.id,
                                user_id=booking.user_id,
                                amount=bank_amount,
                                vpa=row.get('VPA', 'UNKNOWN'),
                                status="PENDING",
                                reason=f"Partial/Mismatch Payment: Required {booking.amount_paid}, Received {bank_amount}"
                            )
                            db.add(refund)
                            booking.escrow_status = EscrowStatus.FAILED
                            booking.escrow_message = f"Payment mismatch. Received ₹{bank_amount}. Refund initiated."
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
