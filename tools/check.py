#!/usr/bin/env python3
"""Run the same bounded, offline repository checks locally and in CI."""

from __future__ import annotations

import argparse
import ast
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def has_cli(path: Path) -> bool:
    if path.name.startswith("test_"):
        return False
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return any(isinstance(node, ast.Compare) and isinstance(node.left, ast.Name)
               and node.left.id == "__name__" and any(isinstance(value, ast.Constant)
               and value.value == "__main__" for value in node.comparators) for node in ast.walk(tree))


def test_directories(root: Path) -> list[Path]:
    candidates = [root / "tools/tests"]
    candidates.extend(path / name for path in sorted((root / "skills").iterdir()) if path.is_dir() for name in ("scripts", "tests"))
    return [path for path in candidates if any(path.glob("test_*.py"))]


def run(command: list[str], env: dict, timeout: int = 180, quiet: bool = False) -> None:
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=quiet, text=True, timeout=timeout)
    if result.returncode:
        if quiet:
            print(result.stdout, end="")
            print(result.stderr, end="", file=sys.stderr)
        raise RuntimeError(f"exit {result.returncode}: {' '.join(command)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--swift", action="store_true", help="also typecheck all native macOS helpers")
    args = parser.parse_args()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    python = sys.executable
    try:
        print("Checking prerequisites and source packages", flush=True)
        run([python, "tools/doctor.py", "--dev", *(["--swift"] if args.swift else [])], env)
        run([python, "tools/validate_skills.py"], env)
        with tempfile.TemporaryDirectory(prefix="ai-video-check-") as temporary:
            compile_env = dict(env, PYTHONPYCACHEPREFIX=str(Path(temporary) / "pycache"))
            run([python, "-m", "compileall", "-q", "skills", "tools"], compile_env)
            scripts = sorted([*ROOT.glob("skills/**/*.py"), *ROOT.glob("tools/*.py")])
            entries = [path for path in scripts if path != Path(__file__).resolve() and has_cli(path)]
            for path in entries:
                run([python, str(path), "--help"], env, timeout=30, quiet=True)
            print(f"Validated {len(entries)} CLI help entrypoints; helper/test modules were compiled only.", flush=True)
            groups = test_directories(ROOT)
            for directory in groups:
                print(f"Tests: {directory.relative_to(ROOT)}", flush=True)
                run([python, "-m", "unittest", "discover", "-s", str(directory), "-p", "test_*.py"], env)
            if args.swift:
                swift_sources = sorted(ROOT.glob("skills/**/*.swift"))
                for path in swift_sources:
                    print(f"Swift: {path.relative_to(ROOT)}", flush=True)
                    run(["xcrun", "swiftc", "-typecheck", "-module-cache-path", str(Path(temporary) / "swift-cache"), str(path)], env)
            run(["git", "diff", "--check"], env)
            run(["git", "diff", "--cached", "--check"], env)
        # A second structural pass proves compilation/tests didn't poison validation.
        run([python, "tools/validate_skills.py"], env)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"All repository checks passed ({len(groups)} isolated test groups).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
