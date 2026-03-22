import numpy as np
import os
import logging
import json
from pathlib import Path
from typing import Dict, Optional, Any
from collections import OrderedDict

logger = logging.getLogger("lazy-graph-loader")

class LazyGraphLoader:
    """
    Subtask 5.2: Lazy Graph Loader.
    Prevents cold-start RAM spikes by loading graph components on-demand.
    Uses memory mapping and an LRU cache for high-frequency zones.
    """
    def __init__(self, base_dir: str = None, max_zones_in_ram: int = 5):
        from database.config import Config
        self.base_dir = Path(Config.MEMMAP_DIR) / "zones"
        self.max_zones = max_zones_in_ram
        self.loaded_zones: OrderedDict[int, Any] = OrderedDict()
        os.makedirs(self.base_dir, exist_ok=True)
        
        # Load stop mapping for zone resolution
        self.stop_to_idx = {}
        self.num_zones = 10
        self.zone_size = 0
        self._load_metadata()

    def _load_metadata(self):
        try:
            from database.config import Config
            timetable_path = Path(Config.BASE_DIR) / "data" / "timetable.npz"
            if timetable_path.exists():
                data = np.load(timetable_path)
                stop_ids = data['stop_ids']
                self.stop_to_idx = {int(sid): i for i, sid in enumerate(stop_ids)}
                
                max_idx = len(stop_ids) - 1
                self.zone_size = (max_idx // self.num_zones) + 1
                logger.info(f"📂 ZonalLoader: Loaded {len(stop_ids)} stops, zone_size={self.zone_size}")
        except Exception as e:
            logger.error(f"Failed to load zonal metadata: {e}")

    async def prewarm_essential_hubs(self, hub_ids: list):
        """Loads critical hub zones during bootstrap at low priority."""
        for hid in hub_ids:
            zone_id = self.get_zone_id_for_stop(hid)
            await self.get_zone_data(zone_id)

    async def get_zone_data(self, zone_id: int) -> Optional[np.ndarray]:
        """Returns MMAP data for a zone, loading from disk if needed."""
        if zone_id in self.loaded_zones:
            self.loaded_zones.move_to_end(zone_id)
            return self.loaded_zones[zone_id]

        file_path = self.base_dir / f"zone_{zone_id}.dat"
        meta_path = self.base_dir / f"zone_{zone_id}.meta"
        
        if not file_path.exists() or not meta_path.exists():
            return None

        try:
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            
            # Load as MMAP
            data = np.memmap(file_path, dtype=meta['dtype'], mode='r', shape=tuple(meta['shape']))
            
            if len(self.loaded_zones) >= self.max_zones:
                self.loaded_zones.popitem(last=False)
                
            self.loaded_zones[zone_id] = data
            return data
        except Exception as e:
            logger.error(f"LazyLoader error for zone {zone_id}: {e}")
            return None

    def get_zone_id_for_stop(self, stop_id: int) -> int:
        """Determines zone mapping based on timetable index."""
        idx = self.stop_to_idx.get(int(stop_id))
        if idx is None:
            # Fallback if stop not in timetable
            return 0
        return min(self.num_zones - 1, idx // self.zone_size)

lazy_graph_loader = LazyGraphLoader()
