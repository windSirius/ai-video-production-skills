#!/usr/bin/env python3
"""Validate repository Skill packages without third-party dependencies."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
USER_PATH_RE = re.compile(r"/Users/[^/\s`\"']+")
LINK_RE = re.compile(r"\[[^\]]+\]\((?!https?://|#)([^)]+)\)")
FORBIDDEN_NAMES = {".DS_Store"}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo"}
MAX_SOURCE_BYTES = 5 * 1024 * 1024


def scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        parsed = ast.literal_eval(value)
        if not isinstance(parsed, str):
            raise ValueError("frontmatter value must be a string")
        return parsed
    return value


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("missing opening YAML delimiter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("missing closing YAML delimiter") from exc

    data: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")) or ":" not in line:
            raise ValueError(f"unsupported frontmatter line: {line!r}")
        key, value = line.split(":", 1)
        data[key.strip()] = scalar(value)
    return data


def validate_agent_yaml(skill_dir: Path, skill_name: str) -> list[str]:
    errors: list[str] = []
    path = skill_dir / "agents" / "openai.yaml"
    if not path.is_file():
        return [f"{path.relative_to(ROOT)}: missing recommended agents/openai.yaml"]

    text = path.read_text(encoding="utf-8")
    for field in ("display_name", "short_description", "default_prompt"):
        match = re.search(rf"^\s{{2}}{field}:\s*(.+)$", text, re.MULTILINE)
        if not match:
            errors.append(f"{path.relative_to(ROOT)}: missing interface.{field}")
            continue
        raw = match.group(1).strip()
        if not (len(raw) >= 2 and raw[0] == raw[-1] == '"'):
            errors.append(f"{path.relative_to(ROOT)}: {field} must be double quoted")
    if f"${skill_name}" not in text:
        errors.append(f"{path.relative_to(ROOT)}: default_prompt must mention ${skill_name}")
    return errors


def validate_links(skill_md: Path) -> list[str]:
    errors: list[str] = []
    text = skill_md.read_text(encoding="utf-8")
    for target in LINK_RE.findall(text):
        clean = target.split("#", 1)[0]
        if clean and not (skill_md.parent / clean).exists():
            errors.append(f"{skill_md.relative_to(ROOT)}: broken local link {target!r}")
    return errors


def validate_skill(skill_dir: Path) -> list[str]:
    errors: list[str] = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return [f"{skill_dir.relative_to(ROOT)}: missing SKILL.md"]

    try:
        metadata = parse_frontmatter(skill_md)
    except (SyntaxError, ValueError) as exc:
        return [f"{skill_md.relative_to(ROOT)}: {exc}"]

    if set(metadata) != {"name", "description"}:
        errors.append(
            f"{skill_md.relative_to(ROOT)}: frontmatter keys must be exactly name and description"
        )
    name = metadata.get("name", "")
    if name != skill_dir.name:
        errors.append(f"{skill_md.relative_to(ROOT)}: name must match directory {skill_dir.name!r}")
    if not NAME_RE.fullmatch(name):
        errors.append(f"{skill_md.relative_to(ROOT)}: invalid skill name {name!r}")
    if len(name) > 64:
        errors.append(f"{skill_md.relative_to(ROOT)}: skill name exceeds 64 characters")
    if not metadata.get("description", "").strip():
        errors.append(f"{skill_md.relative_to(ROOT)}: description is empty")
    if (skill_dir / "README.md").exists():
        errors.append(f"{skill_dir.relative_to(ROOT)}: README.md belongs at repository root")

    errors.extend(validate_agent_yaml(skill_dir, name))
    errors.extend(validate_links(skill_md))
    return errors


def validate_repository_files() -> list[str]:
    errors: list[str] = []
    for path in SKILLS_DIR.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if path.name in FORBIDDEN_NAMES or path.suffix in FORBIDDEN_SUFFIXES:
            errors.append(f"{rel}: generated file must not be committed")
        if path.stat().st_size > MAX_SOURCE_BYTES:
            errors.append(f"{rel}: file exceeds 5 MiB source limit")
        if path.suffix.lower() in {".md", ".py", ".swift", ".yaml", ".yml", ".json"}:
            text = path.read_text(encoding="utf-8")
            match = USER_PATH_RE.search(text)
            if match:
                errors.append(f"{rel}: contains machine-specific path {match.group(0)!r}")
    return errors


def main() -> int:
    if not SKILLS_DIR.is_dir():
        print("ERROR: missing skills directory", file=sys.stderr)
        return 1

    skill_dirs = sorted(path for path in SKILLS_DIR.iterdir() if path.is_dir())
    errors: list[str] = []
    for skill_dir in skill_dirs:
        errors.extend(validate_skill(skill_dir))
    errors.extend(validate_repository_files())

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Validated {len(skill_dirs)} Skill packages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
