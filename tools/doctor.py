#!/usr/bin/env python3
"""Read-only prerequisite check; never imports speech engines or downloads models."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import re
import shutil
import subprocess
import sys


def package_check(name: str, minimum: tuple[int, ...], maximum_major: int | None = None) -> dict:
    try:
        version = importlib.metadata.version(name)
        parts = tuple(int(x) for x in re.match(r"\d+(?:\.\d+)*", version).group().split("."))
        ok = parts >= minimum and (maximum_major is None or parts[0] < maximum_major)
        return {"name": name, "ok": ok, "detail": version}
    except (importlib.metadata.PackageNotFoundError, AttributeError):
        return {"name": name, "ok": False, "detail": "missing or unrecognized version"}


def command_check(name: str, args: list[str]) -> dict:
    path = shutil.which(name)
    if not path:
        return {"name": name, "ok": False, "detail": "not on PATH"}
    try:
        result = subprocess.run([path, *args], capture_output=True, text=True, timeout=15)
        lines = (result.stdout + result.stderr).strip().splitlines()
        return {"name": name, "ok": result.returncode == 0, "detail": lines[0] if lines else path}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"name": name, "ok": False, "detail": str(exc)}


def inspect(dev: bool = False, swift: bool = False) -> dict:
    checks = [{"name": "Python", "ok": (3, 11) <= sys.version_info[:2] < (3, 15), "detail": platform.python_version()}]
    checks.append(package_check("Pillow", (12, 3, 0), 13))
    checks.extend(command_check(name, ["-version"]) for name in ("ffmpeg", "ffprobe"))
    if dev:
        checks.append(package_check("PyYAML", (6, 0, 3), 7))
        checks.append(command_check("git", ["--version"]))
    if swift:
        checks.append({"name": "macOS", "ok": sys.platform == "darwin", "detail": sys.platform})
        checks.append(command_check("xcrun", ["swiftc", "--version"]))
    return {
        "passed": all(check["ok"] for check in checks),
        "checks": checks,
        "scope": "tool availability only; not media QA, model readiness, or user approval",
        "optional_not_checked": ["VoxCPM/VoxCPM2 service", "FunASR/SenseVoice models", "HyperFrames/browser", "editor app", "voice reference audio"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev", action="store_true", help="include repository validation dependencies")
    parser.add_argument("--swift", action="store_true", help="require macOS and the Swift compiler")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = inspect(args.dev, args.swift)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for check in result["checks"]:
            print(f"{'PASS' if check['ok'] else 'FAIL'} {check['name']}: {check['detail']}")
        print(result["scope"])
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
