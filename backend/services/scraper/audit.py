import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("nexus.scraper.audit")

class ScraperAudit:
    """[Task 34] Advanced Content Density & Polarity Auditor.
    Detects 'Silent Failures' (Status 200 with Empty Content).
    """

    def __init__(self, min_density_bytes: int = 500):
        self.min_density = min_density_bytes

    def verify_content(self, 
                       html: str, 
                       expected_markers: List[str] = None) -> bool:
        """
        [Task 34.1] Content Density Audit.
        Checks if the HTML payload is > min_density and contains expected markers.
        """
        # 1. Byte Density Check
        if len(html) < self.min_density:
             logger.warning(f"📉 [AUDIT:FAIL] Low content density detected ({len(html)} bytes). Possible scraper ban.")
             return False
             
        # 2. Key Marker Check (e.g., 'table', 'train_no', 'schedule')
        if expected_markers:
             for marker in expected_markers:
                  if marker.lower() in html.lower():
                       return True
             logger.warning(f"📉 [AUDIT:FAIL] Multi-marker check failed. Expected: {expected_markers}")
             return False
             
        return True

    def calculate_error_polarity(self, 
                                providers_data: List[Dict[str, Any]]) -> float:
        """
        [Task 36.5] Returns a polarity score (0.0 to 1.0) for the current scrape cycle.
        0.0 = All providers failed. 1.0 = High density success.
        """
        if not providers_data: return 0.0
        
        success_count = sum(1 for p in providers_data if p.get("success"))
        avg_density = sum(len(p.get("content", "")) for p in providers_data) / len(providers_data)
        
        # Weighted Score: 60% Success Rate, 40% Density Scaling
        score = (success_count / len(providers_data)) * 0.6 + min(avg_density / 5000, 1.0) * 0.4
        return round(score, 2)

scraper_audit = ScraperAudit()
