"""Utility CLI for inspecting graph snapshots and hub stats.

Usage (from workspace root):
    python scripts/graph_debug.py [--date YYYY-MM-DD]

If no date is provided, the latest file in the snapshot directory is analysed.
"""
import argparse
import os
import pickle
from datetime import datetime

from backend.core.route_engine.snapshot_manager import SnapshotManager
from backend.core.route_engine.graph import StaticGraphSnapshot


def describe_snapshot(snapshot: StaticGraphSnapshot):
    stops = len(snapshot.stop_cache or {})
    trips = len(snapshot.trip_segments or {})
    transfers = sum(len(v) for v in snapshot.transfer_graph.values())
    patterns = len(snapshot.route_patterns or {})

    print(f"Snapshot date: {snapshot.date}")
    print(f"Stops: {stops}")
    print(f"Trips: {trips}")
    print(f"Transfers: {transfers}")
    print(f"Route patterns: {patterns}")
    print(f"Version: {snapshot.version}")
    print(f"Created at: {snapshot.created_at}")

    if snapshot.transfer_graph:
        max_transfers = max(len(v) for v in snapshot.transfer_graph.values())
        print(f"Max transfers from a stop: {max_transfers}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect graph snapshot files")
    parser.add_argument("--date", help="Date of snapshot (YYYY-MM-DD)")
    args = parser.parse_args()

    mgr = SnapshotManager()
    if args.date:
        date = datetime.fromisoformat(args.date)
        path = mgr._get_snapshot_path(date)
    else:
        # pick most recent snapshot file
        files = [f for f in os.listdir(mgr.snapshot_dir) if f.startswith("graph_snapshot_")]
        if not files:
            print("No snapshots found in", mgr.snapshot_dir)
            exit(1)
        latest = sorted(files)[-1]
        path = os.path.join(mgr.snapshot_dir, latest)

    print("Inspecting", path)
    try:
        with open(path, 'rb') as f:
            snap = pickle.load(f)
        describe_snapshot(snap)
    except Exception as e:
        print("Failed to read snapshot:", e)
