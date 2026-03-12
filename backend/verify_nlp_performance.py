from utils.nlp_router import get_local_intent

def test_nlp_router():
    test_cases = [
        ("PNR 1234567890", "pnr"),
        ("SOS HELP ME", "sos"),
        ("My bookings", "bookings"),
        ("show dashboard", "dashboard"),
        ("link telegram", "telegram"),
        ("cancel my ticket", "cancel"),
        ("refund status", "cancel"),
        ("how much is the fare", "fare"),
        ("train cost to Mumbai", "fare"),
        ("track my train", "track"),
        ("where is train 12626", "track"),
        ("station facilities", "station"),
        ("platform number", "station"),
    ]
    
    print("\n--- NLP Router Verification ---")
    for text, expected in test_cases:
        res = get_local_intent(text)
        intent = res["intent"] if res else "None"
        status = "✅ PASS" if intent == expected else f"❌ FAIL (Expected {expected}, got {intent})"
        print(f"Query: '{text}' -> Intent: {intent} | {status}")

if __name__ == "__main__":
    test_nlp_router()
