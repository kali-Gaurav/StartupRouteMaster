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
    def categorize(routes: List[Route], persona: Persona = Persona.BUDGET) -> Dict[str, List[Dict]]:
        """
        [NEW] Advanced Categorization for Confirmed Arrival and Structural Preference.
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

        import numpy as np

        # 1. Hydrate and Filter
        hydrated = []
        for r in routes:
            rd = r.to_dict()
            # Pricing logic injection
            base_fare = rd.get("total_fare", 0)
            rd["pricing"] = {
                "view_only_fee": 49.0,
                "agent_booking_fee": 10.0,
                "ticket_fare": base_fare,
                "total_agent_checkout": round(base_fare + 49.0 + 10.0, 2)
            }
            hydrated.append(rd)

        # 2. Bucket: Top 10 Fastest Total
        sorted_by_speed = sorted(hydrated, key=lambda x: x.get("total_duration", 99999))
        top_10_fastest = sorted_by_speed[:10]

        # 3. Bucket: Top 3 Confirmed Fastest
        confirmed = [rd for rd in hydrated if rd.get("metadata", {}).get("is_verified") == True]
        top_3_confirmed = sorted(confirmed, key=lambda x: x.get("total_duration", 99999))[:3]

        # 4. Bucket: Top 5 Optimal
        sorted_optimal = sorted(hydrated, key=lambda x: x.get("score", 99999))
        top_5_optimal = sorted_optimal[:5]

        # 5. Structural Buckets (Transfers)
        direct = []
        one_transfer = []
        two_transfer = []
        three_plus_transfer = []

        for rd in hydrated:
            transfer_count = len(rd.get("transfers", []))
            if transfer_count == 0:
                direct.append(rd)
            elif transfer_count == 1:
                one_transfer.append(rd)
            elif transfer_count == 2:
                two_transfer.append(rd)
            else:
                three_plus_transfer.append(rd)

        # 6. Bucket: Alternative Sorted (Travel Time)
        # Unique routes not already highlighted in the priority top buckets
        top_ids = {r["journey_id"] for r in top_3_confirmed + top_10_fastest + top_5_optimal}
        alternatives = [rd for rd in sorted_by_speed if rd["journey_id"] not in top_ids]

        return {
            "top_3_confirmed_fastest": top_3_confirmed,
            "top_10_fastest_total": top_10_fastest,
            "top_5_optimal": top_5_optimal,
            "direct": sorted(direct, key=lambda x: x.get("total_duration", 99999))[:10],
            "one_transfer": sorted(one_transfer, key=lambda x: x.get("total_duration", 99999))[:10],
            "two_transfer": sorted(two_transfer, key=lambda x: x.get("total_duration", 99999))[:10],
            "three_plus_transfer": sorted(three_plus_transfer, key=lambda x: x.get("total_duration", 99999))[:10],
            "alternative_sorted": alternatives[:20],
            "metadata": {
                "total_yield": len(hydrated),
                "confirmed_yield": len(confirmed)
            }
        }
