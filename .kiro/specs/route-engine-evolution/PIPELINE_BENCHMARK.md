# Route Engine Evolution - Pipeline Latency Benchmark

**Target:** 700ms for fully AI-enriched routes  
**Owner:** SIGMA (Backend Lead)  
**Status:** 🔄 IN PROGRESS  
**Date:** 2026-05-08

---

## Benchmark Strategy

### Pipeline Stages and Targets

| Stage | Target | Cumulative | Description |
|-------|--------|------------|-------------|
| QPO | 50ms | 50ms | Query Plan Optimizer analysis |
| RAPTOR | 500ms | 550ms | Route search and ranking |
| TIS | 100ms | 650ms | Transfer Intelligence scoring |
| Safety | 50ms | 700ms | Corridor safety filtering |
| SSE Stream | 0ms | 700ms | Progressive delivery |

### Test Scenarios

1. **Best Case:** Popular corridor (NDLS-BCT), direct route, no transfers
2. **Average Case:** Medium traffic corridor, one transfer
3. **Worst Case:** Low traffic corridor, multiple transfers

---

## Benchmark Script

```python
"""
Pipeline Latency Benchmark Script

Usage:
    python benchmark_pipeline.py --iterations 100 --corridor NDLS-BCT
"""

import asyncio
import time
import statistics
import argparse
from datetime import datetime
from typing import List, Dict, Any

from backend.services.routing.query_plan_optimizer import QueryPlanOptimizer, QueryContext
from backend.services.routing.transfer_intelligence import TransferIntelligenceService
from backend.services.routing.corridor_safety_bus import CorridorSafetyBus
from backend.services.routing.unified_route_service import UnifiedRouteService


class PipelineBenchmark:
    """Benchmark the tiered intelligence pipeline"""
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
    
    async def benchmark_full_pipeline(
        self,
        source: str,
        destination: str,
        travel_date: str,
        iterations: int = 100
    ) -> Dict[str, Any]:
        """Run full pipeline benchmark"""
        print(f"\n{'='*60}")
        print(f"Benchmarking: {source} → {destination}")
        print(f"Iterations: {iterations}")
        print(f"{'='*60}\n")
        
        stage_times = {
            "qpo": [],
            "raptor": [],
            "tis": [],
            "safety": [],
            "total": []
        }
        
        for i in range(iterations):
            iteration_result = await self._run_single_iteration(
                source, destination, travel_date
            )
            
            for stage, duration in iteration_result["stage_times"].items():
                stage_times[stage].append(duration)
            
            stage_times["total"].append(iteration_result["total_time"])
            
            if (i + 1) % 10 == 0:
                print(f"  Completed: {i + 1}/{iterations}")
        
        return self._calculate_statistics(stage_times)
    
    async def _run_single_iteration(
        self,
        source: str,
        destination: str,
        travel_date: str
    ) -> Dict[str, Any]:
        """Run a single pipeline iteration"""
        start_time = time.perf_counter()
        stage_times = {}
        
        # Stage 1: Query Plan Optimizer
        qpo_start = time.perf_counter()
        optimizer = QueryPlanOptimizer()
        context = QueryContext(
            source=source,
            destination=destination,
            travel_date=travel_date
        )
        plan = await optimizer.create_query_plan(context)
        stage_times["qpo"] = (time.perf_counter() - qpo_start) * 1000
        
        # Stage 2: RAPTOR Route Search
        raptor_start = time.perf_counter()
        service = UnifiedRouteService()
        routes = await service.search_routes(
            UnifiedRouteRequest(
                source=source,
                destination=destination,
                travel_date=travel_date,
                max_routes=10
            )
        )
        stage_times["raptor"] = (time.perf_counter() - raptor_start) * 1000
        
        # Stage 3: Transfer Intelligence Scoring
        tis_start = time.perf_counter()
        tis_service = TransferIntelligenceService()
        for route in routes[:5]:  # Score top 5 routes
            if len(route.journey.segments) > 1:
                # Score each transfer
                for j in range(len(route.journey.segments) - 1):
                    arrival = route.journey.segments[j]
                    departure = route.journey.segments[j + 1]
                    await tis_service.calculate_transfer_score(
                        transfer_station=arrival.to_station_code,
                        arrival_train=arrival.train_number,
                        departure_train=departure.train_number,
                        connection_time_minutes=30
                    )
        stage_times["tis"] = (time.perf_counter() - tis_start) * 1000
        
        # Stage 4: Safety Check
        safety_start = time.perf_counter()
        safety_bus = CorridorSafetyBus()
        await safety_bus.get_corridor_safety(source, destination)
        stage_times["safety"] = (time.perf_counter() - safety_start) * 1000
        
        total_time = (time.perf_counter() - start_time) * 1000
        
        return {
            "total_time": total_time,
            "stage_times": stage_times,
            "routes_found": len(routes)
        }
    
    def _calculate_statistics(
        self,
        stage_times: Dict[str, List[float]]
    ) -> Dict[str, Any]:
        """Calculate statistics for benchmark results"""
        stats = {}
        
        for stage, times in stage_times.items():
            if times:
                stats[stage] = {
                    "count": len(times),
                    "min_ms": round(min(times), 2),
                    "max_ms": round(max(times), 2),
                    "avg_ms": round(statistics.mean(times), 2),
                    "p50_ms": round(statistics.median(times), 2),
                    "p95_ms": round(
                        sorted(times)[int(len(times) * 0.95)], 2
                    ) if len(times) > 1 else round(max(times), 2),
                    "p99_ms": round(
                        sorted(times)[int(len(times) * 0.99)], 2
                    ) if len(times) > 1 else round(max(times), 2),
                    "std_dev": round(statistics.stdev(times), 2) if len(times) > 1 else 0
                }
        
        return stats
    
    def print_results(self, results: Dict[str, Any]):
        """Print benchmark results"""
        print(f"\n{'='*60}")
        print("BENCHMARK RESULTS")
        print(f"{'='*60}\n")
        
        # Target comparison
        total_avg = results["total"]["avg_ms"]
        target = 700
        
        print(f"Target: {target}ms")
        print(f"Actual: {total_avg}ms")
        print(f"Status: {'✅ PASS' if total_avg <= target else '❌ FAIL'}")
        print(f"Difference: {total_avg - target:+.2f}ms\n")
        
        # Stage breakdown
        print("Stage Breakdown:")
        print("-" * 60)
        print(f"{'Stage':<15} {'Avg (ms)':<12} {'P95 (ms)':<12} {'Target':<12} {'Status'}")
        print("-" * 60)
        
        stage_targets = {
            "qpo": 50,
            "raptor": 500,
            "tis": 100,
            "safety": 50,
            "total": 700
        }
        
        for stage in ["qpo", "raptor", "tis", "safety", "total"]:
            if stage in results:
                avg = results[stage]["avg_ms"]
                p95 = results[stage]["p95_ms"]
                target = stage_targets.get(stage, 0)
                status = "✅" if avg <= target else "❌"
                print(f"{stage.upper():<15} {avg:<12.2f} {p95:<12.2f} {target:<12} {status}")
        
        print("-" * 60)
        
        # Recommendations
        print("\nRecommendations:")
        slowest_stage = min(
            [s for s in ["qpo", "raptor", "tis", "safety"] if s in results],
            key=lambda s: results[s]["avg_ms"]
        )
        
        if results["total"]["avg_ms"] > 700:
            print(f"  - {slowest_stage.upper()} is the bottleneck")
            print(f"  - Consider optimizing {slowest_stage} or adding caching")
        
        if results["total"]["p95_ms"] > 1000:
            print("  - P95 latency exceeds 1s")
            print("  - Consider circuit breakers for graceful degradation")
        
        print()


async def main():
    """Main benchmark runner"""
    parser = argparse.ArgumentParser(description="Pipeline Latency Benchmark")
    parser.add_argument("--iterations", type=int, default=100, help="Number of iterations")
    parser.add_argument("--corridor", type=str, default="NDLS-BCT", help="Corridor to benchmark")
    args = parser.parse_args()
    
    source, destination = args.corridor.split("-")
    travel_date = "2026-05-15"
    
    benchmark = PipelineBenchmark()
    results = await benchmark.benchmark_full_pipeline(
        source=source,
        destination=destination,
        travel_date=travel_date,
        iterations=args.iterations
    )
    
    benchmark.print_results(results)
    
    # Save results to file
    import json
    timestamp = datetime.utcnow().isoformat()
    with open(f"benchmark_results_{timestamp}.json", "w") as f:
        json.dump({
            "timestamp": timestamp,
            "corridor": args.corridor,
            "iterations": args.iterations,
            "results": results
        }, f, indent=2)
    
    print(f"Results saved to benchmark_results_{timestamp}.json")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Expected Results

### Best Case (NDLS-BCT, Direct Route)

| Stage | Target | Expected | Status |
|-------|--------|----------|--------|
| QPO | 50ms | 30-40ms | ✅ |
| RAPTOR | 500ms | 400-500ms | ✅ |
| TIS | 100ms | 50-80ms | ✅ |
| Safety | 50ms | 20-30ms | ✅ |
| **Total** | **700ms** | **500-650ms** | **✅** |

### Average Case (Medium Traffic Corridor)

| Stage | Target | Expected | Status |
|-------|--------|----------|--------|
| QPO | 50ms | 40-50ms | ✅ |
| RAPTOR | 500ms | 500-600ms | ⚠️ |
| TIS | 100ms | 80-120ms | ⚠️ |
| Safety | 50ms | 30-40ms | ✅ |
| **Total** | **700ms** | **650-810ms** | **⚠️** |

### Worst Case (Low Traffic, Multi-Transfer)

| Stage | Target | Expected | Status |
|-------|--------|----------|--------|
| QPO | 50ms | 50-60ms | ⚠️ |
| RAPTOR | 500ms | 700-900ms | ❌ |
| TIS | 100ms | 150-200ms | ❌ |
| Safety | 50ms | 40-50ms | ✅ |
| **Total** | **700ms** | **940-1210ms** | **❌** |

---

## Optimization Strategies

### If QPO is Slow (>50ms)
- Add corridor traffic cache
- Pre-compute hub priorities for popular routes
- Use Redis for O(1) corridor lookups

### If RAPTOR is Slow (>500ms)
- Add read replica routing for popular corridors
- Implement query result caching
- Consider async parallel search

### If TIS is Slow (>100ms)
- Cache transfer success rates
- Batch TIS scoring for multiple routes
- Skip TIS for direct routes (no transfers)

### If Safety is Slow (>50ms)
- Cache corridor status (5-minute TTL)
- Use materialized views for safety aggregates
- Reduce safety check frequency

---

## Graceful Degradation

If total latency exceeds 1 second, implement circuit breakers:

```python
async def search_routes_with_fallback(request: UnifiedRouteRequest) -> List[EnrichedRoute]:
    """Search routes with fallback for slow pipeline"""
    try:
        # Try full pipeline with timeout
        routes = await asyncio.wait_for(
            full_pipeline_search(request),
            timeout=1.0  # 1 second timeout
        )
        return routes
    except asyncio.TimeoutError:
        # Fallback: Skip TIS scoring for speed
        routes = await fast_pipeline_search(request)
        return routes
```

---

## Running the Benchmark

```bash
# Install dependencies
pip install -r requirements.txt

# Run benchmark
python benchmark_pipeline.py --iterations 100 --corridor NDLS-BCT

# Run with different corridors
python benchmark_pipeline.py --iterations 50 --corridor NDLS-CNB
python benchmark_pipeline.py --iterations 50 --corridor MAS-COK

# Run all scenarios
python benchmark_pipeline.py --iterations 100 --corridor NDLS-BCT
python benchmark_pipeline.py --iterations 100 --corridor BCT-ADI
python benchmark_pipeline.py --iterations 100 --corridor LKO-DDN
```

---

## Success Criteria

| Metric | Target | Acceptable | Fail |
|--------|--------|------------|------|
| P50 Latency | < 700ms | < 800ms | > 800ms |
| P95 Latency | < 1000ms | < 1200ms | > 1200ms |
| P99 Latency | < 1500ms | < 2000ms | > 2000ms |
| Success Rate | > 99% | > 95% | < 95% |

---

## Action Items

| ID | Action | Owner | Status |
|----|--------|-------|--------|
| BM-01 | Run benchmark on staging | SIGMA | 🔴 PENDING |
| BM-02 | Optimize slow stages | SIGMA | 🔴 PENDING |
| BM-03 | Implement circuit breakers | SIGMA | 🔴 PENDING |
| BM-04 | Add monitoring dashboards | VERA | 🔴 PENDING |
| BM-05 | Set up alerts for latency | VERA | 🔴 PENDING |

---

**Document Version:** 1.0  
**Next Review:** 2026-05-15