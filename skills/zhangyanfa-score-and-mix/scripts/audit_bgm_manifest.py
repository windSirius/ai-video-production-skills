#!/usr/bin/env python3
"""Validate real authority files, distinct auditions, full sections and approval."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


PASS_VALUES = {"pass", "approved"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve(base: Path, value: object) -> Path:
    path = Path(str(value)).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def check_bound_file(
    base: Path, item: Any, label: str, errors: list[str]
) -> tuple[Path | None, str]:
    if not isinstance(item, dict):
        errors.append(f"{label}: object required")
        return None, ""
    path = resolve(base, item.get("path", ""))
    expected = str(item.get("sha256", "")).lower()
    if not path.is_file():
        errors.append(f"{label}: missing file")
        return None, expected
    actual = sha256_file(path)
    if len(expected) != 64 or actual != expected:
        errors.append(f"{label}: sha256 mismatch")
    return path, actual


def read_jsonl(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{number} is not an object")
        rows.append(value)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--approvals", type=Path, required=True)
    parser.add_argument("--minimum-candidates", type=int, default=4)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    base = args.manifest.parent
    errors: list[str] = []
    mode = str(data.get("source_mode", ""))
    if mode not in {"local_library", "generated_score"}:
        errors.append("source_mode must be local_library or generated_score")

    authority = data.get("authority_bindings")
    if not isinstance(authority, dict):
        errors.append("authority_bindings object required")
        authority = {}
    _, narration_sha = check_bound_file(base, authority.get("narration"), "authority narration", errors)
    _, srt_sha = check_bound_file(base, authority.get("srt"), "authority SRT", errors)
    for key in ("fps", "target_frame_count"):
        try:
            if int(authority.get(key, 0)) <= 0:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"authority_bindings.{key} must be positive")
    target_frames = int(authority.get("target_frame_count", 0) or 0)

    candidates = data.get("candidates", [])
    if not isinstance(candidates, list) or len(candidates) < args.minimum_candidates:
        errors.append(f"at least {args.minimum_candidates} comparable candidates required")
        candidates = candidates if isinstance(candidates, list) else []
    candidate_ids: set[str] = set()
    candidate_audio_shas: dict[str, str] = {}
    directions: set[str] = set()
    comparison_keys: set[tuple[str, str]] = set()
    for index, row in enumerate(candidates, 1):
        if not isinstance(row, dict):
            errors.append(f"candidate {index}: object required")
            continue
        candidate_id = str(row.get("candidate_id", ""))
        if not candidate_id or candidate_id in candidate_ids:
            errors.append(f"candidate {index}: missing or duplicate candidate_id")
        candidate_ids.add(candidate_id)
        _, audio_sha = check_bound_file(base, row.get("audition_mix"), f"candidate {candidate_id} audition_mix", errors)
        if audio_sha in candidate_audio_shas.values():
            errors.append(f"candidate {candidate_id}: audition audio SHA duplicates another candidate")
        candidate_audio_shas[candidate_id] = audio_sha
        candidate_narration_sha = str(row.get("narration_sha256", ""))
        review_range = row.get("review_range_frames")
        comparison_keys.add((candidate_narration_sha, json.dumps(review_range, sort_keys=True)))
        if candidate_narration_sha != narration_sha:
            errors.append(f"candidate {candidate_id}: narration binding mismatch")
        if not isinstance(review_range, list) or len(review_range) != 2:
            errors.append(f"candidate {candidate_id}: two-frame review range required")
        else:
            try:
                if int(review_range[0]) < 0 or int(review_range[1]) <= int(review_range[0]) or int(review_range[1]) > target_frames:
                    raise ValueError
            except (TypeError, ValueError):
                errors.append(f"candidate {candidate_id}: invalid review range")
        direction = str(row.get("direction", "")).strip()
        if not direction or direction in directions:
            errors.append(f"candidate {candidate_id}: unique direction required")
        directions.add(direction)
    if len(comparison_keys) > 1:
        errors.append("candidate audition mixes do not use one frozen narration/range")

    selected = str(data.get("selected_candidate_id", ""))
    if selected not in candidate_ids:
        errors.append("selected_candidate_id must name a current candidate")

    sections = data.get("sections", [])
    if not isinstance(sections, list) or not sections:
        errors.append("nonempty sections list required")
        sections = []
    prior_end = 0
    for index, row in enumerate(sections, 1):
        if not isinstance(row, dict):
            errors.append(f"section {index}: object required")
            continue
        try:
            start = int(row.get("start_frame", -1))
            end = int(row.get("end_frame", -1))
        except (TypeError, ValueError):
            errors.append(f"section {index}: invalid frame range")
            continue
        if start != prior_end or end <= start or end > target_frames:
            errors.append(f"section {index}: sections must contiguously cover the frame clock")
        prior_end = end
        for key in ("chapter", "mood", "rhetorical_job", "vocal_content"):
            if not row.get(key):
                errors.append(f"section {index}: {key} required")
        if row.get("candidate_id") != selected:
            errors.append(f"section {index}: candidate_id must match selected candidate")
        if row.get("vocal_content") == "lyrics":
            for key in ("lyrics_language", "lyric_meaning_summary", "semantic_conflict_review", "narration_intelligibility_review"):
                if not row.get(key):
                    errors.append(f"section {index}: lyric field {key} required")
    if prior_end != target_frames:
        errors.append(f"sections end at {prior_end}, expected {target_frames}")

    check_bound_file(base, data.get("bgm_master"), "bgm_master", errors)
    approved_path, approved_sha = check_bound_file(
        base, data.get("approved_audition_mix"), "approved_audition_mix", errors
    )
    if selected in candidate_audio_shas and approved_sha != candidate_audio_shas[selected]:
        errors.append("approved_audition_mix does not match selected candidate audio")

    approval_id = str(data.get("approval_id", ""))
    approval_ok = False
    for row in read_jsonl(args.approvals):
        row_id = str(row.get("approval_id") or row.get("id") or "")
        decision = str(row.get("status", row.get("decision", ""))).lower()
        artifact = row.get("artifact", {})
        gate_ok = row.get("gate") == "bgm_review" or row.get("role") == "bgm_review"
        if (
            row_id == approval_id
            and decision in PASS_VALUES
            and gate_ok
            and isinstance(artifact, dict)
            and str(artifact.get("sha256", "")).lower() == approved_sha
        ):
            if approved_path and str(artifact.get("path", "")) not in {
                str(approved_path), str(data.get("approved_audition_mix", {}).get("path", ""))
            }:
                continue
            approval_ok = True
            break
    if not approval_id or not approval_ok:
        errors.append("artifact-bound current bgm_review approval required")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "source_mode": mode,
        "narration_sha256": narration_sha,
        "srt_sha256": srt_sha,
        "candidate_count": len(candidates),
        "selected_candidate_id": selected,
        "section_count": len(sections),
        "errors": errors,
    }
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
