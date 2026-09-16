#!/usr/bin/env python3
"""Validate distinct concepts, source rights, recent comparison and ratio re-layout."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


USABLE_RIGHTS = {"official", "licensed", "user_owned"}
CONCEPT_GATES = (
    "identity_pass", "shot_pass", "same_space_pass", "text_pass",
    "thumbnail_pass", "edge_artifact_pass", "source_rights_pass",
    "recent_cover_compare_pass",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve(base: Path, value: object) -> Path:
    path = Path(str(value)).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def bound_file(base: Path, item: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(item, dict):
        errors.append(f"{label}: object required")
        return None
    path = resolve(base, item.get("path", ""))
    expected = str(item.get("sha256", "")).lower()
    if not path.is_file():
        errors.append(f"{label}: file missing")
        return None
    if len(expected) != 64 or sha256_file(path) != expected:
        errors.append(f"{label}: sha256 mismatch")
    return path


def image_size(path: Path) -> tuple[int, int] | None:
    try:
        result = subprocess.run(
            ["/usr/bin/sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10,
        )
        values: dict[str, int] = {}
        for line in result.stdout.splitlines():
            if ":" in line:
                key, value = line.strip().split(":", 1)
                if value.strip().isdigit():
                    values[key] = int(value.strip())
        if "pixelWidth" in values and "pixelHeight" in values:
            return values["pixelWidth"], values["pixelHeight"]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def aspect_ok(path: Path, ratio: str) -> bool:
    size = image_size(path)
    if size is None:
        return False
    expected = {"16:9": 16 / 9, "4:3": 4 / 3, "3:4": 3 / 4}[ratio]
    return abs(size[0] / size[1] - expected) < 0.02


def normalized_gray(path: Path, ffmpeg: str) -> bytes | None:
    try:
        result = subprocess.run(
            [
                ffmpeg, "-v", "error", "-i", str(path), "-vf",
                "scale=64:64:flags=area,format=gray", "-frames:v", "1",
                "-f", "rawvideo", "-",
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 and len(result.stdout) == 4096 else None


def normalized_difference(left: Path, right: Path, ffmpeg: str) -> float | None:
    a = normalized_gray(left, ffmpeg)
    b = normalized_gray(right, ffmpeg)
    if a is None or b is None:
        return None
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    base = args.manifest.parent
    errors: list[str] = []

    if not str(data.get("cover_promise", "")).strip():
        errors.append("cover_promise required")

    source_rows = data.get("cover_sources", [])
    if not isinstance(source_rows, list) or not source_rows:
        errors.append("nonempty cover_sources list required")
        source_rows = []
    source_ids: set[str] = set()
    for index, row in enumerate(source_rows, 1):
        if not isinstance(row, dict):
            errors.append(f"cover source {index}: object required")
            continue
        source_id = str(row.get("source_id", ""))
        if not source_id or source_id in source_ids:
            errors.append(f"cover source {index}: unique source_id required")
        source_ids.add(source_id)
        if row.get("rights_status") not in USABLE_RIGHTS:
            errors.append(f"cover source {source_id}: rights must be cleared")
        if not row.get("role"):
            errors.append(f"cover source {source_id}: role required")
        bound_file(base, row.get("artifact"), f"cover source {source_id}", errors)

    recent_rows = data.get("recent_covers", [])
    if not isinstance(recent_rows, list) or len(recent_rows) < 3:
        errors.append("at least three bound recent_covers required")
        recent_rows = recent_rows if isinstance(recent_rows, list) else []
    recent_shas: set[str] = set()
    for index, item in enumerate(recent_rows, 1):
        path = bound_file(base, item, f"recent cover {index}", errors)
        if path:
            recent_shas.add(sha256_file(path))
    if len(recent_shas) != len(recent_rows):
        errors.append("recent cover artifacts must have unique visual SHAs")

    concepts = data.get("concepts_16_9", [])
    if not isinstance(concepts, list) or len(concepts) != 6:
        errors.append("exactly six 16:9 concepts required")
        concepts = concepts if isinstance(concepts, list) else []
    concept_ids: set[str] = set()
    directions: set[str] = set()
    concept_paths: dict[str, Path] = {}
    concept_shas: set[str] = set()
    for index, row in enumerate(concepts, 1):
        if not isinstance(row, dict):
            errors.append(f"concept {index}: object required")
            continue
        concept_id = str(row.get("concept_id", ""))
        direction = str(row.get("narrative_direction", "")).strip()
        if concept_id not in set("ABCDEF") or concept_id in concept_ids:
            errors.append(f"concept {index}: unique A-F concept_id required")
        concept_ids.add(concept_id)
        if not direction or direction in directions:
            errors.append(f"concept {concept_id}: unique narrative_direction required")
        directions.add(direction)
        path = bound_file(base, row.get("artifact"), f"concept {concept_id}", errors)
        if path:
            concept_paths[concept_id] = path
            concept_shas.add(sha256_file(path))
            if not aspect_ok(path, "16:9"):
                errors.append(f"concept {concept_id}: image is not 16:9")
        used_sources = row.get("source_ids")
        if not isinstance(used_sources, list) or not used_sources:
            errors.append(f"concept {concept_id}: source_ids required")
        elif not set(map(str, used_sources)).issubset(source_ids):
            errors.append(f"concept {concept_id}: unknown or uncleared source_id")
        for key in CONCEPT_GATES:
            if str(row.get(key, "")).lower() != "pass":
                errors.append(f"concept {concept_id}: {key} must pass before selection")
    if len(concept_shas) != 6:
        errors.append("six concepts must have six unique visual SHAs")

    selected = str(data.get("selected_concept_id", ""))
    if selected not in concept_ids:
        errors.append("selected_concept_id must name A-F")
    approved = bound_file(base, data.get("approved_16_9"), "approved_16_9", errors)
    approved_sha = sha256_file(approved) if approved else ""
    if approved and not aspect_ok(approved, "16:9"):
        errors.append("approved_16_9 has wrong aspect ratio")
    if approved and selected in concept_paths and approved_sha != sha256_file(concept_paths[selected]):
        errors.append("approved_16_9 does not match selected concept")

    ratios = data.get("ratio_reviews", {})
    if not isinstance(ratios, dict):
        errors.append("ratio_reviews object required")
        ratios = {}
    for ratio in ("4:3", "3:4"):
        review = ratios.get(ratio)
        path = bound_file(base, review.get("artifact") if isinstance(review, dict) else None, f"ratio {ratio}", errors)
        if path and not aspect_ok(path, ratio):
            errors.append(f"ratio {ratio}: wrong aspect ratio")
        if isinstance(review, dict):
            for key in ("subject_not_occluded", "aspect_ratio_preserved", "thumbnail_readable", "title_safe_area_pass", "independent_layout"):
                if str(review.get(key, "")).lower() != "pass":
                    errors.append(f"ratio {ratio}: {key} must pass")
            if str(review.get("source_16_9_sha256", "")).lower() != approved_sha:
                errors.append(f"ratio {ratio}: source_16_9_sha256 mismatch")
            operations = review.get("layout_operations")
            if not isinstance(operations, list) or not operations:
                errors.append(f"ratio {ratio}: layout_operations required")
        if path and approved:
            difference = normalized_difference(approved, path, args.ffmpeg)
            if difference is None:
                errors.append(f"ratio {ratio}: unable to compare layout pixels")
            elif difference <= 2.0:
                errors.append(f"ratio {ratio}: mechanical resize detected")

    approval = data.get("cover_review")
    if not isinstance(approval, dict) or str(approval.get("status", "")).lower() not in {"pass", "approved"}:
        errors.append("artifact-bound cover_review required")
    elif approved and str(approval.get("approved_sha256", "")) != approved_sha:
        errors.append("cover_review does not bind approved 16:9 SHA")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "cover_promise": str(data.get("cover_promise", "")),
        "concept_count": len(concepts),
        "unique_concept_sha_count": len(concept_shas),
        "selected_concept_id": selected,
        "errors": errors,
    }
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
