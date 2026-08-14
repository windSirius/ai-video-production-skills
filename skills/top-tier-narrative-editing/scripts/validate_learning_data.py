#!/usr/bin/env python3
"""Validate corpus and hypothesis registries for narrative-editing learning."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse


ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ROLES = {"benchmark", "core-corpus", "discovery", "negative", "user-baseline"}
CORPUS_STATUSES = {"discovered", "selected", "analyzing", "sampled", "fully-annotated"}
RIGHTS_MODES = {"public-metadata", "temporary-analysis-copy", "user-owned", "user-provided"}
HYPOTHESIS_LEVELS = {"H0", "H1", "H2", "H3", "H4"}
HYPOTHESIS_STATUSES = {"active", "narrowed", "retired"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--hypotheses", type=Path)
    parser.add_argument("--check-paths", action="store_true")
    return parser.parse_args()


def load_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be a JSON object")
    return value


def require_list(entry: dict, key: str, where: str, errors: list[str]) -> list:
    value = entry.get(key)
    if not isinstance(value, list):
        errors.append(f"{where}.{key}: must be a list")
        return []
    return value


def valid_source(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} or Path(value).is_absolute()


def validate_corpus(data: dict, check_paths: bool) -> tuple[list[str], dict[str, dict]]:
    errors: list[str] = []
    entries = data.get("entries")
    if data.get("schema_version") != "1.0":
        errors.append("corpus.schema_version: expected 1.0")
    if not isinstance(entries, list):
        return [*errors, "corpus.entries: must be a list"], {}

    by_id: dict[str, dict] = {}
    required_text = {"id", "title", "creator", "language", "platform", "source", "role", "status", "rights_mode"}
    for index, entry in enumerate(entries):
        where = f"corpus.entries[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{where}: must be an object")
            continue
        for key in required_text:
            if not isinstance(entry.get(key), str) or not entry[key]:
                errors.append(f"{where}.{key}: required non-empty string")

        entry_id = entry.get("id")
        if isinstance(entry_id, str):
            if not ID_RE.fullmatch(entry_id):
                errors.append(f"{where}.id: must be lowercase kebab-case")
            elif entry_id in by_id:
                errors.append(f"{where}.id: duplicate {entry_id}")
            else:
                by_id[entry_id] = entry

        if entry.get("role") not in ROLES:
            errors.append(f"{where}.role: unsupported value")
        if entry.get("status") not in CORPUS_STATUSES:
            errors.append(f"{where}.status: unsupported value")
        if entry.get("rights_mode") not in RIGHTS_MODES:
            errors.append(f"{where}.rights_mode: unsupported value")
        if not valid_source(entry.get("source")):
            errors.append(f"{where}.source: expected http(s) URL or absolute local path")

        strata = require_list(entry, "strata", where, errors)
        reasons = require_list(entry, "selection_reasons", where, errors)
        recognition = require_list(entry, "recognition_sources", where, errors)
        artifacts = require_list(entry, "analysis_artifacts", where, errors)
        require_list(entry, "limitations", where, errors)
        if not strata:
            errors.append(f"{where}.strata: at least one value required")
        if not reasons:
            errors.append(f"{where}.selection_reasons: at least one value required")
        if entry.get("role") == "benchmark" and not recognition:
            errors.append(f"{where}.recognition_sources: benchmark requires independent recognition")

        if check_paths:
            source = entry.get("source")
            if isinstance(source, str) and Path(source).is_absolute() and not Path(source).exists():
                errors.append(f"{where}.source: local path does not exist")
            for artifact in artifacts:
                if isinstance(artifact, str) and Path(artifact).is_absolute() and not Path(artifact).exists():
                    errors.append(f"{where}.analysis_artifacts: missing {artifact}")
    return errors, by_id


def validate_hypotheses(data: dict, corpus: dict[str, dict]) -> list[str]:
    errors: list[str] = []
    hypotheses = data.get("hypotheses")
    if data.get("schema_version") != "1.0":
        errors.append("hypotheses.schema_version: expected 1.0")
    if not isinstance(hypotheses, list):
        return [*errors, "hypotheses.hypotheses: must be a list"]

    seen: set[str] = set()
    for index, item in enumerate(hypotheses):
        where = f"hypotheses[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where}: must be an object")
            continue
        for key in ("id", "statement", "evidence_level", "status", "next_test"):
            if not isinstance(item.get(key), str) or not item[key]:
                errors.append(f"{where}.{key}: required non-empty string")

        item_id = item.get("id")
        if isinstance(item_id, str):
            if not ID_RE.fullmatch(item_id):
                errors.append(f"{where}.id: must be lowercase kebab-case")
            elif item_id in seen:
                errors.append(f"{where}.id: duplicate {item_id}")
            seen.add(item_id)

        level = item.get("evidence_level")
        if level not in HYPOTHESIS_LEVELS:
            errors.append(f"{where}.evidence_level: unsupported value")
        if item.get("status") not in HYPOTHESIS_STATUSES:
            errors.append(f"{where}.status: unsupported value")

        applies_to = require_list(item, "applies_to", where, errors)
        supporting = require_list(item, "supporting_entries", where, errors)
        contradicting = require_list(item, "contradicting_entries", where, errors)
        tests = require_list(item, "tests", where, errors)
        require_list(item, "limitations", where, errors)
        if not applies_to:
            errors.append(f"{where}.applies_to: at least one value required")

        for entry_id in [*supporting, *contradicting]:
            if entry_id not in corpus:
                errors.append(f"{where}: unknown corpus entry {entry_id}")

        if level in {"H1", "H2", "H3", "H4"} and not supporting:
            errors.append(f"{where}: {level} requires supporting entries")
        if level in {"H2", "H3", "H4"}:
            creators = {corpus[entry_id]["creator"] for entry_id in supporting if entry_id in corpus}
            if len(supporting) < 3 or len(creators) < 2:
                errors.append(f"{where}: {level} requires 3 entries from 2 creators")
        if level in {"H3", "H4"} and not tests:
            errors.append(f"{where}: {level} requires at least one experiment")
        if level == "H4" and len(tests) < 3:
            errors.append(f"{where}: H4 requires at least three experiments")
    return errors


def main() -> None:
    args = parse_args()
    corpus_data = load_object(args.corpus)
    errors, corpus = validate_corpus(corpus_data, args.check_paths)
    hypothesis_count = 0
    if args.hypotheses:
        hypothesis_data = load_object(args.hypotheses)
        hypothesis_count = len(hypothesis_data.get("hypotheses", []))
        errors.extend(validate_hypotheses(hypothesis_data, corpus))

    result = {
        "valid": not errors,
        "corpus_entries": len(corpus),
        "hypotheses": hypothesis_count,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
