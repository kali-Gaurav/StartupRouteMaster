import re
from typing import Dict, Any, Optional

class SOSEntityExtractor:
    """
    Extracts structured emergency data from voice transcripts.
    Focuses on: Coach, Seat, Symptoms, Weapon types.
    """
    
    PATTERNS = {
        "coach": r"(?i)\bcoach\s+([A-Z0-9]{2,4})\b",
        "seat": r"(?i)\bseat\s+(\d{1,3})\b",
        "berth": r"(?i)\bberth\s+(\d{1,3})\b",
        "weapon": r"(?i)\b(knife|gun|pistol|weapon|blade|bottle)\b",
        "medical": r"(?i)\b(pain|breath|bleeding|heart|chest|faint|unconscious|delivery|pregnant)\b"
    }

    @staticmethod
    def extract(text: str) -> Dict[str, Any]:
        results = {}
        for key, pattern in SOSEntityExtractor.PATTERNS.items():
            if key == "medical":
                matches = re.findall(pattern, text)
                if matches:
                    results[key] = list(set(matches)) # Unique symptoms
            else:
                match = re.search(pattern, text)
                if match:
                    results[key] = match.group(1) if len(match.groups()) > 0 else match.group(0)
        return results

    @staticmethod
    def get_urgency_score(extracted: Dict[str, Any]) -> int:
        """Returns a score from 0-10 based on threat level."""
        score = 0
        if "weapon" in extracted: score += 8
        if "medical" in extracted: score += 7
        if "coach" in extracted: score += 1
        return min(score, 10)
