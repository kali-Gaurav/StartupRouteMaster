import numpy as np
import logging
from typing import List, Set, Dict, Tuple
from .zonal_loader import zonal_loader

logger = logging.getLogger("graph-stitcher")

class GraphStitcher:
    """
    Epic 3.6: Boundary Node & Multi-Zonal Stitching Logic.
    Manages connections between geographical zones.
    """
    def __init__(self):
        # Cache of boundary stops: {stop_id: {target_zone_id, ...}}
        self.boundary_stops: Dict[int, Set[int]] = {}
        self.zone_map: Dict[int, List[int]] = {} # zone_id -> [stop_ids]

    async def get_required_zones(self, origin_stop: int, destination_stop: int) -> Set[int]:
        """
        Predicts which zones are likely needed for this search.
        Always returns at least origin and destination zones.
        """
        origin_zone = zonal_loader.get_zone_id_for_stop(origin_stop)
        dest_zone = zonal_loader.get_zone_id_for_stop(destination_stop)
        
        required = {origin_zone, dest_zone}
        
        # Simple heuristic: add intermediate zones if needed
        # (Assuming zones are ordered linearly for this simulation)
        low, high = min(origin_zone, dest_zone), max(origin_zone, dest_zone)
        for z in range(low, high + 1):
            required.add(z)
            
        return required

    async def stitch_active_graph(self, origin_stop: int, destination_stop: int) -> np.ndarray:
        """
        JIT loads all required zones and merges them into a temporary search-graph.
        """
        zone_ids = await self.get_required_zones(origin_stop, destination_stop)
        logger.info(f"🧵 Stitching {len(zone_ids)} zones for route: {origin_stop} -> {destination_stop}")
        
        all_conns = []
        for zid in zone_ids:
            data = await zonal_loader.get_zone_data(zid)
            if data is not None:
                all_conns.append(data)
        
        if not all_conns:
            return np.array([])

        # VITAL: Return a view or concatenated array
        # Subtask 3.11: Concurrent graph stitcher using numpy
        return np.vstack(all_conns)

graph_stitcher = GraphStitcher()
