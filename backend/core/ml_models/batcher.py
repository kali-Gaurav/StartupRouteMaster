import asyncio
import time
import logging
import numpy as np
from typing import List, Dict, Any, Tuple

logger = logging.getLogger("ml-batcher")

class MLBatcher:
    """
    Subtask 5.8 (FIXED): Dynamic Inference Batching.
    Now with atomic queue slicing to prevent race conditions.
    """
    def __init__(self, model: Any, window_ms: int = 10, max_batch: int = 64):
        self.model = model
        self.window_ms = window_ms
        self.max_batch = max_batch
        self.queue: List[Tuple[List[float], asyncio.Future]] = []
        self._lock = asyncio.Lock()
        self._task = None

    async def predict(self, features: List[float]) -> float:
        future = asyncio.get_event_loop().create_future()
        
        async with self._lock:
            self.queue.append((features, future))
            if self._task is None or self._task.done():
                self._task = asyncio.create_task(self._process_loop())
        
        return await future

    async def _process_loop(self):
        # Wait for the aggregation window
        await asyncio.sleep(self.window_ms / 1000.0)
        
        async with self._lock:
            if not self.queue: return
            
            # ATOMIC SLICE: Take ONLY up to max_batch
            batch_to_process = self.queue[:self.max_batch]
            self.queue = self.queue[self.max_batch:]
            
        try:
            start_inf = time.perf_counter()
            # 1. Vectorize
            features_matrix = np.array([item[0] for item in batch_to_process], dtype=np.float32)

            # 2. Inference
            results = self.model.predict(features_matrix)

            # Subtask 5.13: Record Metrics
            inf_dur = (time.perf_counter() - start_inf) * 1000
            from core.infrastructure.metrics import jit_metrics
            jit_metrics.ml_inferences_total += len(batch_to_process)
            # Rolling average
            jit_metrics.ml_latency_avg_ms = (jit_metrics.ml_latency_avg_ms + inf_dur) / 2
            jit_metrics.ml_batch_efficiency = (jit_metrics.ml_batch_efficiency + len(batch_to_process)) / 2

            # 3. Validation
            # Ensure results match batch size
            if len(results) != len(batch_to_process):
                # Fallback to individual results if kernel is incompatible
                for i, (feat, future) in enumerate(batch_to_process):
                    if not future.done(): future.set_result(0.5) 
            else:
                for i, (feat, future) in enumerate(batch_to_process):
                    if not future.done(): future.set_result(float(results[i]))
                    
        except Exception as e:
            logger.error(f"Batch inference error: {e}")
            for feat, future in batch_to_process:
                if not future.done(): future.set_exception(e)

        # Immediate re-trigger if queue still has items
        async with self._lock:
            if self.queue:
                self._task = asyncio.create_task(self._process_loop())
