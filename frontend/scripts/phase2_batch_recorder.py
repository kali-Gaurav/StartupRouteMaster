"""Phase 2 Batch Recorder: Records 2,500 labeled scenes across NTES/IRCTC.

This script scales collection by recording multiple scenes in sequence (serial or batch).

Usage:
  python scripts/phase2_batch_recorder.py --target 2500 --batch-ntes 1000 --batch-irctc 1000 --split-live --split-dry-run
  python scripts/phase2_batch_recorder.py --target 100 --dry-run  # Quick pilot

Strategy:
1. Split target into site-based batches (NTES, IRCTC, etc.)
2. For each site, generate realistic task combinations (train numbers, routes, dates)
3. Record scenes in parallel (via asyncio.gather) for speed
4. Auto-label each scene after recording
5. Run QA on all scenes daily
6. Upload to S3 when target reached
"""
from __future__ import annotations
import asyncio
import argparse
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List

from routemaster_agent.data.website_recorder import WebsiteRecorder
from routemaster_agent.data.auto_labeler import auto_label_scene
from routemaster_agent.data.dataset_qa import run_qa


# Task generators for realistic data
NTES_TRAIN_NUMBERS = [
    "12345", "12346", "12347", "14067", "15035", "20501", "20502", "22452", "23047", "24067",
    "13355", "13356", "15704", "15705", "16503", "16504", "18030", "18031", "19037", "19038",
]

IRCTC_ROUTES = [
    ("BANGALORE", "HYDERABAD"),
    ("MUMBAI", "DELHI"),
    ("DELHI", "AGRA"),
    ("JAIPUR", "KOTA"),
    ("HYDERABAD", "BANGALORE"),
    ("BANGALORE", "MYSORE"),
    ("MUMBAI", "PUNE"),
    ("DELHI", "LUCKNOW"),
    ("KOLKATA", "NEW JALPAIGURI"),
    ("CHENNAI", "BANGALORE"),
]


def generate_ntes_tasks(count: int) -> List[Dict]:
    tasks = []
    for i in range(count):
        train_no = NTES_TRAIN_NUMBERS[i % len(NTES_TRAIN_NUMBERS)]
        tasks.append({
            "type": "ntes_schedule",
            "scene_id": f"ntes_{i:04d}",
            "train_no": train_no,
        })
    return tasks


def generate_irctc_tasks(count: int) -> List[Dict]:
    tasks = []
    base_date = datetime.now()
    for i in range(count):
        origin, dest = IRCTC_ROUTES[i % len(IRCTC_ROUTES)]
        date_offset = i % 30
        date_obj = base_date + timedelta(days=date_offset)
        date_str = date_obj.strftime("%d/%m/%Y")
        tasks.append({
            "type": "irctc_search",
            "scene_id": f"irctc_{i:04d}",
            "origin": origin,
            "dest": dest,
            "date": date_str,
        })
    return tasks


async def record_task_batch(tasks: List[Dict], recorder: WebsiteRecorder, dry_run: bool = False, parallel: int = 1):
    """Record a batch of tasks with concurrency control."""
    async def record_one(task):
        try:
            if task["type"] == "ntes_schedule":
                if not dry_run:
                    return await recorder.record_ntes_schedule(task["scene_id"], task["train_no"])
                # dry-run: pretend we recorded
                return f"dry-run: {task['scene_id']}"
            elif task["type"] == "irctc_search":
                if not dry_run:
                    return await recorder.record_irctc_search(task["scene_id"], task["origin"], task["dest"], task["date"])
                return f"dry-run: {task['scene_id']}"
        except Exception as e:
            print(f"  ✗ {task['scene_id']}: {e}")
            return None

    # Record in batches of `parallel` to avoid overwhelming the machine
    results = []
    for i in range(0, len(tasks), parallel):
        batch = tasks[i:i+parallel]
        print(f"  Recording batch {i//parallel + 1}/{(len(tasks)-1)//parallel + 1} ({len(batch)} tasks)...")
        batch_results = await asyncio.gather(*[record_one(t) for t in batch], return_exceptions=True)
        results.extend([r for r in batch_results if r is not None])
    return results


async def run_phase2(target: int, batch_ntes: int, batch_irctc: int, base_dir: str = "datasets/phase2", dry_run: bool = False):
    """Run Phase 2 batch recording."""
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)

    print(f"[PHASE 2] Target: {target} scenes ({batch_ntes} NTES + {batch_irctc} IRCTC)")
    print(f"[PHASE 2] Dry-run: {dry_run}")

    recorder = WebsiteRecorder(base_dir=str(base / "raw_scenes"))

    # Generate tasks
    print("\n[PHASE 2] Generating task lists...")
    ntes_tasks = generate_ntes_tasks(batch_ntes)
    irctc_tasks = generate_irctc_tasks(batch_irctc)
    all_tasks = ntes_tasks + irctc_tasks
    print(f"  ✓ {len(all_tasks)} tasks generated")

    # Record (serial for safety; can be parallelized later)
    print("\n[PHASE 2] Recording...")
    recorded = await record_task_batch(all_tasks, recorder, dry_run=dry_run, parallel=1)
    print(f"  ✓ {len(recorded)} scenes recorded")

    # Auto-label
    print("\n[PHASE 2] Auto-labeling...")
    scenes_dir = base / "raw_scenes"
    labeled = 0
    for scene_dir in sorted([p for p in scenes_dir.iterdir() if p.is_dir()]):
        try:
            await auto_label_scene(scene_dir, trainer=None)
            labeled += 1
        except Exception as e:
            print(f"  ✗ labeling {scene_dir.name}: {e}")
    print(f"  ✓ {labeled} scenes labeled")

    # QA
    print("\n[PHASE 2] Running QA...")
    qa_results = run_qa(scenes_dir)
    print(f"  Total: {qa_results['total']}")
    print(f"  Passed: {qa_results['passed']}")
    print(f"  Failed: {qa_results['failed']}")

    # Report
    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "phase": "Phase 2",
        "target": target,
        "ntes_batch": batch_ntes,
        "irctc_batch": batch_irctc,
        "total_recorded": len(recorded),
        "total_labeled": labeled,
        "qa_results": qa_results,
        "dry_run": dry_run,
    }

    report_path = base / "phase2_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n✅ Phase 2 run complete. Report: {report_path}")
    return report


def cli():
    p = argparse.ArgumentParser()
    p.add_argument("--target", type=int, default=2500, help="Total scenes to collect")
    p.add_argument("--batch-ntes", type=int, default=1250, help="NTES scenes")
    p.add_argument("--batch-irctc", type=int, default=1250, help="IRCTC scenes")
    p.add_argument("--base", default="datasets/phase2")
    p.add_argument("--dry-run", action="store_true", help="Do not launch browser")
    args = p.parse_args()
    asyncio.run(run_phase2(args.target, args.batch_ntes, args.batch_irctc, args.base, args.dry_run))


if __name__ == '__main__':
    cli()
