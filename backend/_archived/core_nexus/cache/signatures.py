import hashlib
import logging
import asyncio
from typing import Optional
from .mmap_cortex import nexus_cortex

logger = logging.getLogger("nexus.cache.signatures")

class SearchDeduplicator:
    """
    [Task 43] Search Signature & Deduplication Engine.
    Uses Mmap bitset to prevent redundant scraper calls across processes.
    """
    
    def _get_hash_idx(self, src: str, dst: str, date: str, quota: str) -> int:
        """Deterministic mapping of search params to a bit index (0-8191)."""
        fingerprint = f"{src}:{dst}:{date}:{quota}".lower()
        hash_val = int(hashlib.md5(fingerprint.encode()).hexdigest(), 16)
        return hash_val % 8192

    async def is_already_processing(self, src: str, dst: str, date: str, quota: str) -> bool:
        """Checks if an identical fiber is already running in another process."""
        idx = self._get_hash_idx(src, dst, date, quota)
        return nexus_cortex.is_in_flight(idx)

    def mark_started(self, src: str, dst: str, date: str, quota: str):
        """Mark search as IN_FLIGHT at L0 layer."""
        idx = self._get_hash_idx(src, dst, date, quota)
        nexus_cortex.mark_in_flight(idx, True)

    def mark_finished(self, src: str, dst: str, date: str, quota: str):
        """Clear IN_FLIGHT bit at L0 layer."""
        idx = self._get_hash_idx(src, dst, date, quota)
        nexus_cortex.mark_in_flight(idx, False)

    async def wait_for_completion(self, src: str, dst: str, date: str, quota: str, timeout: int = 40):
        """Wait for another worker to finish the search (Polls Mmap)."""
        idx = self._get_hash_idx(src, dst, date, quota)
        start = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start < timeout:
             if not nexus_cortex.is_in_flight(idx):
                  return True # Other worker finished
             await asyncio.sleep(0.5)
             
        return False # Timeout

search_dedup = SearchDeduplicator()
