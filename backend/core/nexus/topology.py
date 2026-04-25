import logging
from enum import Enum
from typing import Dict, List, Set, Tuple

logger = logging.getLogger("nexus.topology")

class Region(str, Enum):
    NORTH = "NORTH"   # Delhi Hub
    WEST = "WEST"     # Mumbai Hub
    SOUTH = "SOUTH"   # Chennai Hub
    EAST = "EAST"     # Kolkata Hub
    CENTRAL = "CENTRAL" # Bhopal Hub
    UNKNOWN = "UNKNOWN"

# Strategic Global Hubs for Cross-Shard Stitching
GLOBAL_STITCH_HUBS = {
    "NDLS", "BCT", "CSMT", "MAS", "HWH", "BPL", "NGP", "ET", "MGS", "PNBE"
}

class NexusCartographer:
    """
    [Atomic Task 1] Topology Mapping.
    Maps 8000+ stations to regional shards to enable pruned search spaces.
    """
    
    @staticmethod
    def get_region_for_station(code: str, state_code: str = "") -> Region:
        """
        Heuristic mapping of station state/code to regional shard.
        """
        # [Production Note] In a real 8GB graph, this would be a pre-computed lookup table
        # Northern Shard: DL, HR, PB, UP, UK, JK, HP
        # Western Shard: MH, GJ, RJ, GA
        # Southern Shard: TN, KL, KA, AP, TS
        # Eastern Shard: WB, OR, BR, JH, NE States
        # Central Shard: MP, CG
        
        north = {"DL", "HR", "PB", "UP", "UK", "JK", "HP"}
        west = {"MH", "GJ", "RJ", "GA"}
        south = {"TN", "KL", "KA", "AP", "TS"}
        east = {"WB", "OR", "BR", "JH", "AS", "TR", "MN", "ML"}
        central = {"MP", "CG"}
        
        if state_code in north: return Region.NORTH
        if state_code in west: return Region.WEST
        if state_code in south: return Region.SOUTH
        if state_code in east: return Region.EAST
        if state_code in central: return Region.CENTRAL
        
        return Region.UNKNOWN

class ShardRouter:
    """
    [Atomic Task 2] The Dispatcher.
    Decides which Neural Spine shards handle the search intent.
    """
    
    @staticmethod
    def get_required_shards(src: str, dst: str, src_region: Region, dst_region: Region) -> Set[Region]:
        """
        Determines minimal shard set for a query.
        """
        if src_region == dst_region and src_region != Region.UNKNOWN:
            return {src_region}
            
        # Cross-region always involves the source shard, destination shard, 
        # and Central shard for stitching if they are not adjacent.
        shards = {src_region, dst_region}
        
        # If going North -> South, we almost always need Central (Bhopal/Itarsi)
        if (src_region == Region.NORTH and dst_region == Region.SOUTH) or \
           (src_region == Region.SOUTH and dst_region == Region.NORTH):
            shards.add(Region.CENTRAL)
            
        return {s for s in shards if s != Region.UNKNOWN}

    @staticmethod
    def get_logical_hubs(shards: Set[Region]) -> List[str]:
        """
        Returns relevant stitch hubs for the selected shards.
        """
        # Sample logic: filter GLOBAL_STITCH_HUBS by region proximity
        # (Simplified for Phase 1)
        return list(GLOBAL_STITCH_HUBS)
