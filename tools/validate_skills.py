#!/usr/bin/env python3
"""Validate source packages, local documentation links, data files, and frozen UI."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

try:
    import yaml
except ImportError:
    raise SystemExit("PyYAML is required: python3 -m pip install -r requirements-dev.txt")

ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Literal placeholders such as /Users/<name> are documentation, not private paths.
USER_PATH_RE = re.compile(r"/(?:Users|home)/(?!<|\$|\{)[^/\s`\"'<>]+")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*(?:<([^>]+)>|([^\s)]+))(?:\s+\"[^\"]*\")?\s*\)")
TEXT_SUFFIXES = {".md", ".py", ".swift", ".yaml", ".yml", ".json", ".html", ".js", ".css", ".env", ".txt", ".tsv", ".srt", ".toml"}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo", ".pem", ".key", ".mp4", ".mov", ".mkv", ".avi", ".webm", ".wav", ".flac", ".mp3", ".m4a", ".aac", ".safetensors", ".ckpt", ".pth", ".pt", ".onnx", ".bin"}
MAX_SOURCE_BYTES = 5 * 1024 * 1024
IGNORED_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML with duplicate keys rejected instead of silently overwritten."""


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def load_yaml(text: str):
    return yaml.load(text, Loader=UniqueKeyLoader)


def parse_frontmatter(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("missing opening YAML delimiter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("missing closing YAML delimiter") from exc
    data = load_yaml("\n".join(lines[1:end]))
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a mapping")
    return data


def source_files(root: Path) -> list[Path]:
    """Check tracked files even if ignored, plus new non-ignored source files."""
    # Do not accidentally query an enclosing repository when checking an archive.
    if (root / ".git").exists():
        result = subprocess.run(["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"], capture_output=True, check=True)
        paths = {root / name.decode("utf-8") for name in result.stdout.split(b"\0") if name}
        return sorted(path for path in paths if path.is_file() or path.is_symlink())
    # ZIP/source-tree fallback. Ignored runtime caches are not publication inputs.
    return sorted(path for path in root.rglob("*") if path.is_file() and not any(part in IGNORED_DIRS for part in path.relative_to(root).parts))


def validate_agent_yaml(skill_dir: Path, name: str, root: Path = ROOT) -> list[str]:
    path = skill_dir / "agents/openai.yaml"
    label = path.relative_to(root)
    if not path.is_file():
        return [f"{label}: missing agents/openai.yaml"]
    try:
        text = path.read_text(encoding="utf-8")
        data = load_yaml(text)
        interface = data.get("interface", {}) if isinstance(data, dict) else {}
        if not isinstance(interface, dict):
            raise ValueError("interface must be a mapping")
        errors = []
        for field in ("display_name", "short_description", "default_prompt"):
            if not isinstance(interface.get(field), str) or not interface[field].strip():
                errors.append(f"{label}: missing nonempty interface.{field}")
            if not re.search(rf'^  {field}:\s*".*"\s*$', text, re.MULTILINE):
                errors.append(f"{label}: interface.{field} must be double quoted")
        if f"${name}" not in str(interface.get("default_prompt", "")):
            errors.append(f"{label}: default_prompt must mention ${name}")
        return errors
    except (ValueError, TypeError, yaml.YAMLError) as exc:
        return [f"{label}: {exc}"]


def validate_links(path: Path, root: Path = ROOT) -> list[str]:
    errors = []
    # Code examples may intentionally contain placeholder links.
    text = re.sub(r"(?ms)^(`{3,}|~{3,}).*?^\1\s*$", "", path.read_text(encoding="utf-8"))
    for angle, plain in LINK_RE.findall(text):
        target = angle or plain
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        linked = (path.parent / unquote(parsed.path)).resolve()
        if not linked.is_relative_to(root.resolve()) or not linked.exists():
            errors.append(f"{path.relative_to(root)}: broken or out-of-repository local link {target!r}")
    return errors


def validate_skill(skill_dir: Path, root: Path = ROOT) -> list[str]:
    path = skill_dir / "SKILL.md"
    if not path.is_file():
        return [f"{skill_dir.relative_to(root)}: missing SKILL.md"]
    try:
        metadata = parse_frontmatter(path)
    except (ValueError, TypeError, yaml.YAMLError) as exc:
        return [f"{path.relative_to(root)}: {exc}"]
    errors = []
    label = path.relative_to(root)
    if set(metadata) != {"name", "description"}:
        errors.append(f"{label}: frontmatter keys must be exactly name and description")
    name = metadata.get("name", "")
    if not isinstance(name, str) or not NAME_RE.fullmatch(name) or len(name) > 64:
        errors.append(f"{label}: invalid skill name")
    if name != skill_dir.name:
        errors.append(f"{label}: name must match directory {skill_dir.name!r}")
    description = metadata.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append(f"{label}: description must be a nonempty string")
    if (skill_dir / "README.md").exists():
        errors.append(f"{label}: README.md belongs at repository root")
    errors.extend(validate_agent_yaml(skill_dir, skill_dir.name, root))
    return errors


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def validate_repository_files(root: Path = ROOT) -> list[str]:
    errors = []
    for path in source_files(root):
        rel = path.relative_to(root)
        if path.is_symlink():
            errors.append(f"{rel}: published source must not be a symlink")
            continue
        if path.name == ".DS_Store" or path.suffix.lower() in FORBIDDEN_SUFFIXES or (path.name.startswith(".env") and path.name != ".env.example"):
            errors.append(f"{rel}: generated, private, or binary runtime file must not be committed")
        if path.stat().st_size > MAX_SOURCE_BYTES:
            errors.append(f"{rel}: file exceeds 5 MiB source limit")
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
            match = USER_PATH_RE.search(text)
            if match:
                errors.append(f"{rel}: contains a machine-specific home path")
            if path.suffix == ".md":
                errors.extend(validate_links(path, root))
            elif path.suffix == ".json":
                json.loads(text, object_pairs_hook=unique_json)
            elif path.suffix in {".yaml", ".yml"}:
                load_yaml(text)
        except (UnicodeError, ValueError, TypeError, yaml.YAMLError) as exc:
            errors.append(f"{rel}: invalid text/data: {exc}")
    return errors


def validate_catalog(root: Path, names: set[str]) -> list[str]:
    try:
        catalog = json.loads((root / "skill_catalog.json").read_text(encoding="utf-8"))
        if catalog.get("schema_version") != 1:
            raise ValueError("unsupported schema_version")
        groups = [catalog[key] for key in ("production", "compatibility")]
        if not all(isinstance(group, list) and group for group in groups):
            raise ValueError("both catalog groups must be nonempty lists")
        listed = [name for group in groups for name in group]
        if len(set(listed)) != len(listed) or set(listed) != names:
            raise ValueError("catalog must list each Skill package exactly once")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"skill_catalog.json: {exc}"]
    return []


def validate_frozen_ui(root: Path) -> list[str]:
    folder = root / "skills/zhangyanfa-track-design/assets/review-ui-v1"
    try:
        manifest = json.loads((folder / "framework_manifest.json").read_text(encoding="utf-8"))
        if manifest.get("framework_id") != "foxjiu-review-ui-v1" or set(manifest["sha256"]) != {"index.html", "review.css", "review.js"}:
            raise ValueError("unexpected frozen UI manifest")
        for name, expected in manifest["sha256"].items():
            if hashlib.sha256((folder / name).read_bytes()).hexdigest() != expected:
                raise ValueError(f"changed approved framework asset: {name}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"review-ui-v1: {exc}"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    if not (root / "skills").is_dir():
        print("ERROR: missing skills directory", file=sys.stderr)
        return 1
    directories = sorted(path for path in (root / "skills").iterdir() if path.is_dir())
    errors = [error for directory in directories for error in validate_skill(directory, root)]
    errors.extend(validate_catalog(root, {path.name for path in directories}))
    errors.extend(validate_repository_files(root))
    errors.extend(validate_frozen_ui(root))
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if not errors:
        print(f"Validated {len(directories)} Skill packages, repository sources, local links, and frozen review UI.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
