import numpy as np
import logging
import json
import os
import time
from typing import List, Set, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from .zonal_loader import lazy_graph_loader as zonal_loader

logger = logging.getLogger("graph-stitcher")

@dataclass
class SnapshotMetadata:
    zone_id: int
    station_ids: Set[int]
    file_path: str
    boundary_stations: Set[int] = field(default_factory=set)
    # [Task 26.7] Overlap Buffer (Stations within range of boundary)
    overlap_buffer: Set[int] = field(default_factory=set)

class GraphStitcher:
    """
    [Task 26] Multi-Zonal Route Stitching & Boundary Logic.
    Manages the unification of regional graph snapshots into a searchable entity.
    """
    def __init__(self):
        self.registry: Dict[int, SnapshotMetadata] = {}
        self.connectivity: Dict[int, Set[int]] = {}
        self._is_initialized = False

    def initialize(self, stop_to_zone: Dict[int, int], station_coords: Optional[Dict[int, Tuple[float, float]]] = None):
        """Build the registry and detect boundaries from metadata."""
        zone_to_stops = {}
        for sid, zid in stop_to_zone.items():
            if zid not in zone_to_stops: zone_to_stops[zid] = set()
            zone_to_stops[zid].add(sid)
            
        for zid, stops in zone_to_stops.items():
            self.registry[zid] = SnapshotMetadata(
                zone_id=zid,
                station_ids=stops,
                file_path=f"zone_{zid}.dat"
            )
            
        # [Task 26.2/26.7] Stitcher Boundary Identification with Overlap Buffer
        self._detect_boundaries(station_coords)
        self._is_initialized = True
        logger.info(f"🧵 GraphStitcher: Initialized {len(self.registry)} zones with boundary detection.")

    def _detect_boundaries(self, station_coords: Optional[Dict[int, Tuple[float, float]]] = None):
        """Finds stations that connect multiple zones (Task 26.2/26.7)."""
        all_zones = list(self.registry.keys())
        for i in range(len(all_zones)):
            for j in range(i + 1, len(all_zones)):
                z1, z2 = all_zones[i], all_zones[j]
                
                # 1. Direct Overlaps (Shared Station IDs)
                common = self.registry[z1].station_ids.intersection(self.registry[z2].station_ids)
                
                # 2. [Task 26.7] Proximity Overlaps (Bridges < 2km apart)
                if station_coords:
                    from utils.geo_utils import haversine_distance
                    for s1 in self.registry[z1].station_ids:
                        for s2 in self.registry[z2].station_ids:
                            c1 = station_coords.get(s1)
                            c2 = station_coords.get(s2)
                            if c1 and c2:
                                dist = haversine_distance(c1[0], c1[1], c2[0], c2[1])
                                if dist < 2.0: # 2km buffer
                                    common.add(s1)
                                    common.add(s2)

                if common:
                    self.registry[z1].boundary_stations.update(common)
                    self.registry[z2].boundary_stations.update(common)
                    self.registry[z1].overlap_buffer.update(common)
                    self.registry[z2].overlap_buffer.update(common)
                    
                    if z1 not in self.connectivity: self.connectivity[z1] = set()
                    self.connectivity[z1].add(z2)
                    if z2 not in self.connectivity: self.connectivity[z2] = set()
                    self.connectivity[z2].add(z1)

    async def get_required_zones(self, origin_stop: int, destination_stop: int) -> Set[int]:
        origin_zone = zonal_loader.get_zone_id_for_stop(origin_stop)
        dest_zone = zonal_loader.get_zone_id_for_stop(destination_stop)
        
        if origin_zone == dest_zone:
            return {origin_zone}
            
        queue = [(origin_zone, [origin_zone])]
        visited = {origin_zone}
        
        while queue:
            (curr, path) = queue.pop(0)
            if curr == dest_zone:
                return set(path)
            
            neighbors = self.connectivity.get(curr, set())
            if not neighbors:
                low, high = min(origin_zone, dest_zone), max(origin_zone, dest_zone)
                return {z for z in range(low, high + 1)}

            for nxt in neighbors:
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, path + [nxt]))
                    
        return {origin_zone, dest_zone}

    async def stitch_active_graph(self, origin_stop: int, destination_stop: int) -> np.ndarray:
        """
        [Task 26.6] Unified Graph View with [Task 26.4] Temporal Alignment.
        """
        zone_ids = await self.get_required_zones(origin_stop, destination_stop)
        
        all_conns = []
        # [Task 26.4] Base reference timestamp for alignment
        base_ref_ts = None

        for zid in zone_ids:
            data = await zonal_loader.get_zone_data(zid)
            if data is not None:
                # [Task 26.4] Simple alignment: if timestamps are relative, shift them
                # For now, we assume global UNIX timestamps so no shift is needed.
                # If they were relative to start of week, we'd addzid * week_secs.
                all_conns.append(data)
        
        if not all_conns:
            return np.array([])

        return np.vstack(all_conns)

    def get_zone_id_for_stop(self, stop_id: int) -> int:
        return zonal_loader.get_zone_id_for_stop(stop_id)

graph_stitcher = GraphStitcher()
