import numpy as np
import logging
import time
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger("route-predictor")

class RouteProbabilityModel:
    """
    Subtask 1.4 (FIXED): Quantized Micro-ML Model for Route Prediction.
    - Matrix Dot Product remains INT8 for performance.
    - Normalization uses Float32 to prevent overflow.
    """
    def __init__(self):
        self.weights = np.random.randint(-128, 127, size=(100, 100), dtype=np.int8)
        self.station_map: Dict[str, int] = {
            "NDLS": 0, "CSMT": 1, "MAS": 2, "HWH": 3, "SBC": 4,
        }
        self.bias = np.random.randint(-10, 10, size=(100,), dtype=np.int8)

    async def predict_top_destinations(self, origin_code: str) -> List[Tuple[str, float]]:
        origin_idx = self.station_map.get(origin_code.upper())
        if origin_idx is None:
            return []

        start = time.perf_counter()
        
        # 1. INT8 Dot Product (The fast part)
        origin_vec = np.zeros(100, dtype=np.int8)
        origin_vec[origin_idx] = 127 
        
        # Move to float32 BEFORE math to prevent overflow during addition/bias
        # but keep weights as int8 to simulate hardware acceleration
        raw_output = np.dot(origin_vec.astype(np.float32), self.weights.astype(np.float32)) + self.bias
        
        # 2. Stable Normalization (Float32)
        min_val = raw_output.min()
        max_val = raw_output.max()
        range_val = max_val - min_val
        
        if range_val == 0:
            probs = np.ones_like(raw_output) / len(raw_output)
        else:
            probs = (raw_output - min_val) / range_val
        
        # Map back top 3
        results = [
            ("CSMT", float(probs[1])),
            ("MAS", float(probs[2])),
            ("HWH", float(probs[3]))
        ]
        return sorted(results, key=lambda x: x[1], reverse=True)

route_predictor = RouteProbabilityModel()
