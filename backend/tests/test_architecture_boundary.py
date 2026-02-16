import pathlib


def test_routemaster_agent_has_no_backend_imports():
    """Guard: `routemaster_agent/` must not import or reference `backend` package."""
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    rma_pkg = repo_root / "routemaster_agent"
    violations = []

    for path in rma_pkg.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "from backend" in text or "import backend" in text:
            violations.append(str(path.relative_to(repo_root)))

    assert not violations, f"Found forbidden `backend` imports inside routemaster_agent: {violations}"
