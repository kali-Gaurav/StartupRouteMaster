"""Simple micro-benchmark for the RAPTOR MVP in `RouteEngine`.

Usage:
    python scripts/raptor_benchmark.py --stations 200 --routes 400 --queries 100

The script is intentionally lightweight so it can run in CI as a smoke benchmark.
"""
import sys
from pathlib import Path
import time
import random
import argparse

# Ensure project root is on sys.path so `backend` package is importable when running this script directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# Also add `backend` folder so internal `from config import ...` style imports resolve
_BACKEND_DIR = ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from backend.services.route_engine import route_engine


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
    parser.add_argument("--stations", type=int, default=50)
    parser.add_argument("--route-length", type=int, default=3)
    parser.add_argument("--queries", type=int, default=50)
    args = parser.parse_args()

    print("Building synthetic network...")
    build_synthetic_network(num_stations=args.stations, route_length=args.route_length)
    print(f"Stations: {len(route_engine.stations_map)}, routes: {len(route_engine.route_segments)}")

    # Prepare random queries
    station_names = list(route_engine.station_name_to_id.keys())
    queries = []
    for _ in range(args.queries):
        a, b = random.sample(station_names, 2)
        queries.append((a, b))

    # Run searches and time them
    times = []
    metrics_agg = {
        "labels_generated": [],
        "max_labels_per_stop": [],
        "transfer_expansions": [],
        "binary_search_calls": [],
        "rounds_processed": [],
    }
    for q in queries:
        start = time.perf_counter()
        _ = route_engine.search_routes(q[0], q[1], "2026-02-16")
        times.append(time.perf_counter() - start)
        # collect metrics from the route_engine if available
        m = getattr(route_engine, "_last_metrics", None)
        if m:
            for k in metrics_agg.keys():
                metrics_agg[k].append(m.get(k, 0))

    times_ms = [t * 1000 for t in times]
    median = sorted(times_ms)[len(times_ms)//2]
    mean = sum(times_ms)/len(times_ms)
    output = {
        "total_routes_tested": len(route_engine.route_segments),
        "total_queries": len(times),
        "median_runtime_ms": round(median, 2),
        "avg_runtime_ms": round(mean, 2),
        "max_runtime_ms": round(max(times_ms), 2),
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

    import json
    print(json.dumps(output, indent=2))
