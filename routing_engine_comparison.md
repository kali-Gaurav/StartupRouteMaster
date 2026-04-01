# 🚦 Routing Engine Comparison Report

**Date:** 2026-03-29 12:34:12
**Test Parameters:** 3 cases, 6 engines.

## Direct (Delhi -> Kota)

| Engine | Latency (ms) | Routes Found | Best Duration (min) | Status |
| :--- | :--- | :--- | :--- | :--- |
| **UltraTurbo** | 30.44 | 20 | 269 | OK |
| **HubTier0** | 39.58 | 15 | 275 | OK |
| **FastPath** | 122.21 | 0 | N/A | OK |
| **Turbo** | 129.40 | 20 | 269 | OK |
| **RAPTOR** | 649.56 | 9 | N/A | OK |
| **TBR** | 18779.64 | 15 | 285 | OK |

## Long (Delhi -> Pune)

| Engine | Latency (ms) | Routes Found | Best Duration (min) | Status |
| :--- | :--- | :--- | :--- | :--- |
| **HubTier0** | 22.44 | 2 | 1610 | OK |
| **UltraTurbo** | 37.43 | 5 | 1194 | OK |
| **TBR** | 81.41 | 2 | 1540 | OK |
| **Turbo** | 92.07 | 5 | 1194 | OK |
| **FastPath** | 151.66 | 0 | N/A | OK |
| **RAPTOR** | 190.58 | 1 | 100 | OK |

## Cross-Country (Mumbai -> Howrah)

| Engine | Latency (ms) | Routes Found | Best Duration (min) | Status |
| :--- | :--- | :--- | :--- | :--- |
| **HubTier0** | 35.01 | 0 | N/A | OK |
| **UltraTurbo** | 57.81 | 9 | 1773 | OK |
| **Turbo** | 94.21 | 9 | 1773 | OK |
| **FastPath** | 381.44 | 0 | N/A | OK |
| **TBR** | 837.36 | 3 | 1795 | OK |
| **RAPTOR** | 896.82 | 10 | N/A | OK |

## 🏆 Recommended Ordering

Based on the benchmarks above, we recommend the following order in the Orchestrator:

1. **HubTier0**: Ultra-fast backbone lookup.
2. **Turbo / UltraTurbo**: Direct and 1-transfer SQL-based high speed search.
3. **TBR (Trip Based Routing)**: Optimized graph search for multi-transfer routes.
4. **RAPTOR**: Discovery engine for complex connectivity.
5. **FastPath**: Final fallback for broad connectivity.
