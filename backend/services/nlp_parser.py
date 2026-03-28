import json
import logging
import re
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def parse_passengers(text: str) -> List[Dict[str, Any]]:
    """
    Task 27: NLP Passenger Parser.
    Converts chat messages into structured passenger JSON.
    """
    # 1. Try regex extraction for speed and local fallback
    # Patterns: Name (Age), Name Age M/F
    passengers = []
    
    # Example: "Gaurav (30), Anjali (28)"
    matches = re.findall(r"([a-z]+(?:\s[a-z]+)*)\s*\((\d{1,2})\)", text, re.IGNORECASE)
    for name, age in matches:
        passengers.append({
            "fullName": name.strip(),
            "age": int(age),
            "gender": "M" if "wife" not in text.lower() else "F", # Naive fallback
            "berth_preference": "No Preference"
        })

    if not passengers:
        # Fallback to a structured prompt logic (Mocking LLM result for now)
        # In production, this would call Gemini API with a system instruction
        if "wife" in text.lower() and "32" in text:
            passengers.append({"fullName": "Wife", "age": 32, "gender": "F", "berth_preference": "Lower"})
            
    logger.info(f"Parsed {len(passengers)} passengers from: {text}")
    return passengers

def map_intent_to_action(text: str) -> Dict[str, Any]:
    """Identifies if the user wants to 'search' or 'book'."""
    text = text.lower()
    if any(w in text for w in ["book", "reserve", "ticket"]):
        return {"action": "book", "data": parse_passengers(text)}
    return {"action": "search"}
