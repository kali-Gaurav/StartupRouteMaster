"""Pilot runner: records 50 scenes (dry-run), auto-labels + QA, generates report.

This is designed to validate the end-to-end collection pipeline before scaling to 2,500.

Usage:
  python scripts/run_pilot.py --num-scenes 50 --dry-run --base datasets/pilot_run
"""
from __future__ import annotations
import asyncio
import argparse
import json
from pathlib import Path
from datetime import datetime

from routemaster_agent.data.scene_recorder import SceneRecorder
from routemaster_agent.data.auto_labeler import auto_label_scene
from routemaster_agent.data.dataset_qa import run_qa
from routemaster_agent.data.playwright_plans import ALL_PLANS


class MockPage:
    async def screenshot(self, path: str):
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\nPILOT")

    async def content(self):
        return "<html><body>pilot mock</body></html>"


async def run_pilot(num_scenes: int, dry_run: bool, base_dir: str):
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)

    print(f"[PILOT] Recording {num_scenes} scenes (dry_run={dry_run})...")
    scenes_dir = base / "raw_scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)

    # Record scenes
    recorded = []
    for i in range(num_scenes):
        plan_path = ALL_PLANS[i % len(ALL_PLANS)]
        plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))

        scene_id = f"pilot_{i:03d}"
        recorder = SceneRecorder(base_dir=scenes_dir)
        await recorder.start_scene(scene_id, plan.get("meta", {}))

        page = MockPage()
        for step_no, step in enumerate(plan.get("steps", []), 1):
            await recorder.record_step(page, step.get("action"), step_no)

        out = recorder.finish_scene()
        recorded.append(out)
        print(f"  ✓ {scene_id}")

    # Auto-label
    print(f"\n[PILOT] Auto-labeling {num_scenes} scenes...")
    trainer = None  # will use DummyTrainer in auto_label_scene
    labeled = 0
    for scene_dir in sorted([p for p in scenes_dir.iterdir() if p.is_dir()]):
        try:
            await auto_label_scene(scene_dir, trainer=None)  # dry-run uses Dummy
            labeled += 1
        except Exception as e:
            print(f"  ✗ labeling error in {scene_dir.name}: {e}")

    # QA
    print(f"\n[PILOT] Running QA on {num_scenes} scenes...")
    qa_results = run_qa(scenes_dir)
    print(f"  Total: {qa_results['total']}")
    print(f"  Passed: {qa_results['passed']}")
    print(f"  Failed: {qa_results['failed']}")

    # Write report
    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "num_scenes": num_scenes,
        "dry_run": dry_run,
        "recorded": len(recorded),
        "labeled": labeled,
        "qa_results": qa_results,
    }

    report_path = base / "pilot_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n✅ Pilot complete. Report: {report_path}")
    return report


def cli():
    p = argparse.ArgumentParser()
    p.add_argument("--num-scenes", type=int, default=50)
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--base", default="datasets/pilot_run")
    args = p.parse_args()
    asyncio.run(run_pilot(args.num_scenes, args.dry_run, args.base))


if __name__ == '__main__':
    cli()
