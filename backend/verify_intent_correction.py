import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from utils.nlp_router import get_local_intent

def log_test(name, success, detail=""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"[{status}] {name}: {detail}")

def run_tests():
    print("\n--- Task 2.8: Automatic Command Correction Verification ---")
    
    test_cases = [
        ("serch train", "search"),
        ("pner status", "pnr"),
        ("soos help", "sos"),
        ("trak my train", "track"),
        ("show dashbord", "dashboard"),
        ("my boking", "bookings"),
        ("pnrr", "pnr"),
        ("please serch trains", "search"),
        ("szarch delhi", "search"),
        ("cancle my ticket", "cancel"),
        ("ticketprice", "fare"),
        ("SEArCH", "search"),
        ("bookings", "bookings"),
        ("serch Delhi Mumbai", "search"),
    ]

    for text, expected in test_cases:
        res = get_local_intent(text)
        intent = res["intent"] if res else "None"
        success = intent == expected
        log_test(f"Typo: '{text}'", success, f"Resolved to: {intent}")

    print("----------------------------------------------------------\n")

if __name__ == "__main__":
    run_tests()
