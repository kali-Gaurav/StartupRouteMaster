import logging
import math
from typing import List, Dict, Any, Optional
from datetime import timedelta, datetime
from core.data_structures import Route, RouteSegment, TransferConnection

logger = logging.getLogger("engine.interlining")

class InterliningEngine:
    """
    [G1.6.1] The 'Virtual Interlining' Engine.
    Scales RouteMaster by combining disconnected transport modes (Bus + Rail, Rail + Air).
    Provides 'Station Hub' mapping and connection safety windows.
    """
    
    # Global Hub Radius in KM (Distance to consider stations as "Connectable")
    HUB_RADIUS_KM = 35.0  # Increased for City-to-Airport transitions (e.g. NDLS to DEL)

    def haversine_distance(self, lat1, lon1, lat2, lon2):
        """Standard distance calculation between two geo-coordinates."""
        R = 6371  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.asin(math.sqrt(a))
        return R * c

    async def find_interlined_routes(self, first_leg_routes: List[Route], second_leg_routes: List[Route]) -> List[Route]:
        """
        [Child G1.6.1.2] Multi-Modal Path-Finder.
        Attempts to stitch two partial routes together (e.g. Train -> Flight).
        """
        interlined = []
        if not first_leg_routes or not second_leg_routes:
            return []
        
        # Optimization: Group second legs by origin for faster lookup
        second_by_origin = {}
        for r2 in second_leg_routes:
            if not r2.segments: continue
            origin = r2.segments[0].departure_code
            if origin not in second_by_origin: second_by_origin[origin] = []
            second_by_origin[origin].append(r2)

        for r1 in first_leg_routes:
            if not r1.segments: continue
            last_seg = r1.segments[-1]
            r1_arrival_node = last_seg.arrival_code
            r1_arrival_time = last_seg.arrival_time
            
            # Check all possible connections
            for r2_origin, r2_list in second_by_origin.items():
                # 1. Connection Logic: Same Hub or within radius?
                if self._is_connectable_hub(r1_arrival_node, r2_origin):
                    for r2 in r2_list:
                        r2_departure_time = r2.segments[0].departure_time
                        
                        # 2. Timing Logic: Safe Window
                        # Flights need more time (3-8 hours) vs buses (1.5-4 hours)
                        is_air = r2.metadata.get("mode") == "FLIGHT"
                        min_wait = timedelta(hours=3) if is_air else timedelta(hours=1.5)
                        max_wait = timedelta(hours=10) if is_air else timedelta(hours=6)
                        
                        wait_time = r2_departure_time - r1_arrival_time
                        if min_wait <= wait_time <= max_wait:
                            # 3. Stitch segments
                            unified_route = self._stitch_routes(r1, r2, wait_time)
                            interlined.append(unified_route)
                            logger.info(f"🔗 [INTERLINING] Virtual Link Found: {r1_arrival_node} -> {r2_origin} ({r2.metadata.get('mode')})")

        return interlined

    def _is_connectable_hub(self, code1: str, code2: str, cluster_map: Optional[Dict[str, str]] = None) -> bool:
        """Determines if two station codes are within the connectable hub radius."""
        if not code1 or not code2: return False
        if code1 == code2: return True
        
        # 1. Use the provided cluster map (Dynamic Knowledge from Builder)
        if cluster_map:
            if cluster_map.get(code1) == cluster_map.get(code2) and cluster_map.get(code1) is not None:
                return True

        # 2. Hardcoded High-Confidence Links (Static Fallback)
        hub_links = {
            "NDLS": "DEL", "NZM": "DEL", "DLI": "DEL", "ANVT": "DEL",
            "BCT": "BOM", "CSMT": "BOM", "LTT": "BOM", "BOM": "BOM", "BDTS": "BOM",
            "MAS": "MAA", "MS": "MAA", "MAA": "MAA",
            "SBC": "BLR", "YPR": "BLR", "BLR": "BLR",
            "HWH": "CCU", "SDAH": "CCU", "CCU": "CCU",
            "PNBE": "PAT", "PPTA": "PAT"
        }
        if hub_links.get(code1) == hub_links.get(code2) and hub_links.get(code1) is not None:
            return True
        if hub_links.get(code1) == code2 or hub_links.get(code2) == code1:
            return True

        # Legacy Prefix Match (Final Fallback)
        return code1[:3] == code2[:3]

    def _stitch_routes(self, first: Route, second: Route, wait_time: timedelta) -> Route:
        """Combines two routes into one Virtual Interlined Route."""
        new_route = Route()
        
        # Copy segments from first route
        for seg in first.segments:
            new_route.add_segment(seg)
            
        # Add a TransferConnection between them
        last_s1 = first.segments[-1]
        first_s2 = second.segments[0]
        
        tc = TransferConnection(
            station_id=0,
            station_code=f"{last_s1.arrival_code}->{first_s2.departure_code}",
            arrival_time=last_s1.arrival_time,
            departure_time=first_s2.departure_time,
            duration_minutes=int(wait_time.total_seconds() // 60),
            station_name=f"Hub Transfer: {last_s1.arrival_code} to {first_s2.departure_code}",
            facilities_score=0.0,
            safety_score=0.0,
            platform_from=None,
            platform_to=None,
            is_multi_station=True,
            transfer_type="INTER-MODAL"
        )
        new_route.add_transfer(tc)
        
        # Copy segments from second route
        for seg in second.segments:
            new_route.add_segment(seg)
        
        new_route.total_cost = (first.total_cost or 0) + (second.total_cost or 0)
        
        # Merge and define metadata
        new_route.metadata = first.metadata.copy()
        new_route.metadata.update(second.metadata)
        new_route.metadata.update({
            "type": "VIRTUAL_INTERLINED",
            "modes": list(set([first.metadata.get("mode", "RAIL"), second.metadata.get("mode", "RAIL")])),
            "wait_time_minutes": wait_time.total_seconds() / 60,
            "is_insured": True,
            "engine": "interlining_nexus_v1"
        })
        
        # Calculate new duration
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
