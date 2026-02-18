import pytest
import asyncio
from pathlib import Path

from routemaster_agent.data.scene_recorder import SceneRecorder


class DummyPage:
    def __init__(self, tmp_dir: Path):
        self.tmp_dir = tmp_dir

    async def screenshot(self, path: str):
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\nPLACEHOLDER")

    async def content(self):
        return "<html><body>dummy</body></html>"


@pytest.mark.asyncio
async def test_scene_recorder_writes_files(tmp_path):
    base = tmp_path / "datasets" / "raw_scenes"
    recorder = SceneRecorder(base_dir=base)

    scene_dir = await recorder.start_scene("Test Scene 1", {"page": "ntes", "job_type": "search"})
    page = DummyPage(tmp_path)

    step = await recorder.record_step(page, {"type": "click", "selector": "#go"}, step=1)
    assert step["action"]["type"] == "click"
    # metadata defaults: success True present
    assert "meta" in step and step["meta"].get("success") is True

    # record a step with explicit metadata
    step2 = await recorder.record_step(page, {"type": "input", "selector": "#q"}, step=2, metadata={"strategy": "css", "selector_confidence": 0.92, "time_to_success_ms": 120, "success": True})
    assert step2["meta"]["strategy"] == "css"
    assert abs(step2["meta"]["selector_confidence"] - 0.92) < 1e-6

    out = recorder.finish_scene()
    scene_path = Path(scene_dir)
    assert (scene_path / "scene.json").exists()
    assert (scene_path / "step_001.png").exists()

    content = (scene_path / "scene.json").read_text(encoding="utf-8")
    assert 'Test Scene 1'.lower().replace(' ', '_') in content
