"""Auto-labeler scaffold — uses existing SkillTrainer to prelabel scenes.

The function accepts an optional `trainer` so tests or alternative backends can
be injected. The module writes `labels.json` inside the scene folder.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional


async def auto_label_scene(scene_dir: str | Path, trainer: Optional[object] = None):
    scene_dir = Path(scene_dir)
    scene_json = scene_dir / "scene.json"
    if not scene_json.exists():
        raise FileNotFoundError(scene_json)

    scene = json.loads(scene_json.read_text(encoding="utf-8"))
    # Build a minimal scene object expected by SkillTrainer
    scene_obj = {
        "page": scene.get("meta", {}).get("page", "unknown"),
        "screenshots": [str(scene_dir / s["screenshot"]) for s in scene.get("steps", [])]
    }
    task = scene.get("meta", {}).get("task", {"objective": "unknown"})

    labels = []
    if trainer is not None and hasattr(trainer, "propose_actions"):
        labels = await trainer.propose_actions(scene_obj, task)

    out = scene_dir / "labels.json"
    out.write_text(json.dumps({"scene_id": scene["scene_id"], "labels": labels}, indent=2), encoding="utf-8")
    return str(out)
