from utils.ticket_generator import generate_branded_ticket
import os

def verify_task_37():
    print("🧪 Verifying Task 37: E-Ticket Generator...")
    
    passengers = [
        {"fullName": "Gaurav Nagar", "age": 30, "gender": "M"},
        {"fullName": "Anjali Nagar", "age": 28, "gender": "F"}
    ]
    
    path = generate_branded_ticket(
        booking_id="TEST_B123",
        pnr="4256789012",
        train_no="12345",
        from_stn="NDLS",
        to_stn="BCT",
        travel_date="2026-03-10",
        passengers=passengers
    )
    
    print(f"Generated PDF path: {path}")
    assert os.path.exists(path)
    assert os.path.getsize(path) > 1000 # Should be at least a few KB
    
    print("✅ Task 37 Verification SUCCESSFUL!")

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.append(str(Path("backend").resolve()))
    verify_task_37()
