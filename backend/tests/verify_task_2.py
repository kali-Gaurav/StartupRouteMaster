import sys
import os
import urllib.parse

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.payment_utils import generate_upi_uri, get_transaction_note

def verify_task_2():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 2 (UPI DEEP LINKING)")
    
    # 1. Test standard URI generation
    vpa = "test@upi"
    name = "RouteMaster Test"
    amount = 49.0
    note = "RM_BOOK123"
    
    uri = generate_upi_uri(vpa, name, amount, note)
    print(f"  Generated URI: {uri}")
    
    # Check components
    parsed = urllib.parse.urlparse(uri)
    query = urllib.parse.parse_qs(parsed.query)
    
    assert parsed.scheme == "upi"
    assert parsed.netloc == "pay"
    assert query["pa"][0] == vpa
    assert query["pn"][0] == name
    assert query["am"][0] == "49.00"
    assert query["cu"][0] == "INR"
    assert query["tn"][0] == note
    
    # 2. Test Special Character Encoding (Subtask 2.9)
    name_special = "Anthony & Nagar"
    uri_special = generate_upi_uri(vpa, name_special, amount, note)
    print(f"  Encoded URI (Special Chars): {uri_special}")
    assert "Anthony+%26+Nagar" in uri_special or "Anthony%20%26%20Nagar" in uri_special
    
    # 3. Test Note Generation (Subtask 2.5)
    gen_note = get_transaction_note("550e8400-e29b-41d4-a716-446655440000")
    print(f"  Generated Note: {gen_note}")
    assert gen_note.startswith("RM_")
    
    print("\n✅ TASK 2 FULLY VERIFIED: UPI deep linking logic is accurate and safe.")

if __name__ == "__main__":
    verify_task_2()
