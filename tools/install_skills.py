#!/usr/bin/env python3
"""Preview or install a catalogued skill set without overwriting existing skills."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]


def selected_skills(root: Path, group: str) -> list[str]:
    catalog = json.loads((root / "skill_catalog.json").read_text(encoding="utf-8"))
    if catalog.get("schema_version") != 1:
        raise ValueError("unsupported skill catalog schema")
    groups = ("production", "compatibility") if group == "all" else (group,)
    names = [name for key in groups for name in catalog[key]]
    if not names or len(names) != len(set(names)):
        raise ValueError("skill selection is empty or contains duplicates")
    for name in names:
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
            raise ValueError("invalid skill name in catalog")
        skill = root / "skills" / name
        if skill.is_symlink() or not (skill / "SKILL.md").is_file():
            raise ValueError(f"missing regular source skill: {name}")
    return names


def install(root: Path, destination: Path, group: str, mode: str, apply: bool) -> list[str]:
    root = root.resolve()
    destination = destination.expanduser().resolve()
    sources = root / "skills"
    if destination.is_relative_to(sources) or sources.is_relative_to(destination):
        raise ValueError("installation destination must not overlap source skills")
    names = selected_skills(root, group)
    actions = []
    # Check every collision before writing anything. Never replace a user's skill.
    for name in names:
        source, target = sources / name, destination / name
        if mode == "symlink" and target.is_symlink() and target.resolve() == source.resolve():
            actions.append((source, target, "already linked"))
        elif target.exists() or target.is_symlink():
            raise ValueError(f"destination already exists; compare and back it up first: {target}")
        else:
            actions.append((source, target, mode))
        if any(path.is_symlink() for path in source.rglob("*")):
            raise ValueError(f"source skill contains a symlink: {source}")
    if apply:
        destination.mkdir(parents=True, exist_ok=True)
        for source, target, action in actions:
            if action == "copy":
                shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".DS_Store"))
            elif action == "symlink":
                target.symlink_to(source, target_is_directory=True)
    verb = "Installed" if apply else "Preview"
    return [f"{verb}: {target.name} ({action}) -> {target}" for _, target, action in actions]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", choices=("production", "compatibility", "all"), default="production")
    parser.add_argument("--destination", type=Path, default=Path.home() / ".agents/skills")
    parser.add_argument("--mode", choices=("copy", "symlink"), default="copy")
    parser.add_argument("--apply", action="store_true", help="write files; default is a read-only preview")
    args = parser.parse_args()
    try:
        for line in install(ROOT, args.destination, args.set, args.mode, args.apply):
            print(line)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if not args.apply:
        print("No files changed. Add --apply to install this selection.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
