import asyncio
import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from telegram_bot.intent_classifier import IntentClassifier
from telegram_bot.schemas import IntentType

async def test_nlp_search():
    classifier = IntentClassifier()
    
    test_cases = [
        {
            "text": "train from Delhi to Mumbai tomorrow",
            "expected": {
                "intent": IntentType.SEARCH_TRAINS,
                "origin": "NDLS",
                "destination": "MMCT",
                "date": (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
            }
        },
        {
            "text": "Palakkad to Chennai 5 May sleeper",
            "expected": {
                "intent": IntentType.SEARCH_TRAINS,
                "origin": "Palakkad",
                "destination": "MAS",
                "date": datetime.strptime(f"5 May {datetime.utcnow().year}", "%d %b %Y").strftime("%Y-%m-%d"),
                "class": "sleeper"
            }
        },
        {
            "text": "Kochi to Bangalore today",
            "expected": {
                "intent": IntentType.SEARCH_TRAINS,
                "origin": "ERS",
                "destination": "SBC",
                "date": datetime.utcnow().strftime("%Y-%m-%d")
            }
        },
        {
            "text": "Delhi to Mumbai",
            "expected": {
                "intent": IntentType.SEARCH_TRAINS,
                "origin": "NDLS",
                "destination": "MMCT"
            }
        }
    ]
    
    print(f"=== Running NLP Search Unit Tests ({len(test_cases)} cases) ===")
    
    passed = 0
    for i, case in enumerate(test_cases):
        result = await classifier.classify(case["text"])
        
        print(f"\nTest {i+1}: '{case['text']}'")
        print(f"Detected Intent: {result.intent}")
        print(f"Extracted Entities: {result.entities}")
        
        # Check intent
        if result.intent != case["expected"]["intent"]:
            print(f"FAILED: Intent Mismatch: Expected {case['expected']['intent']}, got {result.intent}")
            continue
            
        # Check entities
        match = True
        for key, expected_val in case["expected"].items():
            if key == "intent": continue
            
            actual_val = result.entities.get(key)
            if actual_val != expected_val:
                print(f"FAILED: Entity Mismatch for '{key}': Expected {expected_val}, got {actual_val}")
                match = False
        
        if match:
            print("PASSED")
            passed += 1
        else:
            print("FAILED")
            
    print(f"\nSummary: {passed}/{len(test_cases)} tests passed.")

if __name__ == "__main__":
    asyncio.run(test_nlp_search())
