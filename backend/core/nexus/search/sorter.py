import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("nexus.search.sorter")

class NexusPolaritySorter:
    """[Task 31] Intelligence-Grade Search Sorter.
    Balances Duration, Price, and LIVE Delay Polarity.
    """
    
    def __init__(self):
        # Weights for balanced persona (Tasks 22/31)
        self.weights = {
            "duration": 0.4,
            "price": 0.3,
            "reliability": 0.2,
            "delay_polarity": 0.1
        }

    def sort_results(self, 
                    results: List[Dict[str, Any]], 
                    persona: str = "ECONOMY") -> List[Dict[str, Any]]:
        """
        Rank search results using a multi-dimensional Polarity Score.
        Lower score = Better rank (like distance).
        """
        if not results: return []
        
        # Adjust weights based on Persona [Task 12.3]
        current_weights = self.weights.copy()
        if persona == "EMERGENCY":
            current_weights["duration"] = 0.6
            current_weights["price"] = 0.1
        elif persona == "BUSINESS":
            current_weights["reliability"] = 0.4
            current_weights["duration"] = 0.3
            
        scored_results = []
        for r in results:
            score = self._calculate_polarity_score(r, current_weights)
            r["polarity_score"] = round(score, 4)
            scored_results.append(r)
            
        # Sort by Polarity Score ascending (Lower is better)
        return sorted(scored_results, key=lambda x: x["polarity_score"])

    def _calculate_polarity_score(self, item: Dict[str, Any], weights: Dict[str, float]) -> float:
        """
        [Task 31.3] Polarity Calculation:
        Score = (Norm_Duration * Wd) + (Norm_Price * Wp) + (1 - Reliability * Wr) + (Delay_Penalty * Wp)
        """
        # 1. Normalized Duration (Base 1000 mins)
        # Handle both V2 (total_duration) and V3 (duration) keys
        duration = item.get("total_duration") or item.get("duration") or 600
        duration_factor = min(duration / 1000, 1.0)
        
        # 2. Normalized Price (Base 2000 INR)
        # Handle both V2 (total_cost) and V3 (price) keys
        price = item.get("total_cost") or item.get("price") or 500
        price_factor = min(price / 2000, 1.0)
        
        # 3. Reliability Reversal (Higher Reliability = Lower Factor)
        # Handle both V2 (reliability_score) and V3 (reliability)
        reliability = item.get("reliability_score") or item.get("reliability") or 1.0
        reliability_factor = 1.0 - reliability
        
        # 4. Live Delay Polarity [NEW Task 31]
        # Check if segments have delay data in metadata
        delay_penalty = 0.0
        for segment in item.get("segments", []):
             delay = segment.get("delay_mins", 0)
             if delay > 30: # [Task 31.3]
                  delay_penalty += 0.2
             if delay > 120: # Severe Delay
                  delay_penalty += 0.5
                  
        total_score = (
            (duration_factor * weights["duration"]) +
            (price_factor * weights["price"]) +
            (reliability_factor * weights["reliability"]) +
            (delay_penalty * weights.get("delay_polarity", 0.1))
        )
        
        return total_score

nexus_sorter = NexusPolaritySorter()
