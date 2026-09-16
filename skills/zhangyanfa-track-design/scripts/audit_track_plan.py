#!/usr/bin/env python3
"""Audit a multi-track TSV plan, selected shots, identity proofs and reviews."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


REQUIRED = {
    "cue_id", "start_frame", "end_frame", "text", "track", "candidate_id",
    "shot_id", "source_id", "source_in", "source_out", "visual_family_id",
    "visual_transform", "match_class", "match_reason", "identity_required",
    "identity_proof_id", "refresh_from_previous", "continuity_override_id",
    "review_status",
}
USABLE_RIGHTS = {"official", "licensed", "user_owned"}
PASS_VALUES = {"pass", "approved"}
IDENTITY_BASIS = "visible_character_features"
FORBIDDEN_IDENTITY_TERMS = {
    "ocr", "subtitle", "caption", "dialogue", "dialog", "name", "text",
    "字幕", "台词", "对白", "名字", "文字", "提到", "说出",
}
FLOAT_TOLERANCE = 1e-6


def truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "pass", "approved"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_tsv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


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


def resolve(base: Path, value: object) -> Path:
    path = Path(str(value)).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def approved_override_ids(rows: list[dict[str, Any]]) -> set[str]:
    approved: set[str] = set()
    for row in rows:
        if (
            str(row.get("gate", "")) == "continuity_override"
            and str(row.get("status", row.get("decision", ""))).lower() in PASS_VALUES
            and (row.get("approval_id") or row.get("id"))
        ):
            approved.add(str(row.get("approval_id") or row.get("id")))
    return approved


def bound_file(base: Path, item: Any, label: str, errors: list[str]) -> tuple[Path | None, str]:
    if not isinstance(item, dict):
        errors.append(f"{label}: artifact object required")
        return None, ""
    path = resolve(base, item.get("path", ""))
    expected = str(item.get("sha256", "")).lower()
    if not path.is_file():
        errors.append(f"{label}: artifact missing")
        return None, expected
    actual = sha256_file(path)
    if len(expected) != 64 or actual != expected:
        errors.append(f"{label}: artifact SHA mismatch")
    return path, actual


def verify_track_reviews(
    review_manifest: Path | None,
    approvals: list[dict[str, Any]],
    required_tracks: set[str],
    errors: list[str],
) -> None:
    if review_manifest is None or not review_manifest.is_file():
        errors.append("reviewed stage requires --track-reviews")
        return
    data = json.loads(review_manifest.read_text(encoding="utf-8"))
    reviews = data.get("tracks", {}) if isinstance(data, dict) else {}
    if not isinstance(reviews, dict):
        errors.append("track review manifest must contain tracks object")
        return
    for track in sorted(required_tracks):
        review = reviews.get(track)
        if not isinstance(review, dict):
            errors.append(f"track {track}: review manifest entry required")
            continue
        artifact_path, artifact_sha = bound_file(
            review_manifest.parent, review.get("artifact"), f"track {track} review", errors
        )
        approval_id = str(review.get("approval_id", ""))
        expected_gate = f"{track.lower()}_track_review"
        expected_role = f"{track.lower()}_review"
        matched = False
        for row in approvals:
            row_id = str(row.get("approval_id") or row.get("id") or "")
            decision = str(row.get("status", row.get("decision", ""))).lower()
            gate_matches = row.get("gate") == expected_gate or row.get("role") == expected_role
            artifact = row.get("artifact", {})
            if (
                row_id == approval_id
                and decision in PASS_VALUES
                and gate_matches
                and isinstance(artifact, dict)
                and str(artifact.get("sha256", "")).lower() == artifact_sha
            ):
                if artifact_path and str(artifact.get("path", "")) not in {
                    str(artifact_path), str(review.get("artifact", {}).get("path", ""))
                }:
                    continue
                matched = True
                break
        if not approval_id or not matched:
            errors.append(f"track {track}: artifact-bound current approval required")


def verify_proof_file(
    base: Path,
    row: dict[str, Any],
    source_in: float,
    source_out: float,
    prefix: str,
    errors: list[str],
) -> None:
    frame_times: list[float] = []
    for position in ("head", "mid", "tail"):
        path_value = row.get(f"{position}_frame")
        hash_value = str(row.get(f"{position}_sha256", "")).lower()
        path = resolve(base, path_value or "")
        if not path.is_file():
            errors.append(f"{prefix}: missing {position}_frame")
        elif len(hash_value) != 64 or sha256_file(path) != hash_value:
            errors.append(f"{prefix}: invalid {position}_frame hash")
        try:
            frame_time = float(row.get(f"{position}_source_time"))
            if frame_time < source_in - FLOAT_TOLERANCE or frame_time > source_out + FLOAT_TOLERANCE:
                errors.append(f"{prefix}: {position}_source_time outside selected range")
            frame_times.append(frame_time)
        except (TypeError, ValueError):
            errors.append(f"{prefix}: {position}_source_time required")
    if len(frame_times) == 3 and frame_times != sorted(frame_times):
        errors.append(f"{prefix}: proof frame times must be ordered head/mid/tail")


def approval_rows(path: Path | None) -> list[dict[str, Any]]:
    return read_jsonl(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--identity-proof", type=Path)
    parser.add_argument("--approvals", type=Path)
    parser.add_argument("--track-reviews", type=Path)
    parser.add_argument("--shot-index", type=Path)
    parser.add_argument("--rights-ledger", type=Path)
    parser.add_argument("--expected-cue-count", type=int)
    parser.add_argument("--required-tracks", default="A")
    parser.add_argument("--stage", choices=["proposed", "reviewed"], default="reviewed")
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()

    rows = read_tsv(args.plan)
    errors: list[str] = []
    if not rows:
        errors.append("track plan is empty")
    elif not REQUIRED.issubset(rows[0]):
        errors.append(f"track plan missing columns: {sorted(REQUIRED - set(rows[0]))}")

    required_tracks = {value.strip() for value in args.required_tracks.split(",") if value.strip()}
    if not required_tracks or not required_tracks.issubset({"A", "B", "C"}):
        errors.append("--required-tracks must be a comma-separated subset of A,B,C")
    approvals = approval_rows(args.approvals)
    overrides = approved_override_ids(approvals)
    proof_rows = read_jsonl(args.identity_proof)
    proofs = {str(row.get("proof_id", "")): row for row in proof_rows if row.get("proof_id")}
    shot_rows = read_tsv(args.shot_index)
    shots = {row.get("shot_id", "").strip(): row for row in shot_rows if row.get("shot_id", "").strip()}
    rights_rows = read_tsv(args.rights_ledger)
    rights = {row.get("source_id", "").strip(): row.get("rights_status", "").strip() for row in rights_rows}
    if args.stage == "reviewed":
        if args.expected_cue_count is None or args.expected_cue_count <= 0:
            errors.append("reviewed stage requires positive --expected-cue-count")
        if not shot_rows:
            errors.append("reviewed stage requires --shot-index")
        if not rights_rows:
            errors.append("reviewed stage requires --rights-ledger")
        verify_track_reviews(args.track_reviews, approvals, required_tracks, errors)

    parsed_by_track: dict[str, list[tuple[int, dict[str, str], int, int, int, float, float]]] = {
        "A": [], "B": [], "C": []
    }
    seen_keys: set[tuple[str, int]] = set()
    identity_required_count = 0

    for row_number, row in enumerate(rows, 1):
        label = f"row {row_number}"
        try:
            cue_id = int(row.get("cue_id", ""))
            start = int(row.get("start_frame", ""))
            end = int(row.get("end_frame", ""))
            source_in = float(row.get("source_in", ""))
            source_out = float(row.get("source_out", ""))
        except ValueError:
            errors.append(f"{label}: invalid cue/frame/source-range values")
            continue
        track = row.get("track", "").strip()
        key = (track, cue_id)
        if key in seen_keys:
            errors.append(f"{label}: duplicate track+cue_id {track}+{cue_id}")
        seen_keys.add(key)
        if track not in {"A", "B", "C"}:
            errors.append(f"{label}: invalid track")
            continue
        if end <= start:
            errors.append(f"{label}: end_frame must be after start_frame")
        if source_out <= source_in:
            errors.append(f"{label}: invalid source range")
        for field in ("candidate_id", "shot_id", "source_id", "visual_family_id"):
            if not row.get(field, "").strip():
                errors.append(f"{label}: {field} required")
        if row.get("match_class", "").strip() not in {"direct", "strong", "support"}:
            errors.append(f"{label}: match_class must be direct, strong or support")
        if not row.get("match_reason", "").strip():
            errors.append(f"{label}: match_reason required")
        if args.stage == "reviewed" and row.get("review_status", "").strip().lower() not in PASS_VALUES:
            errors.append(f"{label}: reviewed stage requires review_status pass")
        source_id = row.get("source_id", "").strip()
        if args.stage == "reviewed" and rights.get(source_id) not in USABLE_RIGHTS:
            errors.append(f"{label}: source rights are not cleared")

        if track == "A" and shots:
            shot_id = row.get("shot_id", "").strip()
            shot = shots.get(shot_id)
            if shot is None:
                errors.append(f"{label}: selected shot_id not found in shot index")
            else:
                if shot.get("source_id", "").strip() != source_id:
                    errors.append(f"{label}: selected shot source_id mismatch")
                if shot.get("visual_family_id", "").strip() != row.get("visual_family_id", "").strip():
                    errors.append(f"{label}: visual_family_id does not match shot index")
                try:
                    shot_in = float(shot.get("start_s", ""))
                    shot_out = float(shot.get("end_s", ""))
                    if source_in < shot_in - FLOAT_TOLERANCE or source_out > shot_out + FLOAT_TOLERANCE:
                        errors.append(f"{label}: selected source range lies outside indexed shot")
                except ValueError:
                    errors.append(f"{label}: indexed shot has invalid range")

        if truthy(row.get("identity_required")):
            identity_required_count += 1
            proof_id = row.get("identity_proof_id", "").strip()
            proof = proofs.get(proof_id)
            if proof is None:
                errors.append(f"{label}: identity proof required")
            else:
                if int(proof.get("cue_id", -1)) != cue_id:
                    errors.append(f"{label}: proof cue_id mismatch")
                if str(proof.get("track", "")) != track:
                    errors.append(f"{label}: proof track mismatch")
                if str(proof.get("candidate_id", "")) != row.get("candidate_id", "").strip():
                    errors.append(f"{label}: proof candidate_id mismatch")
                if str(proof.get("source_id", "")) != source_id:
                    errors.append(f"{label}: proof source_id mismatch")
                try:
                    proof_in = float(proof.get("source_in"))
                    proof_out = float(proof.get("source_out"))
                    if abs(proof_in - source_in) > FLOAT_TOLERANCE or abs(proof_out - source_out) > FLOAT_TOLERANCE:
                        errors.append(f"{label}: proof source range mismatch")
                except (TypeError, ValueError):
                    errors.append(f"{label}: proof source range required")
                if str(proof.get("identity_basis", "")) != IDENTITY_BASIS:
                    errors.append(f"{label}: identity_basis must be {IDENTITY_BASIS}")
                if str(proof.get("identity_verdict", "")).lower() not in {"pass", "verified"}:
                    errors.append(f"{label}: identity_verdict must pass")
                features = proof.get("visible_features")
                if not isinstance(features, list) or not features:
                    errors.append(f"{label}: proof needs visible_features list")
                else:
                    feature_text = " ".join(map(str, features)).lower()
                    if any(term in feature_text for term in FORBIDDEN_IDENTITY_TERMS):
                        errors.append(f"{label}: OCR/dialogue/name text cannot serve as visual identity proof")
                if not isinstance(proof.get("confusables_checked"), list):
                    errors.append(f"{label}: proof needs confusables_checked list")
                if not str(proof.get("reviewer", "")).strip():
                    errors.append(f"{label}: proof reviewer required")
                if str(proof.get("review_status", "")).lower() not in PASS_VALUES:
                    errors.append(f"{label}: proof review_status must pass")
                verify_proof_file(args.identity_proof.parent, proof, source_in, source_out, label, errors)

        parsed_by_track[track].append((row_number, row, cue_id, start, end, source_in, source_out))

    for track, items in parsed_by_track.items():
        ordered = sorted(items, key=lambda item: (item[3], item[4], item[2]))
        for previous, current in zip(ordered, ordered[1:]):
            previous_row = previous[1]
            current_row = current[1]
            if previous[4] > current[3]:
                errors.append(f"row {current[0]}: output frame range overlaps previous {track} row")
            if track != "A":
                continue
            refreshed = truthy(current_row.get("refresh_from_previous"))
            same_shot = current_row.get("shot_id", "").strip() == previous_row.get("shot_id", "").strip()
            same_source = current_row.get("source_id", "").strip() == previous_row.get("source_id", "").strip()
            overlaps_source = same_source and current[5] < previous[6] - FLOAT_TOLERANCE
            same_family = (
                current_row.get("visual_family_id", "").strip()
                == previous_row.get("visual_family_id", "").strip()
            )
            override_id = current_row.get("continuity_override_id", "").strip()
            if (not refreshed or same_shot or overlaps_source or same_family) and override_id not in overrides:
                errors.append(f"row {current[0]}: A per_caption_refresh violation without approved override")

    a_cues = {item[2] for item in parsed_by_track["A"]}
    if args.stage == "reviewed" and args.expected_cue_count:
        expected = set(range(1, args.expected_cue_count + 1))
        if a_cues != expected:
            errors.append(
                f"A track cue coverage mismatch: missing={sorted(expected - a_cues)} extra={sorted(a_cues - expected)}"
            )
    present_tracks = {track for track, items in parsed_by_track.items() if items}
    missing_required = required_tracks - present_tracks
    if missing_required:
        errors.append(f"required tracks missing from plan: {sorted(missing_required)}")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "stage": args.stage,
        "row_count": len(rows),
        "cue_count": len(a_cues),
        "track_row_counts": {track: len(items) for track, items in parsed_by_track.items()},
        "identity_required_count": identity_required_count,
        "approved_override_count": len(overrides),
        "errors": errors,
    }
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
