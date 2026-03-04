import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from utils.sentiment import SentimentAnalyzer

def test_sentiment():
    print("--- Sentiment Analysis & Persona Override Verification ---")
    
    test_cases = [
        ("This is the worst service ever, I hate it.", "negative"),
        ("My train is late, help me with a refund!", "urgent"),
        ("I want to book a ticket to Mumbai.", "neutral"),
    ]

    for message, expected_sentiment in test_cases:
        sentiment = SentimentAnalyzer.analyze(message)
        override = SentimentAnalyzer.get_persona_override(sentiment)
        
        status = "PASS" if sentiment == expected_sentiment else "FAIL"
        print(f"[{status}] Message: '{message[:30]}...'")
        print(f"      Sentiment: {sentiment}")
        print(f"      Override:  {override[:50]}...")

if __name__ == "__main__":
    test_sentiment()
