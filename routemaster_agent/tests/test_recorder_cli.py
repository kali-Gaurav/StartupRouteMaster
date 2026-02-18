"""Unit tests for Playwright recorder CLI and pilot runner."""
import pytest
import asyncio
from pathlib import Path

from scripts.record_scene import run_plan
from scripts.run_pilot import run_pilot


@pytest.mark.asyncio
async def test_record_scene_dry_run(tmp_path):
    """Test recording a plan in dry-run mode."""
    plan_file = tmp_path / "test_plan.json"
    plan_file.write_text(
        """{
            "meta": {"site": "test", "job_type": "demo"},
            "steps": [
                {"action": {"type": "click", "selector": "#test"}},
                {"action": {"type": "input", "selector": "input", "value": "hello"}}
            ]
        }"""
    )

    output_dir = tmp_path / "output"
    scene_dir = await run_plan(str(plan_file), "test_scene_001", base_dir=str(output_dir), dry_run=True)

    assert Path(scene_dir).exists()
    assert (Path(scene_dir) / "scene.json").exists()
    assert (Path(scene_dir) / "step_001.png").exists()
    assert (Path(scene_dir) / "step_002.png").exists()


@pytest.mark.asyncio
async def test_run_pilot_dry_run(tmp_path):
    """Test pilot runner in dry-run mode."""
    report = await run_pilot(num_scenes=5, dry_run=True, base_dir=str(tmp_path))

    assert report["num_scenes"] == 5
    assert report["recorded"] == 5
    assert report["labeled"] == 5
    assert (Path(tmp_path) / "pilot_report.json").exists()
