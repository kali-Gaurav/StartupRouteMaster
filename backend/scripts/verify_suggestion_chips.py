import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from api.chat import generate_response

def test_chips():
    session_data = {
        "extracted_entities": {"source": "New Delhi", "destination": "Mumbai Central"}
    }
    
    print("--- Dynamic Suggestion Chips Verification ---")
    
    # 1. Test Search Intent Chips
    print("\n[Test 1] Checking Chips for 'search' intent...")
    response = generate_response("search", "Delhi to Mumbai", session_data)
    if response.suggestions:
        labels = [chip.label for chip in response.suggestions]
        print(f"Chips: {labels}")
        if "View Results" in labels and "Modify Search" in labels:
            print("[PASS] Search chips correctly generated.")
        else:
            print("[FAIL] Missing expected search chips.")
    else:
        print("[FAIL] No chips generated for search.")

    # 2. Test SOS Intent Chips
    print("\n[Test 2] Checking Chips for 'trigger_sos' intent...")
    response = generate_response("trigger_sos", "help me", {})
    if response.suggestions:
        labels = [chip.label for chip in response.suggestions]
        print(f"Chips: {labels}")
        if "🚨 TRIGGER SOS NOW" in labels:
            print("[PASS] SOS chips correctly generated.")
        else:
            print("[FAIL] Missing expected SOS chips.")
    else:
        print("[FAIL] No chips generated for SOS.")

if __name__ == "__main__":
    test_chips()
