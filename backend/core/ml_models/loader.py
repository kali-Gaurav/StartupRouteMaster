import os
import logging
import pickle
import time
import asyncio
import numpy as np
from typing import Dict, Any, Optional, Tuple
from multiprocessing import shared_memory

logger = logging.getLogger("model-loader")

class ModelLoader:
    """
    Subtask 5.6 & 5.10: Optimized JIT Model Loader with Fallback Caching.
    """
    def __init__(self, models_dir: str = "backend/models"):
        self.models_dir = models_dir
        self.loaded_models: Dict[str, Any] = {}
        self.last_used: Dict[str, float] = {}
        self.shared_mem_blocks: Dict[str, shared_memory.SharedMemory] = {}
        self.load_timeout = 0.5 

    async def get_model(self, model_name: str) -> Any:
        """Task 13: Lazy ML Hydration with Low-RAM Fallback."""
        # 1. Trigger JIT (Will skip if in SLIM_MODE)
        from services.jit_manager import jit_manager
        await jit_manager.ensure_ready("ML_MODELS")
        
        # 2. Check memory pressure
        import psutil
        if psutil.virtual_memory().percent > 90:
            logger.warning(f"🚨 Low RAM ({psutil.virtual_memory().percent}%). Bypassing ML for {model_name}.")
            return self._get_heuristic_model(model_name)

        # 3. Check if node was skipped (SLIM_MODE)
        node = jit_manager.nodes.get("ML_MODELS")
        if node and node.state == "READY" and model_name not in self.loaded_models:
            # If it was marked READY but not actually loaded (e.g. skipped)
            # we check if we should still return a heuristic
            if jit_manager.low_power_mode:
                return self._get_heuristic_model(model_name)

        self.last_used[model_name] = time.time()
        
        if model_name in self.loaded_models:
            return self.loaded_models[model_name]

        try:
            # Load with timeout
            model = await asyncio.wait_for(
                self._load_model_jit(model_name), 
                timeout=self.load_timeout
            )
            # CACHE the result (even if it's a fallback)
            self.loaded_models[model_name] = model
            return model
        except asyncio.TimeoutError:
            logger.warning(f"⏳ JIT Load Timeout for {model_name}. Using fallback.")
            fallback = self._get_heuristic_model(model_name)
            self.loaded_models[model_name] = fallback
            return fallback

    async def _load_model_jit(self, model_name: str) -> Any:
        file_path = os.path.join(self.models_dir, f"{model_name}.pkl")
        if not os.path.exists(file_path):
            return self._get_heuristic_model(model_name)

        try:
            with open(file_path, 'rb') as f:
                model_data = pickle.load(f)
            
            if isinstance(model_data, np.ndarray) and model_data.nbytes > 1024 * 1024:
                model_data = self._move_to_shared_memory(model_name, model_data)

            return model_data
        except Exception as e:
            logger.error(f"Error loading {model_name}: {e}")
            return self._get_heuristic_model(model_name)

    def _get_heuristic_model(self, name: str) -> Any:
        class HeuristicModel:
            def predict(self, features: Any):
                return [15.0]
        return HeuristicModel()

    async def run_eviction_worker(self):
        while True:
            await asyncio.sleep(60)
            now = time.time()
            idle_models = [m for m, t in self.last_used.items() if (now - t) > 900]
            for m in idle_models:
                if m in self.loaded_models:
                    del self.loaded_models[m]
                    logger.info(f"♻️  Evicted idle ML model: {m}")
                if m in self.shared_mem_blocks:
                    self.shared_mem_blocks[m].close()
                    try: self.shared_mem_blocks[m].unlink()
                    except: pass
                    del self.shared_mem_blocks[m]

    def _move_to_shared_memory(self, name: str, array: np.ndarray) -> np.ndarray:
        try:
            shm = shared_memory.SharedMemory(name=name, create=True, size=array.nbytes)
            shared_array = np.ndarray(array.shape, dtype=array.dtype, buffer=shm.buf)
            shared_array[:] = array[:]
            self.shared_mem_blocks[name] = shm
            return shared_array
        except Exception:
            return array

    def cleanup(self):
        for shm in self.shared_mem_blocks.values():
            shm.close()
            try: shm.unlink()
            except: pass

model_loader = ModelLoader()
