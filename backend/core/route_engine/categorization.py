"""
Categorization Engine - Phase 4 Intelligence
Groups and ranks search results based on user intent, personas, and efficiency.
"""

import logging
from typing import List, Dict, Any
from core.data_structures import Route, Persona

logger = logging.getLogger(__name__)

class CategorizationEngine:
    """
    Groups the top verified routes into buckets:
    - top_3_highlight: Absolute best based on Persona.
    - confirmed: High availability probability.
    - fastest: Lowest total duration.
    - cheapest: Lowest total cost.
    - balanced: Optimal mix of speed/cost.
    - direct: No transfers.
    - one_transfer: Exactly one transfer.
    """

    @staticmethod
    def categorize(routes: List[Route], persona: Persona = Persona.BUDGET) -> Dict[str, List[Dict]]:
        """
        Takes a list of verified Route objects and returns a dictionary of grouped journey dictionaries.
        [4.1] Calculates global stats for normalization.
        """
        if not routes:
            return {
                "top_3_highlight": [],
                "high_availability": [],
                "fastest": [],
                "cheapest": [],
                "direct": [],
                "one_transfer": [],
                "two_plus_transfer": []
            }

        import numpy as np

        # 1. Global Statistics Engine [4.1]
        costs = np.array([r.total_cost for r in routes])
        durations = np.array([r.total_duration for r in routes])
        
        mean_cost = np.mean(costs)
        std_cost = np.std(costs)
        median_cost = np.median(costs)
        
        mean_dur = np.mean(durations)
        std_dur = np.std(durations)
        
        # 2. Convert to dicts and Filter Outliers [4.6]
        hydrated = []
        for r in routes:
            # Outlier Pruning: > 3x median cost unless it's 2x faster than mean
            is_outlier = r.total_cost > (3 * median_cost) and r.total_duration > (0.5 * mean_dur)
            if is_outlier: continue

            rd = r.to_dict()
            # Inject pricing metadata
            base_fare = rd.get("total_fare", 0)
            rd["pricing"] = {
                "view_only_fee": 49.0,
                "agent_booking_fee": 10.0,
                "ticket_fare": base_fare,
                "total_agent_checkout": round(base_fare + 49.0 + 10.0, 2)
            }
            
            # [4.5] Value Score Formula
            # Normalize Cost and Duration (0 to 1, where 0 is best)
            c_norm = (r.total_cost - np.min(costs)) / (np.max(costs) - np.min(costs)) if np.max(costs) != np.min(costs) else 0
            d_norm = (r.total_duration - np.min(durations)) / (np.max(durations) - np.min(durations)) if np.max(durations) != np.min(durations) else 0
            # Value = 0.4*D + 0.4*C + 0.2*(1-Prob)
            rd["value_score"] = (0.4 * d_norm) + (0.4 * c_norm) + (0.2 * (1.0 - r.availability_probability))
            
            hydrated.append(rd)

        categories = {
            "top_3_highlight": [],
            "high_availability": [],
            "fastest": [],
            "cheapest": [],
            "best_value": [], # [4.5]
            "direct": [],
            "one_transfer": [],
            "two_plus_transfer": []
        }

        # 3. Structural Grouping
        for rd in hydrated:
            num_segs = len(rd.get("segments", []))
            if num_segs == 1:
                categories["direct"].append(rd)
            elif num_segs == 2:
                categories["one_transfer"].append(rd)
            else:
                categories["two_plus_transfer"].append(rd)

            if rd.get("availability_probability", 0) >= 0.8:
                categories["high_availability"].append(rd)

        # 4. Ranked Buckets with Diversification [4.8]
        sorted_fastest = sorted(hydrated, key=lambda x: x.get("total_duration", 99999))
        sorted_cheapest = sorted(hydrated, key=lambda x: x.get("total_cost", 99999))
        sorted_value = sorted(hydrated, key=lambda x: x.get("value_score", 1.0))

        # [4.8] Ensure Fastest and Cheapest are distinct if possible
        cheapest_winner = sorted_cheapest[0] if sorted_cheapest else None
        
        fastest_winner = None
        for f in sorted_fastest:
            if cheapest_winner and f["journey_id"] == cheapest_winner["journey_id"]:
                continue
            fastest_winner = f
            break
        if not fastest_winner and sorted_fastest: fastest_winner = sorted_fastest[0]

        # [4.2] Relative Pricing Bounds Check for "Cheapest"
        # Only include in cheapest bucket if within 1.5 std dev of global min
        min_cost = np.min(costs)
        categories["cheapest"] = [rd for rd in sorted_cheapest if rd["total_fare"] <= (min_cost + 1.5 * std_cost)][:5]
        categories["fastest"] = sorted_fastest[:5]
        categories["best_value"] = sorted_value[:5]
        
        # 5. Persona-based Highlighting
        sorted_by_score = sorted(hydrated, key=lambda x: x.get("score", 99999))
        min_duration = np.min(durations)
        max_avail = np.max([r.get("availability_prob", 0) for r in hydrated]) if hydrated else 0

        top_3 = []
        seen_ids = set()
        for rd in sorted_by_score:
            jid = rd["journey_id"]
            if jid not in seen_ids:
                reason = ""
                # Assign Tag and Reason [4.9]
                if rd.get("total_duration") == min_duration:
                    rd["highlight_label"] = "⚡ Lightning Fast"
                    diff = int(mean_dur - min_duration)
                    reason = f"Saves {diff} mins vs average journey." if diff > 30 else "Fastest available option."
                elif rd.get("total_fare") == min_cost:
                    rd["highlight_label"] = "💰 Cheapest"
                    diff = int(mean_cost - min_cost)
                    reason = f"Save ₹{diff} vs average fare." if diff > 100 else "Lowest fare found."
                elif rd.get("journey_id") == (sorted_value[0]["journey_id"] if sorted_value else None):
                    rd["highlight_label"] = "💎 Best Value"
                    reason = "Perfect balance of speed, cost, and availability."
                else:
                    persona_tags = {
                        Persona.BUDGET: ("📉 Economical", "Optimized for your budget constraints."),
                        Persona.COMFORT: ("🛌 Premium Comfort", "Prioritizes luxury and reliable timing."),
                        Persona.EMERGENCY: ("🚑 Critical", "Earliest possible arrival recommended."),
                        Persona.FAMILY: ("👨‍👩‍👧‍👦 Family Safe", "Spacious transfers and high reliability.")
                    }
                    tag, p_reason = persona_tags.get(persona, ("⭐ Recommended", "Balanced route for your journey."))
                    rd["highlight_label"] = tag
                    reason = p_reason

                rd["is_featured"] = True
                rd["highlight_reason"] = reason
                top_3.append(rd)
                seen_ids.add(jid)
            if len(top_3) >= 3: break
            
        categories["top_3_highlight"] = top_3
        return categories
