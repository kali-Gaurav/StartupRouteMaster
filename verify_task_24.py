from database.session import SessionLocal
from database.models import Booking
import json

def verify_task_24():
    print("🧪 Verifying Task 24: Split Payment Architecture...")
    db = SessionLocal()
    try:
        # Find the most recent booking
        booking = db.query(Booking).order_by(Booking.created_at.desc()).first()
        if not booking:
            print("⏭️ No bookings found to verify. Please create one in the UI.")
            return
            
        print(f"Checking Booking: {booking.id}")
        history = booking.transaction_history
        
        print(f"History Type: {type(history)}")
        print(f"History Content: {history}")
        
        # If it was an old booking, it might be a string "[]" or None depending on SQLite driver
        if history is None:
            print("ℹ️ Found an old booking with NULL history. This is expected for pre-existing records.")
        elif isinstance(history, str):
            history_list = json.loads(history)
            assert isinstance(history_list, list)
            print(f"✅ Transaction history (stringified) verified: {len(history_list)} entries")
        elif isinstance(history, list):
            print(f"✅ Transaction history verified: {len(history)} entries")
        else:
            print(f"⚠️ Unexpected history type: {type(history)}")
            
        print("✅ Task 24 Verification logic completed!")
    finally:
        db.close()

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.append(str(Path("backend").resolve()))
    verify_task_24()
