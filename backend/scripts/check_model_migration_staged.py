"""Pre-commit helper: fail commit when ORM models change but no Alembic migration is staged.

This is intentionally lightweight and fast — it checks staged file paths only.

Rules:
- If any staged file path contains `/models` or is `backend/schemas.py`, require at least one staged file
  under `backend/alembic/versions/` in the same commit.
"""
import subprocess
import sys


def get_staged_files():
    p = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"], capture_output=True, text=True)
    if p.returncode != 0:
        print("[pre-commit] could not read staged files")
        sys.exit(0)
    return [line.strip() for line in p.stdout.splitlines() if line.strip()]


def main():
    staged = get_staged_files()
    if not staged:
        return 0

    model_paths = [s for s in staged if ("/models" in s) or s.endswith("models.py") or s.endswith("schemas.py")]
    if not model_paths:
        # nothing to check
        return 0

    migration_staged = any(s.startswith("backend/alembic/versions/") for s in staged)
    if migration_staged:
        return 0

    print("\n[pre-commit] Detected staged ORM/model changes but no Alembic migration is staged.")
    print("Files changed:")
    for p in model_paths:
        print("  -", p)
    print("\nPlease create an Alembic migration and stage it in the same commit:\n")
    print(r"  .venv\Scripts\python -m alembic -c backend/alembic.ini revision --autogenerate -m \"describe changes\"")
    print("\nThen: git add backend/alembic/versions/<new-file>.py and re-commit.")
    print("\nIf this change is intentionally non-schema (pure refactor), add a comment to the commit or run:\n  git commit -n ... to bypass pre-commit (not recommended)")
    sys.exit(1)


if __name__ == "__main__":
    main()
