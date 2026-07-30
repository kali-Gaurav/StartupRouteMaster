"""Compile every backend Python source file and write a single log.

This script intentionally skips virtual environments, cache folders, and other
generated directories so the report focuses on the repository's own source.
"""

from __future__ import annotations

import argparse
import pathlib
import tokenize
import sys
import traceback
from typing import Iterable


SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
}


def iter_python_files(root: pathlib.Path) -> Iterable[pathlib.Path]:
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        yield path


def compile_file(path: pathlib.Path) -> tuple[bool, str]:
    try:
        with tokenize.open(path) as handle:
            source = handle.read()
        compile(source, str(path), "exec")
        return True, "OK"
    except Exception:
        return False, traceback.format_exc()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=pathlib.Path("backend"),
        help="Directory to scan for Python files.",
    )
    parser.add_argument(
        "--log-file",
        type=pathlib.Path,
        default=pathlib.Path("backend") / "logs" / "backend_compile.log",
        help="Where to write the compile report.",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    log_file = args.log_file.resolve()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(iter_python_files(root))
    ok_count = 0
    fail_count = 0

    with log_file.open("w", encoding="utf-8") as handle:
        handle.write(f"Compile root: {root}\n")
        handle.write(f"Python: {sys.executable}\n")
        handle.write(f"Files scanned: {len(files)}\n\n")

        for path in files:
            rel = path.relative_to(root)
            success, message = compile_file(path)
            if success:
                ok_count += 1
                handle.write(f"[OK]   {rel}\n")
            else:
                fail_count += 1
                handle.write(f"[FAIL] {rel}\n")
                handle.write(message)
                if not message.endswith("\n"):
                    handle.write("\n")
                handle.write("\n")

        handle.write("Summary\n")
        handle.write(f"OK: {ok_count}\n")
        handle.write(f"FAIL: {fail_count}\n")

    print(f"Wrote compile report to {log_file}")
    print(f"Files scanned: {len(files)}, OK: {ok_count}, FAIL: {fail_count}")
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
