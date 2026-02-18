"""Lightweight Playwright-compatible scene recorder (scaffold).

This module provides a minimal, tested API to capture scene folders that
contain screenshots, DOM and an incremental `scene.json` used by the
labeling / training pipeline.

Design goals:
- Small, well-tested core so Playwright integration can call it
- Dry-run friendly for CI / unit tests
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Any


class SceneRecorder:
    def __init__(self, base_dir: str | Path = "datasets/raw_scenes"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._scene = None
        self._scene_dir = None

    async def start_scene(self, scene_id: str, meta: dict):
        scene_id = self._sanitize_id(scene_id)
        self._scene_dir = self.base_dir / scene_id
        self._scene_dir.mkdir(parents=True, exist_ok=True)
        self._scene = {
            "scene_id": scene_id,
            "meta": meta,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "steps": []
        }
        # persist initial file
        self._write_scene_json()
        return str(self._scene_dir)

    async def record_step(self, page: Optional[Any], action: dict, step: int, metadata: Optional[dict] = None):
        """Record a single step. `page` is a Playwright page-like object.

        - `action` stays as the canonical action descriptor (type/selector/value)
        - `metadata` can include: strategy, selector_confidence, time_to_success_ms, success (bool)

        For unit tests `page` can be a fake with `screenshot(path)` and `content()`.
        """
        assert self._scene is not None, "scene not started"
        screenshot_name = f"step_{step:03d}.png"
        screenshot_path = self._scene_dir / screenshot_name

        # Try to capture a screenshot; fall back to a tiny placeholder for tests
        if page is not None and hasattr(page, "screenshot"):
            await page.screenshot(path=str(screenshot_path))
        else:
            # placeholder PNG header (not a full PNG) — sufficient for tests
            screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\n")

        # capture DOM if available
        dom = ""
        if page is not None and hasattr(page, "content"):
            dom = await page.content()

        # normalize metadata
        meta = metadata or {}
        
        # Ensure timestamps are strictly increasing
        import asyncio
        now = datetime.utcnow().isoformat() + "Z"
        if self._scene["steps"]:
            last_ts = self._scene["steps"][-1]["timestamp"]
            # if same timestamp, wait 1ms and retry
            while now <= last_ts:
                await asyncio.sleep(0.001)
                now = datetime.utcnow().isoformat() + "Z"
        
        step_record = {
            "step": step,
            "action": action,
            "meta": {
                "strategy": meta.get("strategy"),
                "selector_confidence": meta.get("selector_confidence"),
                "time_to_success_ms": meta.get("time_to_success_ms"),
                "success": meta.get("success", True),
            },
            "screenshot": screenshot_name,
            "dom": dom,
            "timestamp": now,
        }
        self._scene["steps"].append(step_record)
        self._write_scene_json()
        return step_record

    def finish_scene(self):
        assert self._scene is not None, "scene not started"
        self._write_scene_json()
        out = self._scene_dir
        self._scene = None
        self._scene_dir = None
        return str(out)

    def _write_scene_json(self):
        p = self._scene_dir / "scene.json"
        p.write_text(json.dumps(self._scene, indent=2), encoding="utf-8")

    @staticmethod
    def _sanitize_id(scene_id: str) -> str:
        return scene_id.replace(" ", "_").lower()


__all__ = ["SceneRecorder"]
