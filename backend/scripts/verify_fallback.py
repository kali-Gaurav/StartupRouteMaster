import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from api.chat import generate_response

def test_fallback():
    print("--- Local Fallback Response Verification ---")
    
    # 1. Trigger Fallback
    print(f"\n[Test] Triggering 'fallback' intent...")
    response = generate_response("fallback", "random query when down", {})
    
    print(f"Reply: {response.reply[:100]}...")
    if response.suggestions:
        labels = [s.label for s in response.suggestions]
        print(f"Suggestions: {labels}")
        
    if "trouble connecting" in response.reply and "Manual Search" in labels:
        print("[PASS] Fallback message and actions are correct.")
    else:
        print("[FAIL] Fallback response error.")

if __name__ == "__main__":
    test_fallback()
