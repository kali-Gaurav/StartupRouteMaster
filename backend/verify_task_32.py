import sys
import os
import uuid

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.ticket_generator import generate_branded_ticket

def verify_task_32():
    print("=== Verifying Task 32: Branded PDF Ticket Engine ===")
    
    booking_id = str(uuid.uuid4())
    pnr = "4215678901"
    train_no = "12626"
    from_stn = "New Delhi (NDLS)"
    to_stn = "Bengaluru (SBC)"
    travel_date = "2026-03-15"
    passengers = [
        {"name": "Gaurav Nagar", "age": 28, "gender": "M", "coach": "A1", "berth": "22"},
        {"name": "Ankit Kumar", "age": 25, "gender": "M", "coach": "A1", "berth": "23"}
    ]
    
    # 1. Test Standard Ticket Generation
    print("Generating standard branded ticket...")
    file_path = generate_branded_ticket(
        booking_id=booking_id,
        pnr=pnr,
        train_no=train_no,
        from_stn=from_stn,
        to_stn=to_stn,
        travel_date=travel_date,
        passengers=passengers
    )
    
    assert os.path.exists(file_path)
    assert os.path.getsize(file_path) > 1000 # Should be a valid PDF
    print(f"[OK] Ticket generated at: {file_path}")

    # 2. Test Password Protected Ticket
    print("Generating password-protected ticket...")
    pw_booking_id = str(uuid.uuid4())
    pw_file_path = generate_branded_ticket(
        booking_id=pw_booking_id,
        pnr=pnr,
        train_no=train_no,
        from_stn=from_stn,
        to_stn=to_stn,
        travel_date=travel_date,
        passengers=passengers,
        password="TESTPASSWORD"
    )
    
    assert os.path.exists(pw_file_path)
    print(f"[OK] Password protected ticket generated at: {pw_file_path}")

    # Clean up (optional, keeping for user to see)
    # os.remove(file_path)
    # os.remove(pw_file_path)

    print("=== Task 32 Verification Complete ===")

if __name__ == "__main__":
    verify_task_32()
