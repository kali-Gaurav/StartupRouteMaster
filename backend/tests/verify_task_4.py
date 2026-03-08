import sys
import os
import urllib.parse

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.payment_utils import generate_upi_uri, get_transaction_note

def verify_task_4():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 4 (TRANSACTION NOTE)")
    
    # 1. Test short ID generation
    full_uuid = "550e8400-e29b-41d4-a716-446655440000"
    note = get_transaction_note(full_uuid)
    
    print(f"  Full ID: {full_uuid}")
    print(f"  Generated Note: {note}")
    
    assert note == "RM_550E8400"
    assert len(note) <= 12 # Very safe within 50 chars limit
    
    # 2. Verify in URI
    uri = generate_upi_uri("vpa@upi", "Name", 49.0, note)
    parsed = urllib.parse.urlparse(uri)
    query = urllib.parse.parse_qs(parsed.query)
    
    print(f"  URI Note Param: {query['tn'][0]}")
    assert query["tn"][0] == "RM_550E8400"
    
    print("\n✅ TASK 4 FULLY VERIFIED: Transaction notes are concise and traceable.")

if __name__ == "__main__":
    verify_task_4()
