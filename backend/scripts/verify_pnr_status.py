import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from utils.entity_extractor import EntityExtractor
from api.chat import generate_response

def test_pnr_intent():
    print("--- Conversational PNR Status Verification ---")
    
    # 1. Message with PNR
    message = "Check status for PNR 1234567890"
    print(f"\n[Test 1] Input: '{message}'")
    
    extracted = EntityExtractor.extract_all(message)
    session_data = {"extracted_entities": extracted}
    
    response = generate_response("pnr_status", message, session_data)
    
    print(f"Reply: {response.reply}")
    if response.suggestions:
        labels = [s.label for s in response.suggestions]
        print(f"Suggestions: {labels}")
        
    if "1234567890" in response.reply and "Track Live Train" in labels:
        print("[PASS] PNR recognized and correct suggestions provided.")
    else:
        print("[FAIL] PNR handling error.")

    # 2. Message without PNR
    message_no_pnr = "I want to check my PNR status"
    print(f"\n[Test 2] Input: '{message_no_pnr}'")
    response_no_pnr = generate_response("pnr_status", message_no_pnr, {})
    
    print(f"Reply: {response_no_pnr.reply}")
    if "10-digit PNR" in response_no_pnr.reply:
        print("[PASS] Correct fallback when PNR is missing.")
    else:
        print("[FAIL] Fallback logic error.")

if __name__ == "__main__":
    test_pnr_intent()
