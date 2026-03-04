import re
from typing import Dict, Any

class EmotionalEngine:
    """
    Analyzes text intensity to assess passenger panic levels.
    """
    
    INTENSITY_WORDS = {
        "extreme": ["dying", "killing", "dead", "blood", "stabbing", "gun", "rape", "fire", "screaming", "suffocating"],
        "high": ["help", "save", "scared", "unsafe", "danger", "immediately", "quick", "stole", "hurt"],
        "moderate": ["worried", "late", "stuck", "where", "problem", "missed"]
    }

    @staticmethod
    def calculate_panic_score(text: str) -> int:
        """
        Returns a panic score from 1-10.
        """
        if not text: return 1
        
        score = 1
        msg = text.lower()
        
        # 1. Word Intensity
        for word in EmotionalEngine.INTENSITY_WORDS["extreme"]:
            if word in msg: score += 5
        for word in EmotionalEngine.INTENSITY_WORDS["high"]:
            if word in msg: score += 3
        for word in EmotionalEngine.INTENSITY_WORDS["moderate"]:
            if word in msg: score += 1
            
        # 2. Punctuation Intensity (!!!)
        if "!!!" in text: score += 2
        
        # 3. Typography Intensity (ALL CAPS)
        # Check if message is mostly caps and long enough
        if len(text) > 5 and text.isupper():
            score += 2
            
        return min(score, 10)

    @staticmethod
    def get_priority_escalation(score: int) -> str:
        if score >= 8: return "critical"
        if score >= 5: return "high"
        return "medium"
