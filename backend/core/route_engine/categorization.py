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
    Groups the top verified routes into highly specific utility buckets:
    - top_3_confirmed_fastest: Absolute fastest with real-time verified seats across ALL segments.
    - top_10_fastest_total: Top 10 by speed, regardless of current verification.
    - top_5_optimal: The best 'Value Score' routes (Speed + Cost + Reliability).
    - direct: Journeys with 0 transfers.
    - one_transfer: Journeys with exactly 1 transfer.
    - two_transfer: Journeys with exactly 2 transfers.
    - three_plus_transfer: Journeys with 3 or more transfers.
    - alternative_sorted: All remaining routes sorted strictly by travel time.
    """

    @staticmethod
    def categorize(routes: List[Route], persona: Persona = Persona.COMFORT) -> Dict[str, List[Dict]]:
        """
        [8.1-8.10] Refactored Categorization with Masking and Persona prioritization.
        """
        if not routes:
            return {
                "top_3_confirmed_fastest": [],
                "top_10_fastest_total": [],
                "top_5_optimal": [],
                "direct": [],
                "one_transfer": [],
                "two_transfer": [],
                "three_plus_transfer": [],
                "alternative_sorted": []
            }

        # 1. Hydrate and Mask (Subtask 8.9, 8.10)
        hydrated = []
        for r in routes:
            rd = r.to_dict()
            
            # [8.12] Reliability Badge
            rd["reliability_badge"] = "green" if r.score > 70 else "yellow" if r.score > 40 else "red"
            
            # [8.1] Mask sensitive data if not unlocked
            if not rd.get("is_unlocked"):
                CategorizationEngine._mask_sensitive_data(rd)
                
            hydrated.append(rd)

        # 2. Bucket: Top 10 Fastest Total
        sorted_by_speed = sorted(hydrated, key=lambda x: x.get("total_duration", 99999))
        top_10_fastest = sorted_by_speed[:10]

        # 3. Bucket: Top 3 Confirmed Fastest (Verified Seats)
        confirmed = [rd for rd in hydrated if rd.get("metadata", {}).get("is_verified") == True]
        top_3_confirmed = sorted(confirmed, key=lambda x: x.get("total_duration", 99999))[:3]

        # 4. Bucket: Top 5 Optimal
        sorted_optimal = sorted(hydrated, key=lambda x: x.get("score", 0), reverse=True)
        top_5_optimal = sorted_optimal[:5]

        # 5. Structural Buckets (Subtask 8.3)
        direct = [rd for rd in hydrated if len(rd.get("transfers", [])) == 0]
        one_transfer = [rd for rd in hydrated if len(rd.get("transfers", [])) == 1]
        two_transfer = [rd for rd in hydrated if len(rd.get("transfers", [])) == 2]
        three_plus_transfer = [rd for rd in hydrated if len(rd.get("transfers", [])) >= 3]

        # 6. Final Response with Metadata
        response = {
            "top_3_confirmed_fastest": top_3_confirmed,
            "top_10_fastest_total": top_10_fastest,
            "top_5_optimal": top_5_optimal,
            "direct": sorted(direct, key=lambda x: x.get("total_duration", 99999))[:10],
            "one_transfer": sorted(one_transfer, key=lambda x: x.get("total_duration", 99999))[:10],
            "two_transfer": sorted(two_transfer, key=lambda x: x.get("total_duration", 99999))[:10],
            "three_plus_transfer": sorted(three_plus_transfer, key=lambda x: x.get("total_duration", 99999))[:10],
            "alternative_sorted": sorted_by_speed[:20],
            "metadata": {
                "total_yield": len(hydrated),
                "confirmed_yield": len(confirmed),
                "persona": persona.value
            }
        }
        
        # [8.7] Persona-based prioritisation could be handled by re-ordering keys or via frontend
        return response

    @staticmethod
    def _mask_sensitive_data(rd: Dict):
        """[8.9, 8.10] Masks train numbers and specific trip IDs for locked routes."""
        for leg in rd.get("legs", []):
            t_no = str(leg.get("train_number", ""))
            if t_no and len(t_no) >= 3:
                leg["train_number"] = t_no[:2] + "XXX"
            leg["trip_id"] = "TRP_HIDDEN"
            # Keep station codes and times for planning
