import sys
from pathlib import Path
sys.path.append(str(Path("backend").resolve()))

from utils.payments import generate_upi_uri
import urllib.parse

def verify_task_1():
    print("🧪 Verifying Task 1: Dynamic UPI URI Generator...")
    
    # Test case 1: Standard
    uri, tx_id = generate_upi_uri("gaurav@upi", "Gaurav Nagar", 540.0)
    print(f"Generated: {uri}")
    assert "pa=gaurav%40upi" in uri
    assert "pn=Gaurav%20Nagar" in uri
    assert "am=540.00" in uri
    assert "cu=INR" in uri
    
    # Test case 2: Special characters in note
    uri2, _ = generate_upi_uri("test@upi", "Test", 10.0, transaction_note="Train #12345: New Delhi to Mumbai")
    print(f"Note Test: {uri2}")
    assert "tn=Train%20%2312345%3A%20New%20Delhi%20to%20Mumbai" in uri2
    
    print("✅ Task 1 Verification SUCCESSFUL!")

if __name__ == "__main__":
    verify_task_1()
