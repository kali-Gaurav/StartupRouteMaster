"""Small helper to ensure `backend/` is on sys.path for running top-level scripts.

Usage:
  python scripts/bootstrap-python-path.py scripts/raptor_benchmark.py --stations 100

This script prepends the repository root and `backend/` to sys.path then execs the target script
so relative imports like `from backend.config import Config` or `from config import Config`
resolve consistently for development convenience.
"""
import sys
from pathlib import Path
import runpy

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/bootstrap-python-path.py <script-path> [args...]")
        sys.exit(1)

    repo_root = Path(__file__).resolve().parents[1]
    backend_dir = repo_root / "backend"
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    target = sys.argv[1]
    args = sys.argv[2:]

    # Set argv for the target script and run it in its file context
    sys.argv = [target] + args
    runpy.run_path(target, run_name="__main__")
