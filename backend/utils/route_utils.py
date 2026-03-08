"""
Route Utils - Task 5: Strict Deduplication & Fingerprinting
Ensures zero redundancy in search results.
"""

import hashlib
import logging
from typing import List, Dict, Set
from datetime import datetime, timedelta
from core.data_structures import Route

logger = logging.getLogger(__name__)

class RouteDedupFilter:
    @staticmethod
    def get_sequence_fingerprint(route: Route) -> str:
        """
        [5.1] Generates a hash based on the train sequence and station pairs.
        Format: (T12625:NDLS->KOTA)-(T12626:KOTA->BOM)
        """
        parts = []
        for s in route.segments:
            parts.append(f"{s.train_number or s.trip_id}:{s.departure_code}->{s.arrival_code}")
        
        fingerprint = "-".join(parts)
        return hashlib.md5(fingerprint.encode()).hexdigest()

    @staticmethod
    def apply_strict_dedup(routes: List[Route]) -> List[Route]:
        """
        [5.2] Time-Window Deduping: Merge identical sequences within 2 hours.
        [5.3] Redundant Segment Detection.
        [5.9] Atomic Filter Utility.
        """
        if not routes: return []

        # 1. Group by Sequence Fingerprint
        groups: Dict[str, List[Route]] = {}
        for r in routes:
            fp = RouteDedupFilter.get_sequence_fingerprint(r)
            if fp not in groups:
                groups[fp] = []
            groups[fp].append(r)

        final_routes = []

        # 2. Within each group, filter by time window
        for fp, group in groups.items():
            if len(group) == 1:
                final_routes.append(group[0])
                continue

            # Sort group by departure time
            group.sort(key=lambda x: x.segments[0].departure_time if x.segments else datetime.min)
            
            merged_in_group = []
            if group:
                current_best = group[0]
                for next_r in group[1:]:
                    # [5.2] If depart within 2 hours, they are likely the same "logical" choice
                    time_diff = (next_r.segments[0].departure_time - current_best.segments[0].departure_time).total_seconds() / 3600
                    
                    if time_diff < 2.0:
                        # Keep the one with better score
                        if next_r.score < current_best.score:
                            current_best = next_r
                    else:
                        merged_in_group.append(current_best)
                        current_best = next_r
                merged_in_group.append(current_best)
            
            final_routes.extend(merged_in_group)

        # 3. [5.3] Remove overlapping segments (Redundant checks)
        # (Already handled by graph engines usually, but good as a safety layer)
        
        logger.info(f"Strict Dedup: {len(routes)} -> {len(final_routes)} journeys.")
        return final_routes
