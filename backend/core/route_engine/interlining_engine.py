import logging
import math
from typing import List, Dict, Any, Optional
from datetime import timedelta, datetime
from core.data_utils.structures import Route, RouteSegment, TransferConnection
from core.engines.hubs import MEGA_HUBS, HUB_TERMINAL_MAPPING, get_smart_transfer_buffer

logger = logging.getLogger("engine.interlining")

class InterliningEngine:
    """
    [G1.6.1] The 'Virtual Interlining' Engine.
    Scales RouteMaster by combining disconnected transport modes (Bus + Rail, Rail + Air).
    Provides 'Station Hub' mapping and connection safety windows.
    Refactored for Recursive Stitching (Max Depth 3).
    """
    
    HUB_RADIUS_KM = 35.0

    def __init__(self):
        self.transfer_penalty_multiplier = 1.15 # 15% duration penalty for inter-modal transfers

    async def find_interlined_routes(self, first_leg_routes: List[Route], second_leg_routes: List[Route], depth: int = 1, all_available_pools: Optional[List[List[Route]]] = None) -> List[Route]:
        """
        [Child G1.6.1.2] Multi-Modal Path-Finder.
        Recursive stitching of routes across different modes.
        """
        if depth > 3:
            return []
            
        interlined = []
        if not first_leg_routes or not second_leg_routes:
            return []
        
        # Optimization: Group second legs by origin
        second_by_origin = {}
        for r2 in second_leg_routes:
            if not r2.segments: continue
            origin = str(r2.segments[0].departure_code).upper()
            if origin not in second_by_origin: second_by_origin[origin] = []
            second_by_origin[origin].append(r2)

        for r1 in first_leg_routes:
            if not r1.segments: continue
            last_seg = r1.segments[-1]
            r1_arrival_node = str(last_seg.arrival_code).upper()
            r1_arrival_time = last_seg.arrival_time
            
            # Check all possible connections
            for r2_origin, r2_list in second_by_origin.items():
                if self._is_connectable_hub(r1_arrival_node, r2_origin):
                    for r2 in r2_list:
                        r2_departure_time = r2.segments[0].departure_time
                        
                        # Timing Logic: Safe Window
                        wait_time = r2_departure_time - r1_arrival_time
                        min_wait, max_wait = self._get_safe_window(r1_arrival_node, r2.metadata.get("mode"))
                        
                        if min_wait <= wait_time <= max_wait:
                            unified_route = self._stitch_routes(r1, r2, wait_time)
                            interlined.append(unified_route)
                            
                            # [Recursive Discovery]
                            # If we have more pools, try to stitch the new unified route with them
                            if all_available_pools and depth < 3:
                                for pool in all_available_pools:
                                    # Don't stitch with a pool that doesn't add value (simplified check)
                                    recursive_results = await self.find_interlined_routes(
                                        [unified_route], 
                                        pool, 
                                        depth=depth + 1, 
                                        all_available_pools=all_available_pools
                                    )
                                    interlined.extend(recursive_results)
                            
        logger.info(f"🧬 [INTERLINING] Depth {depth}: Found {len(interlined)} stitches.")
        return interlined

    def _get_safe_window(self, station_code: str, mode: Optional[str]) -> tuple:
        """Returns (min_wait, max_wait) based on hub size and mode."""
        buffer_mins = get_smart_transfer_buffer(station_code)
        
        is_air = mode == "FLIGHT"
        if is_air:
            return timedelta(minutes=buffer_mins + 120), timedelta(hours=10)
        
        return timedelta(minutes=buffer_mins + 30), timedelta(hours=6)

    def _is_connectable_hub(self, code1: str, code2: str) -> bool:
        """Determines if two station codes are within the connectable hub radius."""
        if not code1 or not code2: return False
        if code1 == code2: return True
        
        # 1. Dynamic Hub Mapping (from core.engines.hubs)
        # Check if they belong to the same city hub
        city1 = HUB_TERMINAL_MAPPING.get(code1, {}).get("city")
        city2 = HUB_TERMINAL_MAPPING.get(code2, {}).get("city")
        if city1 and city2 and city1 == city2:
            return True

        # 2. Check if code2 is an airport associated with hub code1
        if code2 in HUB_TERMINAL_MAPPING.get(code1, {}).get("airports", []):
            return True
        if code1 in HUB_TERMINAL_MAPPING.get(code2, {}).get("airports", []):
            return True

        # 3. Last Mile / Proximity (Task 12.6)
        # Mock logic: If codes are very similar (e.g., NDLS and DLI) or have 'METRO' suffix
        if code1[:3] == code2[:3] and len(code1) >= 3 and len(code2) >= 3:
            return True
        
        # Proximity for specific known pairs that are not in HUB_TERMINAL_MAPPING
        proximity_pairs = {
            ("STN", "LGW"), # Stansted to Gatwick (far but common interline)
            ("LHR", "LCY"),
            ("PNQ", "BOM"), # Pune to Mumbai
        }
        if (code1, code2) in proximity_pairs or (code2, code1) in proximity_pairs:
            return True
            
        return False

    def _stitch_routes(self, first: Route, second: Route, wait_time: timedelta) -> Route:
        """Combines two routes into one Virtual Interlined Route."""
        new_route = Route()
        
        for seg in first.segments:
            new_route.add_segment(seg)
            
        last_s1 = first.segments[-1]
        first_s2 = second.segments[0]
        
        # Apply Transfer Penalty Calculator (Hidden Cost)
        penalty_mins = int(wait_time.total_seconds() // 60 * (self.transfer_penalty_multiplier - 1.0))
        
        tc = TransferConnection(
            station_id=0,
            station_code=f"{last_s1.arrival_code}->{first_s2.departure_code}",
            arrival_time=last_s1.arrival_time,
            departure_time=first_s2.departure_time,
            duration_minutes=int(wait_time.total_seconds() // 60) + penalty_mins,
            station_name=f"Hub Transfer: {last_s1.arrival_code} to {first_s2.departure_code}",
            facilities_score=0.0,
            safety_score=0.0,
            is_multi_station=True,
            transfer_type="INTER-MODAL"
        )
        new_route.add_transfer(tc)
        
        for seg in second.segments:
            new_route.add_segment(seg)
        
        new_route.total_cost = (first.total_cost or 0) + (second.total_cost or 0)
        
        # Merge metadata
        new_route.metadata = first.metadata.copy()
        new_route.metadata.update(second.metadata)
        new_route.metadata.update({
            "type": "VIRTUAL_INTERLINED",
            "modes": list(set(first.metadata.get("modes", [first.metadata.get("mode", "RAIL")]) + 
                             second.metadata.get("modes", [second.metadata.get("mode", "RAIL")]))),
            "wait_time_minutes": wait_time.total_seconds() / 60,
            "engine": "interlining_nexus_v2_recursive"
        })
        
        # Duration recalc
        if new_route.segments:
            def _normalize_dt(value):
                if isinstance(value, str):
                    return datetime.fromisoformat(value.replace("Z", "+00:00"))
                return value
            start_dt = _normalize_dt(new_route.segments[0].departure_time)
            end_dt = _normalize_dt(new_route.segments[-1].arrival_time)
            new_route.total_duration = int((end_dt - start_dt).total_seconds() // 60)
            
        return new_route

interlining_engine = InterliningEngine()
