#!/usr/bin/env python3
"""Block narration candidates that contain normalized insertions, deletions, or substitutions."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


ALIAS_EVIDENCE_TYPES = {"second_recognizer", "targeted_human_audition"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"[^\w\u3400-\u9fff]+", "", text, flags=re.UNICODE).lower()


def normalize_asr(text: str, aliases: dict[str, str]) -> str:
    text = unicodedata.normalize("NFKC", text)
    for source in sorted(aliases, key=len, reverse=True):
        text = text.replace(source, aliases[source])
    return normalize(text)


def validate_alias_rows(value: Any) -> tuple[dict[str, str], list[dict[str, str]]]:
    if not isinstance(value, list):
        raise ValueError("alias evidence must be a list of evidence rows, not a replacement map")
    aliases: dict[str, str] = {}
    rows: list[dict[str, str]] = []
    required = (
        "asr_surface",
        "canonical_surface",
        "evidence_type",
        "evidence_ref",
        "reviewer",
        "reviewed_at",
        "decision",
    )
    for index, raw in enumerate(value, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"alias evidence row {index} must be an object")
        row = {field: str(raw.get(field, "")).strip() for field in required}
        missing = [field for field, item in row.items() if not item]
        if missing:
            raise ValueError(f"alias evidence row {index} is missing: {', '.join(missing)}")
        if row["evidence_type"] not in ALIAS_EVIDENCE_TYPES:
            raise ValueError(f"alias evidence row {index} has unsupported evidence_type")
        if row["decision"] != "recognition_ambiguity":
            raise ValueError(f"alias evidence row {index} must decide recognition_ambiguity")
        if row["asr_surface"] == row["canonical_surface"]:
            raise ValueError(f"alias evidence row {index} does not describe an ambiguity")
        if row["asr_surface"] in aliases:
            raise ValueError(f"duplicate ASR alias surface: {row['asr_surface']}")
        aliases[row["asr_surface"]] = row["canonical_surface"]
        rows.append(row)
    return aliases, rows


def validate_alias_bundle(
    value: Any,
    canonical_sha256: str,
    asr_sha256: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    if not isinstance(value, dict) or value.get("schema_version") != "asr_alias_evidence_v1":
        raise ValueError("aliases file must use schema_version=asr_alias_evidence_v1")
    if str(value.get("canonical_sha256", "")).lower() != canonical_sha256:
        raise ValueError("alias evidence does not bind the current canonical SHA")
    if str(value.get("asr_sha256", "")).lower() != asr_sha256:
        raise ValueError("alias evidence does not bind the current ASR SHA")
    return validate_alias_rows(value.get("aliases"))


def audit(canonical: str, asr: str, alias_rows: list[dict[str, str]] | None = None) -> dict[str, Any]:
    aliases, validated_rows = validate_alias_rows(alias_rows or [])
    left = normalize(canonical)
    right = normalize_asr(asr, aliases)
    matcher = SequenceMatcher(None, left, right, autojunk=False)
    operations: list[dict[str, Any]] = []
    insertions = deletions = substitutions = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        canonical_piece = left[i1:i2]
        asr_piece = right[j1:j2]
        if tag == "insert":
            insertions += len(asr_piece)
        elif tag == "delete":
            deletions += len(canonical_piece)
        else:
            paired = min(len(canonical_piece), len(asr_piece))
            substitutions += paired
            deletions += len(canonical_piece) - paired
            insertions += len(asr_piece) - paired
        operations.append(
            {
                "kind": tag,
                "canonical_span": [i1, i2],
                "asr_span": [j1, j2],
                "canonical_text": canonical_piece,
                "asr_text": asr_piece,
            }
        )

    exact = left == right
    similarity = matcher.ratio() if left or right else 1.0
    return {
        "status": "pass" if exact else "fail",
        "exact": exact,
        "canonical_normalized": left,
        "asr_normalized": right,
        "canonical_length": len(left),
        "asr_length": len(right),
        "insertions": insertions,
        "deletions": deletions,
        "substitutions": substitutions,
        "similarity": similarity,
        "operations": operations,
        "alias_evidence_count": len(validated_rows),
        "alias_evidence": validated_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Require exact normalized canonical/ASR equality after approved ASR aliases."
    )
    parser.add_argument("canonical", type=Path)
    parser.add_argument("asr", type=Path)
    parser.add_argument("--aliases", type=Path, help="SHA-bound asr_alias_evidence_v1 JSON receipt")
    parser.add_argument("--output", type=Path, help="Optional JSON receipt path")
    parser.add_argument("--json", action="store_true", help="Print the full JSON receipt")
    args = parser.parse_args()

    canonical_sha = sha256(args.canonical)
    asr_sha = sha256(args.asr)
    aliases: list[dict[str, str]] = []
    if args.aliases:
        _, aliases = validate_alias_bundle(
            json.loads(args.aliases.read_text(encoding="utf-8")),
            canonical_sha,
            asr_sha,
        )
    result = audit(
        args.canonical.read_text(encoding="utf-8"),
        args.asr.read_text(encoding="utf-8"),
        aliases,
    )
    result.update(
        {
            "canonical_path": str(args.canonical.resolve()),
            "canonical_sha256": canonical_sha,
            "asr_path": str(args.asr.resolve()),
            "asr_sha256": asr_sha,
            "aliases_path": str(args.aliases.resolve()) if args.aliases else None,
            "aliases_sha256": sha256(args.aliases) if args.aliases else None,
        }
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    if args.json:
        print(rendered, end="")
    else:
        print(
            f"{result['status'].upper()} exact={str(result['exact']).lower()} "
            f"insertions={result['insertions']} deletions={result['deletions']} "
            f"substitutions={result['substitutions']} similarity={result['similarity']:.4f}"
        )
    return 0 if result["exact"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
