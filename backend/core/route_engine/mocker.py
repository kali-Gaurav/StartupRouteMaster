import numpy as np
import os
import logging

logger = logging.getLogger(__name__)

def generate_mock_timetable(output_path: str = "backend/data/timetable.npz"):
    """
    Generates a synthetic Indian Railway corridor for testing without a database.
    Corridor: Delhi (1) -> Mathura (2) -> Agra (3) -> Gwalior (4) -> Jhansi (5) -> Bhopal (6)
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # [dep_stop_idx, arr_stop_idx, dep_ts, arr_ts, trip_id]
    # 0: NDLS, 1: MTJ, 2: AGC, 3: GWL, 4: VGLB, 5: BPL
    # Kerala Express Style
    connections = [
        [0, 1, 40000, 45000, 12626], # NDLS to MTJ (11:06 AM)
        [1, 2, 45100, 48000, 12626], # MTJ to AGC
        [2, 3, 48100, 55000, 12626], # AGC to GWL
        [3, 4, 55100, 60000, 12626], # GWL to VGLB
        [4, 5, 60100, 72000, 12626], # VGLB to BPL
        
        # Another train: Shatabdi (Faster)
        [0, 2, 21600, 28000, 12002], # NDLS to AGC (06:00 AM)
        [2, 4, 28100, 36000, 12002], # AGC to VGLB
        [4, 5, 36100, 45000, 12002], # VGLB to BPL
    ]
    
    conn_arr = np.array(connections, dtype=np.int32)
    # Sort by departure time
    conn_arr = conn_arr[conn_arr[:, 2].argsort()]
    
    np.savez_compressed(
        output_path,
        connections=conn_arr,
        stop_ids=np.array([1, 2, 3, 4, 5, 6], dtype=np.int32),
        stop_indices=np.array([0, 1, 2, 3, 4, 5], dtype=np.int32)
    )
    logger.info(f"Mock timetable generated at {output_path}")

if __name__ == "__main__":
    generate_mock_timetable()
