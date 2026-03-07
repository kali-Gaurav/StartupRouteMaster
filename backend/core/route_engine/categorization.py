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

        # Convert to dicts for frontend consumption
        hydrated = []
        for r in routes:
            rd = r.to_dict()
            # Inject pricing metadata (Task 44)
            base_fare = rd.get("total_fare", 0)
            rd["pricing"] = {
                "view_only_fee": 49.0,
                "agent_booking_fee": 10.0,
                "ticket_fare": base_fare,
                "total_agent_checkout": round(base_fare + 49.0 + 10.0, 2)
            }
            hydrated.append(rd)

        categories = {
            "top_3_highlight": [],
            "high_availability": [],
            "fastest": [],
            "cheapest": [],
            "shortest_layover": [],
            "direct": [],
            "one_transfer": [],
            "two_plus_transfer": []
        }

        # 1. Structural Grouping
        for rd in hydrated:
            num_segs = len(rd.get("segments", []))
            if num_segs == 1:
                categories["direct"].append(rd)
            elif num_segs == 2:
                categories["one_transfer"].append(rd)
            else:
                categories["two_plus_transfer"].append(rd)

            # 2. Availability Grouping
            if rd.get("availability_probability", 0) >= 0.8:
                categories["high_availability"].append(rd)

        # 3. Ranking based buckets
        categories["fastest"] = sorted(hydrated, key=lambda x: x.get("total_duration", 99999))[:5]
        categories["cheapest"] = sorted(hydrated, key=lambda x: x.get("total_cost", 99999))[:5]
        
        # Calculate total layover for multi-transfer routes
        def get_layover(r_dict):
            segs = r_dict.get("segments", [])
            if len(segs) <= 1: return 0
            # Layover is time between segments
            # For simplicity, we can use metadata or calculate from times
            # Since durations are in minutes, we can use a heuristic or actual diff
            # Let's assume total_duration - sum(segment durations)
            sum_seg_dur = sum(s.get("duration_minutes", 0) for s in segs)
            return r_dict.get("total_duration", 0) - sum_seg_dur

        categories["shortest_layover"] = sorted(hydrated, key=get_layover)[:5]
        
        # 4. Persona-based Highlighting (Task 32)
        sorted_by_score = sorted(hydrated, key=lambda x: x.get("score", 99999))
        
        # Heuristics for tagging and reasoning
        avg_duration = sum([r.get("total_duration", 0) for r in hydrated]) / len(hydrated) if hydrated else 0
        min_duration = min([r.get("total_duration", 99999) for r in hydrated]) if hydrated else 0
        min_cost = min([r.get("total_fare", 99999) for r in hydrated]) if hydrated else 0
        max_avail = max([r.get("availability_prob", 0) for r in hydrated]) if hydrated else 0

        # Diversity check: ensure top 3 are different primary trains
        top_3 = []
        seen_train_sets = set()
        for rd in sorted_by_score:
            train_set = tuple(sorted([s.get("train_number") for s in rd.get("segments", [])]))
            if train_set not in seen_train_sets:
                # [32.6] Reason Generation
                reason = ""
                # Assign Tag and Reason
                if rd.get("total_duration") == min_duration:
                    rd["highlight_label"] = "⚡ Lightning Fast"
                    diff = int(avg_duration - min_duration)
                    reason = f"Saves {diff} mins vs average journey." if diff > 30 else "Fastest available option."
                elif rd.get("total_fare") == min_cost:
                    rd["highlight_label"] = "💰 Best Value"
                    reason = "Absolute lowest fare found for this date."
                elif rd.get("availability_prob") >= 0.9 and rd.get("availability_prob") == max_avail:
                    rd["highlight_label"] = "✅ Most Reliable"
                    reason = "Highest probability of a confirmed seat."
                else:
                    # Persona specific default tags
                    persona_tags = {
                        Persona.BUDGET: ("📉 Economical Choice", "Optimal balance of cost and travel time."),
                        Persona.COMFORT: (" Couch Maximum Comfort", "Prioritizes premium trains and fewer transfers."),
                        Persona.EMERGENCY: ("🚑 Critical Priority", "Selected for earliest possible arrival."),
                        Persona.FAMILY: ("👨‍👩‍👧‍👦 Family Friendly", "Reliable connections with comfortable layovers.")
                    }
                    tag, p_reason = persona_tags.get(persona, ("⭐ Recommended", "Balanced route for your journey."))
                    rd["highlight_label"] = tag
                    reason = p_reason

                rd["is_featured"] = True
                rd["highlight_reason"] = reason
                top_3.append(rd)
                seen_train_sets.add(train_set)
            if len(top_3) >= 3: break

            
        categories["top_3_highlight"] = top_3

        return categories
