import os
import pickle
import logging
import uuid
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("nexus.overflow")

class DiskOverflowManager:
    """
    [Task 87] Swaps large objects to disk when RAM is critically low.
    Optimized for 500MB VPS environments.
    """
    def __init__(self, overflow_dir: str = "/tmp/nexus_overflow"):
        self.overflow_dir = Path(overflow_dir)
        self.overflow_dir.mkdir(parents=True, exist_ok=True)
        self._index = {}

    def swap_out(self, obj: Any, key: Optional[str] = None) -> str:
        """Serializes object to disk and returns a reference key."""
        obj_key = key or str(uuid.uuid4())
        file_path = self.overflow_dir / f"{obj_key}.pkl"
        
        try:
            with open(file_path, 'wb') as f:
                pickle.dump(obj, f)
            self._index[obj_key] = str(file_path)
            # logger.debug(f"💾 [OVERFLOW] Swapped out key '{obj_key}' to disk.")
            return obj_key
        except Exception as e:
            logger.error(f"Failed to swap out object: {e}")
            return None

    def swap_in(self, key: str, delete_after: bool = True) -> Any:
        """Loads object from disk back into RAM."""
        file_path = self._index.get(key)
        if not file_path or not os.path.exists(file_path):
            return None
            
        try:
            with open(file_path, 'rb') as f:
                obj = pickle.load(f)
            
            if delete_after:
                os.remove(file_path)
                del self._index[key]
                
            return obj
        except Exception as e:
            logger.error(f"Failed to swap in object '{key}': {e}")
            return None

    def purge(self):
        """Cleans up all overflow files."""
        for f in self.overflow_dir.glob("*.pkl"):
            try: os.remove(f)
            except: pass
        self._index = {}

# Global Singleton
nexus_overflow = DiskOverflowManager()
