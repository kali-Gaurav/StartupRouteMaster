"""Extended micro-benchmark for the RAPTOR MVP with ML integration.

Usage:
    python scripts/raptor_benchmark.py --stations 2000 --route-length 8 --queries 1000 --ml-enabled

The script measures performance with and without ML integration.
"""
import sys
from pathlib import Path
import time
import random
import argparse
import psutil
import os
from datetime import datetime

# Ensure project root is on sys.path so `backend` package is importable when running this script directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# Also add `backend` folder so internal `from config import ...` style imports resolve
_BACKEND_DIR = ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from backend.services.route_engine import route_engine
from backend.config import Config
from backend.services.cache_service import cache_service
from backend.utils.metrics import RMA_CACHE_HIT_TOTAL, RMA_CACHE_MISS_TOTAL
import logging
logger = logging.getLogger(__name__)


def build_synthetic_network(num_stations: int = 50, route_length: int = 3):
    route_engine.stations_map = {}
    route_engine.station_name_to_id = {}
    route_engine.segments_map = {}
    route_engine.route_segments = {}

    # create stations
    for i in range(num_stations):
        sid = f"S{i}"
        name = f"Station{i}"
        route_engine.stations_map[sid] = {"name": name, "lat": 0.0, "lon": 0.0}
        route_engine.station_name_to_id[name.lower()] = sid

    seg_id = 0
    # create simple linear routes connecting random stations
    for r in range(num_stations // route_length):
        route_id = f"route_r{r}"
        segments = []
        start = r * route_length
        for j in range(route_length - 1):
            src = f"S{start + j}"
            dst = f"S{start + j + 1}"
            seg = {
                "id": f"seg{seg_id}",
                "source_station_id": src,
                "dest_station_id": dst,
                "departure": "08:00",
                "arrival": "09:00",
                "duration": 60,
                "cost": 50.0,
                "operating_days": "1111111",
                "mode": "train",
                "vehicle_id": f"v{r}",
            }
            route_engine.segments_map[seg["id"]] = seg
            segments.append(seg)
            seg_id += 1
        route_engine.route_segments[route_id] = segments

    route_engine._is_loaded = True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stations", type=int, default=2000)
    parser.add_argument("--route-length", type=int, default=8)
    parser.add_argument("--queries", type=int, default=1000)
    parser.add_argument("--ml-enabled", action="store_true", default=True, help="Enable ML ranking")
    parser.add_argument("--compare-ml", action="store_true", help="Compare with and without ML")
    args = parser.parse_args()

    print(f"Running extended RAPTOR benchmark: stations={args.stations}, route_length={args.route_length}, queries={args.queries}")
    print(f"ML enabled: {args.ml_enabled}")

    # Build synthetic network
    print("Building synthetic network...")
    build_synthetic_network(num_stations=args.stations, route_length=args.route_length)
    print(f"Stations: {len(route_engine.stations_map)}, routes: {len(route_engine.route_segments)}")

    # Prepare random queries
    station_names = list(route_engine.station_name_to_id.keys())
    queries = []
    for _ in range(args.queries):
        a, b = random.sample(station_names, 2)
        queries.append((a, b))

    def run_benchmark(ml_enabled=True):
        """Run benchmark with ML enabled/disabled"""
        # Temporarily disable ML if needed
        if not ml_enabled:
            # Monkey patch to disable ML ranking
            original_rank = route_engine.search_routes
            def search_without_ml(source, destination, travel_date, budget_category=None):
                if not route_engine._is_loaded:
                    raise RuntimeError("RouteEngine graph is not loaded.")

                cache_key = f"route:{source}:{destination}:{travel_date}:{budget_category}:{getattr(Config, 'MAX_TRANSFERS', Config.MAX_TRANSFERS)}"
                if cache_service.is_available():
                    cached = cache_service.get(cache_key)
                    if cached:
                        try:
                            RMA_CACHE_HIT_TOTAL.inc()
                        except Exception:
                            pass
                        return cached
                    else:
                        try:
                            RMA_CACHE_MISS_TOTAL.inc()
                        except Exception:
                            pass

                source_station_id = route_engine.station_name_to_id.get(source.lower())
                dest_station_id = route_engine.station_name_to_id.get(destination.lower())
                if not source_station_id or not dest_station_id:
                    return []

                try:
                    date_obj = datetime.strptime(travel_date, "%Y-%m-%d").date()
                except ValueError:
                    logger.warning("Invalid travel_date format: %s", travel_date)
                    return []

                raw_paths = route_engine._raptor_mvp(source_station_id, dest_station_id, date_obj, max_rounds=Config.MAX_TRANSFERS)
                routes = [route_engine._construct_route_from_segment_list(source, destination, p, travel_date, budget_category) for p in raw_paths]
                routes = [r for r in routes if r]

                budget_limits = {"economy": 1000, "standard": 2000, "premium": 5000}
                max_budget = budget_limits.get(budget_category, float("inf"))
                if budget_category and budget_category != "all":
                    routes = [r for r in routes if r["total_cost"] <= max_budget]

                routes.sort(key=lambda r: (r["total_duration_minutes"], r["total_cost"]))

                if cache_service.is_available():
                    ttl = getattr(Config, 'ROUTE_CACHE_TTL_SECONDS', getattr(Config, 'CACHE_TTL_SECONDS', 600))
                    cache_service.set(cache_key, routes, ttl_seconds=ttl)

                return routes
            
            route_engine.search_routes = search_without_ml

        # Measure initial memory
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Run searches and time them
        times = []
        metrics_agg = {
            "labels_generated": [],
            "max_labels_per_stop": [],
            "transfer_expansions": [],
            "binary_search_calls": [],
            "rounds_processed": [],
        }
        
        start_time = time.time()
        for q in queries:
            query_start = time.perf_counter()
            _ = route_engine.search_routes(q[0], q[1], "2026-02-16")
            times.append(time.perf_counter() - query_start)
            # collect metrics from the route_engine if available
            m = getattr(route_engine, "_last_metrics", None)
            if m:
                for k in metrics_agg.keys():
                    metrics_agg[k].append(m.get(k, 0))
        
        total_time = time.time() - start_time
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_delta = final_memory - initial_memory

        times_ms = [t * 1000 for t in times]
        median = sorted(times_ms)[len(times_ms)//2]
        p95 = sorted(times_ms)[int(len(times_ms) * 0.95)]
        mean = sum(times_ms)/len(times_ms)
        
        result = {
            "ml_enabled": ml_enabled,
            "total_time_seconds": round(total_time, 2),
            "total_queries": len(times),
            "median_runtime_ms": round(median, 3),
            "p95_runtime_ms": round(p95, 3),
            "avg_runtime_ms": round(mean, 3),
            "max_runtime_ms": round(max(times_ms), 3),
            "memory_initial_mb": round(initial_memory, 2),
            "memory_final_mb": round(final_memory, 2),
            "memory_delta_mb": round(memory_delta, 2),
            "qps": round(len(times) / total_time, 2),
            "metrics": {
                "labels_generated_avg": round(sum(metrics_agg["labels_generated"])/len(metrics_agg["labels_generated"]) if metrics_agg["labels_generated"] else 0, 2),
                "labels_generated_max": max(metrics_agg["labels_generated"]) if metrics_agg["labels_generated"] else 0,
                "max_labels_per_stop_avg": round(sum(metrics_agg["max_labels_per_stop"])/len(metrics_agg["max_labels_per_stop"]) if metrics_agg["max_labels_per_stop"] else 0, 2),
                "max_labels_per_stop_max": max(metrics_agg["max_labels_per_stop"]) if metrics_agg["max_labels_per_stop"] else 0,
                "transfer_expansions_avg": round(sum(metrics_agg["transfer_expansions"])/len(metrics_agg["transfer_expansions"]) if metrics_agg["transfer_expansions"] else 0, 2),
                "transfer_expansions_max": max(metrics_agg["transfer_expansions"]) if metrics_agg["transfer_expansions"] else 0,
                "binary_search_calls_avg": round(sum(metrics_agg["binary_search_calls"])/len(metrics_agg["binary_search_calls"]) if metrics_agg["binary_search_calls"] else 0, 2),
                "binary_search_calls_max": max(metrics_agg["binary_search_calls"]) if metrics_agg["binary_search_calls"] else 0,
                "rounds_processed_avg": round(sum(metrics_agg["rounds_processed"])/len(metrics_agg["rounds_processed"]) if metrics_agg["rounds_processed"] else 0, 2),
                "rounds_processed_max": max(metrics_agg["rounds_processed"]) if metrics_agg["rounds_processed"] else 0,
            }
        }
        
        # Restore original method if we patched it
        if not ml_enabled:
            route_engine.search_routes = original_rank
            
        return result

    # Run benchmark
    if args.compare_ml:
        print("Running comparison: ML enabled vs disabled...")
        result_with_ml = run_benchmark(ml_enabled=True)
        result_without_ml = run_benchmark(ml_enabled=False)
        
        output = {
            "benchmark_config": {
                "stations": args.stations,
                "route_length": args.route_length,
                "queries": args.queries,
                "max_transfers": 3
            },
            "with_ml": result_with_ml,
            "without_ml": result_without_ml,
            "comparison": {
                "latency_overhead_ms": round(result_with_ml["median_runtime_ms"] - result_without_ml["median_runtime_ms"], 3),
                "memory_overhead_mb": round(result_with_ml["memory_delta_mb"] - result_without_ml["memory_delta_mb"], 2),
                "qps_impact": round(result_with_ml["qps"] - result_without_ml["qps"], 2)
            }
        }
    else:
        result = run_benchmark(ml_enabled=args.ml_enabled)
        output = {
            "benchmark_config": {
                "stations": args.stations,
                "route_length": args.route_length,
                "queries": args.queries,
                "max_transfers": 3,
                "ml_enabled": args.ml_enabled
            },
            **result
        }

    import json
    print(json.dumps(output, indent=2))
