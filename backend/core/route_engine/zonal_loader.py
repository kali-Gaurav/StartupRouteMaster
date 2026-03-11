import numpy as np
import os
import logging
from pathlib import Path
from typing import Dict, Optional
from collections import OrderedDict

logger = logging.getLogger("zonal-loader")

class ZonalGraphLoader:
    """
    Epic 3: Hierarchical Routing Graph Segment Loading.
    Implements MMAP-based on-demand loading of geographical zones.
    """
    def __init__(self, segments_dir: str = "backend/data/graph_segments", max_zones_in_ram: int = 3):
        self.segments_dir = Path(segments_dir)
        self.max_zones = max_zones_in_ram
        # LRU Cache for Zone Data
        self.loaded_zones: OrderedDict[int, np.ndarray] = OrderedDict()
        self.zone_count = 10 # Determined by segment_graph.py

    async def get_zone_data(self, zone_id: int) -> Optional[np.ndarray]:
        """
        Retrieves connections for a specific zone.
        Loads from disk via MMAP if not in cache.
        """
        if zone_id in self.loaded_zones:
            # Move to end (MRU)
            self.loaded_zones.move_to_end(zone_id)
            return self.loaded_zones[zone_id]

        file_path = self.segments_dir / f"zone_{zone_id}.npz"
        if not file_path.exists():
            return None

        try:
            # Subtask 3.2: MMAP Loading for instant access
            # We use mmap_mode='r' to map the file directly into memory space
            data = np.load(file_path, mmap_mode='r')
            connections = data['connections']
            
            # Manage LRU Cache
            if len(self.loaded_zones) >= self.max_zones:
                # Evict oldest (Subtask 3.5)
                evicted_zone, _ = self.loaded_zones.popitem(last=False)
                logger.info(f"♻️  Evicted Zone {evicted_zone} from RAM cache.")

            self.loaded_zones[zone_id] = connections
            logger.info(f"📂 Zone {zone_id} loaded into memory via MMAP.")
            return connections

        except Exception as e:
            logger.error(f"❌ Failed to load Zone {zone_id}: {e}")
            return None

    def get_zone_id_for_stop(self, stop_id: int) -> int:
        """Determines which zone a stop belongs to."""
        # This must match the logic in segment_graph.py
        # For simplicity, we hardcoded 10 zones.
        # REAL FIX: Read zone_metadata.json
        num_zones = 10
        # Approximate max_stop (should be tracked in metadata)
        max_stop = 10000 
        zone_size = (max_stop // num_zones) + 1
        return min(num_zones - 1, stop_id // zone_size)

zonal_loader = ZonalGraphLoader()
