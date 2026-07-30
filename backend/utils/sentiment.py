from typing import Dict, Any

class SentimentAnalyzer:
    """
    Detects user sentiment using keyword analysis.
    Categorizes into: positive, neutral, negative, critical.
    """
    
    CRITICAL_KEYWORDS = ['useless', 'garbage', 'waste', 'hate', 'stupid', 'worst', 'fail', 'bad service']
    URGENT_KEYWORDS = ['late', 'delayed', 'stuck', 'where is', 'cancel', 'refund', 'help', 'sos']

    @staticmethod
    def analyze(text: str) -> str:
        """
        Returns sentiment level: 'neutral', 'negative', or 'urgent'.
        """
        msg = text.lower()
        
        if any(kw in msg for kw in SentimentAnalyzer.CRITICAL_KEYWORDS):
            return "negative"
            
        if any(kw in msg for kw in SentimentAnalyzer.URGENT_KEYWORDS):
            return "urgent"
            
        return "neutral"

    @staticmethod
    def get_persona_override(sentiment: str) -> str:
        """
        Returns a system prompt snippet to override AI behavior.
        """
        if sentiment == "negative":
            return "THE USER IS FRUSTRATED. Be extremely concise, apologetic, and focus ONLY on immediate solutions. Avoid any 'friendly' filler or emojis."
        
        if sentiment == "urgent":
            return "THE USER IS IN A HURRY OR HAS A PROBLEM. Prioritize speed and accuracy. Provide direct links to tracking or SOS if needed."
            
        return ""
