"""CLI: run a recording plan with Playwright (or dry-run with a mock page).

Usage examples:
  python scripts/record_scene.py --plan examples/irctc_search.json --scene-id irctc_search_001
  python scripts/record_scene.py --plan examples/ntes_schedule.json --scene-id ntes_schedule_001 --dry-run

Notes:
- Requires `playwright` for real browser recordings. Dry-run uses placeholders and runs in CI.
"""
from __future__ import annotations
import argparse
import json
import asyncio
from pathlib import Path
from typing import Any, Dict

from routemaster_agent.data.scene_recorder import SceneRecorder


class MockPage:
    async def screenshot(self, path: str):
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\nMOCK")

    async def content(self):
        return "<html><body>mock page</body></html>"


async def run_plan(plan_path: str, scene_id: str, base_dir: str = "datasets/raw_scenes", dry_run: bool = False):
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    recorder = SceneRecorder(base_dir=base_dir)
    await recorder.start_scene(scene_id, plan.get("meta", {}))

    page = None
    if not dry_run:
        try:
            from playwright.async_api import async_playwright
        except Exception as e:
            raise RuntimeError("playwright is not installed in this environment; run with --dry-run or install Playwright") from e

        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(plan["meta"].get("url"))
    else:
        page = MockPage()

    step_no = 1
    for step in plan.get("steps", []):
        action = step.get("action")
        # perform an action only when not dry-run
        if not dry_run:
            t = action.get("type")
            if t == "input":
                await page.fill(action["selector"], action.get("value", ""))
            elif t == "click":
                await page.click(action["selector"])
            elif t == "wait":
                await page.wait_for_selector(action["selector"], timeout=10000)
        # always record the step (captures screenshot + DOM)
        await recorder.record_step(page, action, step_no)
        step_no += 1

    if not dry_run:
        await context.close()
        await browser.close()
        await pw.stop()

    out = recorder.finish_scene()
    return out


def cli():
    p = argparse.ArgumentParser()
    p.add_argument("--plan", required=True, help="Path to recording plan JSON")
    p.add_argument("--scene-id", required=True, help="scene id to write")
    p.add_argument("--base-dir", default="datasets/raw_scenes")
    p.add_argument("--dry-run", action="store_true", help="Do not launch browser; use mock page")
    args = p.parse_args()
    asyncio.run(run_plan(args.plan, args.scene_id, args.base_dir, args.dry_run))


if __name__ == '__main__':
    cli()
