import os
import asyncio
from pathlib import Path
import pytest

from routemaster_agent.testing.runner import TestRunner


pytestmark = pytest.mark.skipif(os.getenv("RMA_RUN_LIVE") is None, reason="Live NTES test disabled unless RMA_RUN_LIVE=1")


def test_runner_live_integration(tmp_path):
    """Integration-style: run real NTES extraction for a small batch and assert artifacts are produced.
    Enable by setting RMA_RUN_LIVE=1 in environment (nightly CI sets this).
    """
    trains = ["11603", "12345"]

    runner = TestRunner(train_numbers=trains, concurrency=2, max_attempts=3, strict=False, save_artifacts=True, output_root=str(tmp_path / "test_output"), log_dir=str(tmp_path / "logs"))
    res = asyncio.run(runner.run())

    assert res["total"] == len(trains)

    # at least one train should have produced artifacts (NTES may be flaky)
    any_artifacts = False
    for r in res["results"]:
        ap = r.get("artifacts_path")
        if not ap:
            continue
        p = Path(ap)
        if not p.exists():
            continue
        if any(p.glob("**/*.html")) or any(p.glob("**/*.png")):
            any_artifacts = True

    assert any_artifacts is True, "Expected HTML/PNG artifacts for at least one train"
