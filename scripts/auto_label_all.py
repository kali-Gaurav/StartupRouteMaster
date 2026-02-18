"""Batch auto-label all scenes in `datasets/raw_scenes` using SkillTrainer.

Usage:
  python scripts/auto_label_all.py --base datasets/raw_scenes --dry-run

If `--live` is passed the script will import the in-repo `SkillTrainer` and use
Gemini (or the configured LLM). Otherwise it will run in dry-run mode using a
Dummy trainer that echoes a single `complete` action.
"""
from __future__ import annotations
import argparse
import asyncio
from pathlib import Path

from routemaster_agent.data.auto_labeler import auto_label_scene


class DummyTrainer:
    async def propose_actions(self, scene, task):
        return [{"type": "complete", "result": "dummy"}]


async def run(base_dir: str, live: bool = False):
    base = Path(base_dir)
    if not base.exists():
        raise FileNotFoundError(base)

    trainer = None
    if live:
        try:
            from routemaster_agent.ai.skill_trainer import SkillTrainer
            from routemaster_agent.ai.gemini_client import GeminiClient
            # SkillTrainer expects an LLM client; construct a default one if available
            gem = GeminiClient()
            trainer = SkillTrainer(gem)
        except Exception:
            trainer = DummyTrainer()
    else:
        trainer = DummyTrainer()

    for scene_dir in sorted([p for p in base.iterdir() if p.is_dir()]):
        out = await auto_label_scene(scene_dir, trainer=trainer)
        print(f"Labeled: {out}")


def cli():
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="datasets/raw_scenes")
    p.add_argument("--live", action="store_true")
    args = p.parse_args()
    asyncio.run(run(args.base, live=args.live))


if __name__ == '__main__':
    cli()
