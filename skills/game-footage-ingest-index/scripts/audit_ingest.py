#!/usr/bin/env python3
"""Audit the source, OCR/index, rights, identity, P0 and coverage handoff."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


ALLOWED_RIGHTS = {"official", "licensed", "user_owned", "permission_needed", "unknown"}
ALLOWED_P0 = {"available", "acquire", "card", "remove"}
ALLOWED_TRANSCRIPT_STATUS = {"complete", "not_present", "audio_transcript_needed", "unreliable"}
USABLE_RIGHTS = {"official", "licensed", "user_owned"}
TIME_TOLERANCE = 0.001


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{number} is not an object")
        rows.append(value)
    return rows


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def resolve(base: Path, value: object) -> Path:
    path = Path(str(value)).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def check_file(path: Path, expected_sha: object, label: str, errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"{label}: missing file {path}")
        return
    expected = str(expected_sha or "").strip().lower()
    if len(expected) != 64:
        errors.append(f"{label}: missing sha256")
    elif sha256_file(path) != expected:
        errors.append(f"{label}: sha256 mismatch")


def positive_float(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def probe_duration(probe: object) -> float | None:
    if not isinstance(probe, dict):
        return None
    for key in ("duration_s", "duration"):
        parsed = positive_float(probe.get(key))
        if parsed is not None:
            return parsed
    return None


def ranges_cover_duration(
    ranges: list[tuple[float, float]], duration: float, label: str, errors: list[str]
) -> None:
    if not ranges:
        errors.append(f"{label}: no coverage ranges")
        return
    ordered = sorted(ranges)
    cursor = 0.0
    for start, end in ordered:
        if start > cursor + TIME_TOLERANCE:
            errors.append(f"{label}: uncovered interval {cursor:.3f}-{start:.3f}s")
        if end > cursor:
            cursor = end
    if cursor < duration - TIME_TOLERANCE:
        errors.append(f"{label}: coverage ends at {cursor:.3f}s before {duration:.3f}s")
    if ordered[0][0] < -TIME_TOLERANCE or cursor > duration + TIME_TOLERANCE:
        errors.append(f"{label}: coverage extends outside source duration")


def write_report(path: Path | None, report: dict[str, Any]) -> None:
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--rights-ledger", type=Path, required=True)
    parser.add_argument("--shot-index", type=Path, required=True)
    parser.add_argument("--ocr-asr-index", type=Path, required=True)
    parser.add_argument("--coverage-receipts", type=Path, required=True)
    parser.add_argument("--identity-registry", type=Path, required=True)
    parser.add_argument("--p0-coverage", type=Path, required=True)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()

    paths = [
        args.source_manifest,
        args.rights_ledger,
        args.shot_index,
        args.ocr_asr_index,
        args.coverage_receipts,
        args.identity_registry,
        args.p0_coverage,
    ]
    errors: list[str] = []
    for path in paths:
        if not path.is_file():
            errors.append(f"missing input: {path}")
    if errors:
        report = {"status": "FAIL", "errors": errors}
        write_report(args.output_json, report)
        return 1

    sources = read_jsonl(args.source_manifest)
    source_rows: dict[str, dict[str, Any]] = {}
    source_durations: dict[str, float] = {}
    source_shas: dict[str, str] = {}
    for index, row in enumerate(sources, 1):
        source_id = str(row.get("source_id", "")).strip()
        if not source_id or source_id in source_rows:
            errors.append(f"source row {index}: missing or duplicate source_id")
            continue
        source_rows[source_id] = row
        raw_path = Path(str(row.get("path", ""))).expanduser()
        if not raw_path.is_absolute():
            errors.append(f"source {source_id}: path must be absolute")
        source_path = resolve(args.source_manifest.parent, raw_path)
        check_file(source_path, row.get("sha256"), f"source {source_id}", errors)
        source_shas[source_id] = str(row.get("sha256", "")).lower()
        duration = probe_duration(row.get("probe"))
        if duration is None:
            errors.append(f"source {source_id}: probe must contain positive duration_s")
        else:
            source_durations[source_id] = duration
        if str(row.get("rights_status", "")) not in ALLOWED_RIGHTS:
            errors.append(f"source {source_id}: invalid rights_status")

    rights = read_tsv(args.rights_ledger)
    rights_by_id = {row.get("source_id", "").strip(): row for row in rights}
    for source_id, source in source_rows.items():
        row = rights_by_id.get(source_id)
        if row is None:
            errors.append(f"rights ledger missing {source_id}")
            continue
        ledger_status = row.get("rights_status", "").strip()
        if ledger_status not in ALLOWED_RIGHTS:
            errors.append(f"rights ledger {source_id}: invalid rights_status")
        elif ledger_status != str(source.get("rights_status", "")):
            errors.append(f"rights ledger {source_id}: status does not match source manifest")

    shots = read_tsv(args.shot_index)
    required_shot = {"shot_id", "source_id", "start_s", "end_s", "visual_family_id"}
    if not shots:
        errors.append("shot index is empty")
    elif not required_shot.issubset(shots[0]):
        errors.append(f"shot index missing required columns: {sorted(required_shot - set(shots[0]))}")
    seen_shots: dict[str, dict[str, str]] = {}
    shot_ranges: dict[str, list[tuple[float, float]]] = {source_id: [] for source_id in source_rows}
    for row in shots:
        shot_id = row.get("shot_id", "").strip()
        source_id = row.get("source_id", "").strip()
        if not shot_id or shot_id in seen_shots:
            errors.append("shot index contains missing or duplicate shot_id")
        else:
            seen_shots[shot_id] = row
        if source_id not in source_rows:
            errors.append(f"shot {shot_id}: unknown source_id")
        if not row.get("visual_family_id", "").strip():
            errors.append(f"shot {shot_id}: visual_family_id required")
        try:
            start = float(row.get("start_s", ""))
            end = float(row.get("end_s", ""))
            if start < 0 or end <= start:
                raise ValueError
            if source_id in shot_ranges:
                shot_ranges[source_id].append((start, end))
        except ValueError:
            errors.append(f"shot {shot_id}: invalid numeric time")
    for source_id, duration in source_durations.items():
        ranges_cover_duration(shot_ranges.get(source_id, []), duration, f"shot index {source_id}", errors)

    ocr_rows = read_tsv(args.ocr_asr_index)
    required_ocr = {
        "source_id", "shot_id", "start_s", "end_s", "ocr_text", "asr_text", "transcript_status"
    }
    if not ocr_rows:
        errors.append("OCR/ASR index is empty")
    elif not required_ocr.issubset(ocr_rows[0]):
        errors.append(f"OCR/ASR index missing required columns: {sorted(required_ocr - set(ocr_rows[0]))}")
    indexed_shots: set[str] = set()
    for index, row in enumerate(ocr_rows, 1):
        shot_id = row.get("shot_id", "").strip()
        source_id = row.get("source_id", "").strip()
        shot = seen_shots.get(shot_id)
        if shot is None:
            errors.append(f"OCR/ASR row {index}: unknown shot_id")
        elif source_id != shot.get("source_id", "").strip():
            errors.append(f"OCR/ASR row {index}: source_id does not match shot")
        else:
            indexed_shots.add(shot_id)
        if row.get("transcript_status", "").strip() not in ALLOWED_TRANSCRIPT_STATUS:
            errors.append(f"OCR/ASR row {index}: invalid transcript_status")
        try:
            start = float(row.get("start_s", ""))
            end = float(row.get("end_s", ""))
            if end <= start:
                raise ValueError
        except ValueError:
            errors.append(f"OCR/ASR row {index}: invalid range")
    missing_ocr_shots = set(seen_shots) - indexed_shots
    if missing_ocr_shots:
        errors.append(f"OCR/ASR index missing shots: {sorted(missing_ocr_shots)}")

    receipt_rows = read_jsonl(args.coverage_receipts)
    receipts: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(receipt_rows, 1):
        source_id = str(row.get("source_id", "")).strip()
        if not source_id or source_id in receipts:
            errors.append(f"coverage receipt {index}: missing or duplicate source_id")
            continue
        receipts[source_id] = row
    for source_id, duration in source_durations.items():
        receipt = receipts.get(source_id)
        if receipt is None:
            errors.append(f"coverage receipt missing {source_id}")
            continue
        if str(receipt.get("source_sha256", "")).lower() != source_shas.get(source_id):
            errors.append(f"coverage receipt {source_id}: source SHA mismatch")
        if str(receipt.get("review_status", "")).lower() not in {"pass", "approved"}:
            errors.append(f"coverage receipt {source_id}: review_status must pass")
        if not str(receipt.get("reviewer", "")).strip():
            errors.append(f"coverage receipt {source_id}: reviewer required")
        intervals = receipt.get("intervals")
        parsed_ranges: list[tuple[float, float]] = []
        if not isinstance(intervals, list) or not intervals:
            errors.append(f"coverage receipt {source_id}: nonempty intervals required")
        else:
            for interval_index, interval in enumerate(intervals, 1):
                if not isinstance(interval, dict) or not str(interval.get("classification", "")).strip():
                    errors.append(f"coverage receipt {source_id} interval {interval_index}: classification required")
                    continue
                try:
                    start = float(interval.get("start_s"))
                    end = float(interval.get("end_s"))
                    if start < 0 or end <= start:
                        raise ValueError
                    parsed_ranges.append((start, end))
                except (TypeError, ValueError):
                    errors.append(f"coverage receipt {source_id} interval {interval_index}: invalid range")
        ranges_cover_duration(parsed_ranges, duration, f"coverage receipt {source_id}", errors)

    registry = json.loads(args.identity_registry.read_text(encoding="utf-8"))
    identities = registry.get("identities", []) if isinstance(registry, dict) else registry
    if not isinstance(identities, list):
        errors.append("identity registry must contain an identities list")
        identities = []
    for index, row in enumerate(identities, 1):
        if not isinstance(row, dict) or not str(row.get("canonical_identity", "")).strip():
            errors.append(f"identity row {index}: canonical_identity required")
            continue
        if not row.get("visible_features") or not isinstance(row.get("confusables", []), list):
            errors.append(f"identity row {index}: visible_features and confusables required")
        proof = row.get("proof_frames", [])
        if not isinstance(proof, list) or not proof:
            errors.append(f"identity row {index}: proof_frames required")
            continue
        for proof_index, item in enumerate(proof, 1):
            if not isinstance(item, dict):
                errors.append(f"identity row {index} proof {proof_index}: invalid")
                continue
            check_file(
                resolve(args.identity_registry.parent, item.get("path", "")),
                item.get("sha256"),
                f"identity row {index} proof {proof_index}",
                errors,
            )

    p0_rows = read_tsv(args.p0_coverage)
    for index, row in enumerate(p0_rows, 1):
        status = row.get("status", "").strip()
        source_id = row.get("source_id", "").strip()
        if not row.get("p0_id", "").strip() or status not in ALLOWED_P0:
            errors.append(f"P0 row {index}: p0_id and valid status required")
        if status == "available":
            if source_id not in source_rows:
                errors.append(f"P0 row {index}: available item needs a known source_id")
            elif rights_by_id.get(source_id, {}).get("rights_status", "").strip() not in USABLE_RIGHTS:
                errors.append(f"P0 row {index}: available item uses unresolved rights")
        elif not row.get("notes", "").strip():
            errors.append(f"P0 row {index}: unresolved choice needs notes")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "source_count": len(sources),
        "shot_count": len(shots),
        "ocr_asr_count": len(ocr_rows),
        "coverage_receipt_count": len(receipt_rows),
        "identity_count": len(identities),
        "p0_count": len(p0_rows),
        "errors": errors,
    }
    write_report(args.output_json, report)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
