# Epic 5: Lazy-Loading ML Models & Quantized Inference

This epic transforms our monolithic ML loading into a high-performance, on-demand inference system. It focuses on sub-millisecond execution, shared memory across processes, and graceful degradation.

## The 15 High-Priority Subtasks

1. **Subtask 5.1: Unified Model Loader Interface:** Create an abstract `ModelLoader` that handles JIT hydration from disk, cloud, or mock sources.
2. **Subtask 5.2: Shared Memory Model Pool:** Use `multiprocessing.shared_memory` to store heavy weight matrices, allowing all Uvicorn workers to share one RAM copy instead of duplicating 1GB+ per process.
3. **Subtask 5.3: INT8 Quantization Wrapper:** Implement a NumPy-based quantization layer that forces 8-bit integer math for core inference loops, targeting 4x speedups.
4. **Subtask 5.4: JIT Node Integration:** Register `ML_MODELS` as a node in the `jit_manager` DAG, making it a dependency for Search and Live Status routes.
5. **Subtask 5.5: Predictive Pre-loading:** Link `ShadowWarmer` to pre-fetch model weights into RAM as soon as a user visits the Search or Live Tracking pages.
6. **Subtask 5.6: Lightning-Fast Heuristic Fallback:** If a model takes > 500ms to load JIT, automatically switch to a "Rule-of-Thumb" heuristic (averages) to keep the UI responsive.
7. **Subtask 5.7: ONNX Runtime Bridge:** Implement an optimized execution path using ONNX for hardware acceleration (CPU/SIMD).
8. **Subtask 5.8: Dynamic Inference Batching:** Group individual user requests over 10ms windows into single matrix operations to maximize CPU cache efficiency.
9. **Subtask 5.9: Hot-Swappable Model Registry:** Allow admin-triggered model updates (versioning) without restarting the server using atomic pointer swaps.
10. **Subtask 5.10: LRU Model Eviction:** Automatically unload models from RAM if they remain unused for > 15 minutes, preserving system memory.
11. **Subtask 5.11: Vectorized Feature Pipeline:** Build a high-speed pre-processing pipeline that converts raw API strings into model-ready tensors using NumPy vectorization.
12. **Subtask 5.12: Hardware-Aware Pathing:** Detect AVX-512 or CUDA presence at runtime and lazily select the most efficient model variant.
13. **Subtask 5.13: Drift & Latency Telemetry:** Hook inference results into `jit_metrics` to track prediction confidence and execution time in real-time.
14. **Subtask 5.14: Shadow Mock Generator:** Implement a "Mock Model" mode for development that simulates model output without requiring the massive 100MB+ binary files.
15. **Subtask 5.15: Model Integrity Fingerprinting:** Perform SHA-256 validation during JIT loading to ensure model weights haven't been corrupted on disk.

---

### Implementation Strategy
We will begin by refactoring the current ML files into this new JIT-capable structure, starting with the **Unified Loader** and **Shared Memory Pool**.
