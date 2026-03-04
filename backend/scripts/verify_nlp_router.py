import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from utils.nlp_router import get_local_intent

def test_router():
    test_cases = [
        ("PNR 1234567890", "pnr_status", "1234567890"),
        ("NDLS to BCT", "search", {"source": "NDLS", "destination": "BCT"}),
        ("emergency SOS!", "sos", None),
        ("help me", "sos", None),
        ("hello diksha", "greet", None),
        ("what are your commands?", "help", None),
        ("random message", None, None)
    ]

    print("--- Starting NLP Router Verification ---")
    for message, expected_intent, expected_entities in test_cases:
        result = get_local_intent(message)
        
        if result is None:
            status = "PASS" if expected_intent is None else "FAIL"
            print(f"[{status}] Message: '{message}' -> Result: None")
            continue

        intent = result.get("intent")
        entities = result.get("entities")
        
        intent_match = intent == expected_intent
        entities_match = True
        if expected_entities:
            if isinstance(expected_entities, str):
                entities_match = entities.get("pnr") == expected_entities
            else:
                entities_match = all(entities.get(k) == v for k, v in expected_entities.items())

        status = "PASS" if (intent_match and entities_match) else "FAIL"
        print(f"[{status}] Message: '{message}' -> Intent: {intent}, Entities: {entities}")

if __name__ == "__main__":
    test_router()
