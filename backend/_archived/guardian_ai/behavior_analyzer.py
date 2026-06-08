import re
import logging
from typing import Dict, Any

logger = logging.getLogger("behavior_analyzer")

class BehaviorAnalyzer:
    """
    Phase 2: Behavior Understanding Brain
    Detects risk from text patterns, looking for fear, panic, harassment, or distress.
    In a full production environment, this delegates to an NLP model (e.g., Llama/Gemini).
    """

    # Keyword heuristics for fast local triage (Offline/Fast path)
    HIGH_RISK_KEYWORDS = [
        r"\bhelp\b", r"\bscared\b", r"\bfollow(ed|ing)?\b", r"\battack(ed|ing)?\b",
        r"\bweapon\b", r"\bgun\b", r"\bknife\b", r"\bpolice\b", r"\bemergency\b",
        r"\bharass(ed|ing)?\b", r"\bcreep\b", r"\bunsafe\b", r"\balone\b"
    ]
    
    MODERATE_RISK_KEYWORDS = [
        r"\bdelay\b", r"\blost\b", r"\bconfused\b", r"\bcancelled\b",
        r"\bmissed\b", r"\bdark\b", r"\bstranded\b"
    ]

    async def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Analyzes passenger input and returns a structured risk assessment.
        """
        text_lower = text.lower()
        
        # 1. Local Heuristic Analysis
        high_matches = []
        mod_matches = []
        
        for pattern in self.HIGH_RISK_KEYWORDS:
            if re.search(pattern, text_lower):
                high_matches.append(pattern.replace(r"\b", "").replace(r"(ed|ing)?", ""))
                
        for pattern in self.MODERATE_RISK_KEYWORDS:
            if re.search(pattern, text_lower):
                mod_matches.append(pattern.replace(r"\b", "").replace(r"(ed|ing)?", ""))

        if high_matches:
            risk_delta = 40.0 + (10.0 * len(high_matches))
            return {
                "detected": True,
                "category": "High Threat Threat",
                "description": f"Detected high-risk keywords: {', '.join(high_matches)}",
                "risk_delta": min(risk_delta, 80.0)
            }
            
        if mod_matches:
            risk_delta = 10.0 + (5.0 * len(mod_matches))
            return {
                "detected": True,
                "category": "Operational Anomaly / Discomfort",
                "description": f"Detected operational/discomfort keywords: {', '.join(mod_matches)}",
                "risk_delta": min(risk_delta, 30.0)
            }

        # 2. Advanced NLP Analysis (Stubbed for Cloud Integration)
        # Here we would call the ML pipeline if local heuristics found nothing but sentiment is negative
        
        return {
            "detected": False,
            "category": "Normal",
            "description": "Standard communication",
            "risk_delta": 0.0
        }

behavior_analyzer = BehaviorAnalyzer()
