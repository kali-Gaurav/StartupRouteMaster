import logging
import asyncio
from typing import List, Dict, Any, Set, Tuple
from core.data_structures import Route, TransferConnection, ensure_datetime
from datetime import timedelta

logger = logging.getLogger("nexus.merge")

class NexusMergeEngine:
    """
    [Task 4] Hub Stitching (The Weaver).
    Joins regional journey fragments into globally optimal routes.
    """
    
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    async def stitch_cross_shard(self, src_routes: List[Route], dst_routes: List[Route], hub_code: str) -> List[Route]:
        """
        [Atomic Task 4.2] Joins routes from two regions via a common Hub.
        """
        logger.info(f"🧵 [NEXUS:MERGE] Stitching {len(src_routes)} x {len(dst_routes)} routes via Hub: {hub_code}")
        
        merged_results = []
        
        # Cross-product join (Optimized for small-K from shards)
        for r1 in src_routes[:20]: # Only top 20 candidates per shard for memory safety
            for r2 in dst_routes[:20]:
                
                leg1_arr = ensure_datetime(r1.segments[-1].arrival_time)
                leg2_dep = ensure_datetime(r2.segments[0].departure_time)
                
                # Buffer verification
                wait_time = (leg2_dep - leg1_arr).total_seconds() / 60
                
                # Rule: 45m min buffer for cross-shard transfers
                if 45 <= wait_time <= 720: # Cap wait at 12 hours
                    # Merge Logic
                    global_route = Route()
                    for seg in r1.segments: global_route.add_segment(seg)
                    for seg in r2.segments: global_route.add_segment(seg)
                    for trf in r1.transfers: global_route.add_transfer(trf)
                    for trf in r2.transfers: global_route.add_transfer(trf)
                    
                    # Add Hub Transfer record
                    hub_xf = TransferConnection(
                        station_id=0, # Local hub ID to be resolved
                        station_name=hub_code,
                        arrival_time=leg1_arr,
                        departure_time=leg2_dep,
                        duration_minutes=int(wait_time)
                    )
                    global_route.add_transfer(hub_xf)
                    global_route.metadata["shard_merge"] = True
                    global_route.metadata["stitch_hub"] = hub_code
                    
                    merged_results.append(global_route)
                    
                    # Performance Cap
                    if len(merged_results) >= 15:
                        return merged_results
                        
        return merged_results

    @staticmethod
    def calculate_shard_coverage(routes: List[Route]) -> Set[str]:
        """Helper to deduplicate routes by shard origin."""
        return {r.metadata.get("shard", "unknown") for r in routes}
