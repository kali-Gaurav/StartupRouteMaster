import json
import logging
from typing import Optional, Dict, Any
from .mmap_cortex import nexus_cortex

logger = logging.getLogger("nexus.cache.slabs")

class HotSlabManager:
    """
    [Task 44] Neural Spine Hot-Slabs.
    Stores Top 32 search results directly in Mmap L0 for Zero-Copy delivery.
    """
    
    def __init__(self):
        # Local mapping of hash to slab index
        self._slab_registry: Dict[int, int] = {}
        self._next_slab = 0

    def _get_hash(self, src: str, dst: str, date: str) -> int:
        return hash(f"{src}:{dst}:{date}".lower()) % 1000000

    def store_result(self, src: str, dst: str, date: str, results: list):
        """Pre-bake results into a 1KB binary slab in shared memory."""
        try:
            h = self._get_hash(src, dst, date)
            data_bytes = json.dumps(results[:10]).encode() # Truncate to save space for hot path
            
            if h not in self._slab_registry:
                 self._slab_registry[h] = self._next_slab
                 self._next_slab = (self._next_slab + 1) % 32
            
            slab_idx = self._slab_registry[h]
            nexus_cortex.store_slab(slab_idx, data_bytes)
            # logger.info(f"🔥 [SLABS] Cached hot route {src}->{dst} into Slab {slab_idx}")
        except Exception as e:
            logger.error(f"⚠️ [SLABS] Failed to store slab: {e}")

    def get_result(self, src: str, dst: str, date: str) -> Optional[list]:
        """Fast-Path retrieval from L0 Neural Spine."""
        h = self._get_hash(src, dst, date)
        if h in self._slab_registry:
             slab_idx = self._slab_registry[h]
             data_bytes = nexus_cortex.get_slab(slab_idx)
             if data_bytes:
                  try:
                       return json.loads(data_bytes)
                  except: pass
        return None

hotslab_manager = HotSlabManager()
