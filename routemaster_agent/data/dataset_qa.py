"""Dataset QA utilities for Phase 2.

Provides simple, deterministic checks to validate recorded scenes before labeling
or training. Intended to be run as part of the pipeline or CI.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any


def check_scene(scene_dir: Path, max_steps: int = 12) -> Dict[str, Any]:
    report = {"scene": scene_dir.name, "ok": True, "errors": []}
    scene_json = scene_dir / "scene.json"
    if not scene_json.exists():
        report["ok"] = False
        report["errors"].append("missing scene.json")
        return report

    scene = json.loads(scene_json.read_text(encoding="utf-8"))
    steps = scene.get("steps", [])
    if len(steps) == 0:
        report["ok"] = False
        report["errors"].append("no steps recorded")
    if len(steps) > max_steps:
        report["ok"] = False
        report["errors"].append(f"too many steps ({len(steps)})")

    prev_ts = None
    for s in steps:
        ss = scene_dir / s.get("screenshot", "")
        if not ss.exists():
            report["ok"] = False
            report["errors"].append(f"missing screenshot {s.get('screenshot')}")
        ts = s.get("timestamp")
        if ts is None:
            report["ok"] = False
            report["errors"].append("missing timestamp on step")
        else:
            if prev_ts and ts <= prev_ts:
                report["ok"] = False
                report["errors"].append("timestamps not increasing")
            prev_ts = ts

    return report


def run_qa(dataset_dir: str | Path = "datasets/raw_scenes") -> Dict[str, Any]:
    dataset_dir = Path(dataset_dir)
    results = {"total": 0, "passed": 0, "failed": 0, "details": []}
    if not dataset_dir.exists():
        raise FileNotFoundError(dataset_dir)

    for scene in sorted([p for p in dataset_dir.iterdir() if p.is_dir()]):
        results["total"] += 1
        r = check_scene(scene)
        results["details"].append(r)
        if r["ok"]:
            results["passed"] += 1
        else:
            results["failed"] += 1

    return results


if __name__ == "__main__":
    import sys
    out = run_qa(sys.argv[1] if len(sys.argv) > 1 else "datasets/raw_scenes")
    print(json.dumps(out, indent=2))
