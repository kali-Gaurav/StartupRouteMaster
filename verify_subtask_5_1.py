import numpy as np
import os
import sys
import logging

# Ensure backend package is importable
sys.path.append(os.getcwd())

from backend.core.route_engine.graph import MemMapManager
from backend.database.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-5.1")

def test_memmap_functionality():
    # 1. Create a large dummy coordinate matrix (10,000 stops)
    num_stops = 10000
    original_coords = np.random.rand(num_stops, 2).astype(np.float32)
    
    logger.info(f"Generated dummy array: {original_coords.shape}, size: {original_coords.nbytes / 1024:.2f} KB")

    # 2. Save using MemMapManager
    try:
        path = MemMapManager.save_array("test_coords", original_coords)
        logger.info(f"✅ Saved array to: {path}")
        assert os.path.exists(path)
        assert os.path.exists(path + ".meta")

        # 3. Load using MemMapManager
        mapped_coords = MemMapManager.load_array("test_coords")
        
        logger.info(f"Loaded array type: {type(mapped_coords)}")
        assert isinstance(mapped_coords, np.memmap)
        
        # 4. Verify data integrity
        np.testing.assert_array_almost_equal(original_coords, mapped_coords)
        logger.info("✅ Data integrity verified.")

        # 5. Check RAM footprint (conceptual)
        # Standard array is fully in RAM. Memmap is demand-paged.
        logger.info("✅ Subtask 5.1: numpy.memmap integration Verified.")

    finally:
        # Cleanup
        if 'mapped_coords' in locals():
            del mapped_coords # Release file handle
        
        if 'path' in locals() and os.path.exists(path):
            try:
                os.remove(path)
                os.remove(path + ".meta")
            except Exception as e:
                logger.warning(f"Cleanup error (ignoring on Windows): {e}")

if __name__ == "__main__":
    test_memmap_functionality()
