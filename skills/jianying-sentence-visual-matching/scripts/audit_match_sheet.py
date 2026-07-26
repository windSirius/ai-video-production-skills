#!/usr/bin/env python3
"""Audit proposed, reviewed, or render-ready sentence-to-shot plans."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {
    "line_id",
    "start",
    "end",
    "duration",
    "text",
    "candidate_a",
    "candidate_a_score",
    "candidate_b",
    "candidate_b_score",
    "candidate_c",
    "candidate_c_score",
    "source_file",
    "source_in",
    "source_out",
    "match_reason",
    "confidence",
    "retry_round",
    "reuse_group",
    "qa_status",
}
STILL_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
TIME_RE = re.compile(
    r"(?P<sh>\d+):(?P<sm>\d{2}):(?P<ss>\d{2})[,.](?P<sms>\d{3})"
    r"\s*-->\s*"
    r"(?P<eh>\d+):(?P<em>\d{2}):(?P<es>\d{2})[,.](?P<ems>\d{3})"
)
TRUE_VALUES = {"1", "true", "yes", "y", "是", "required"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def number(
    value: str, label: str, line_id: str, errors: list[str]
) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        errors.append(f"line {line_id}: invalid {label}={value!r}")
        return None


def parse_candidate(value: str) -> dict[str, Any] | None:
    parts = value.split("|")
    if len(parts) < 5:
        return None
    source_id, filename, span, step_id, kind = parts[:5]
    matches = re.findall(r"(-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)", span)
    if not matches:
        return None
    segments = [(float(start), float(end)) for start, end in matches]
    if any(end <= start for start, end in segments):
        return None
    return {
        "source_id": source_id,
        "filename": filename,
        "segments": segments,
        "step_id": step_id,
        "kind": kind,
        "descriptor": value,
    }


def is_true(value: str) -> bool:
    return value.strip().casefold() in TRUE_VALUES


def is_risk_row(row: dict[str, str]) -> bool:
    explicit = " ".join(
        row.get(key, "")
        for key in (
            "risk_flags",
            "risk_reason",
            "review_risk",
            "identity_review",
        )
    ).strip()
    if explicit:
        return True
    if is_true(row.get("identity_required", "")):
        return True
    if row.get("named_entities_expected", "").strip():
        return True
    if row.get("narrative_job", "").strip().casefold() in {
        "hook",
        "ending",
        "resolution",
        "climax",
        "quote",
        "quote_or_evidence",
    }:
        return True
    if row.get("confidence", "").strip().casefold() in {"low", "medium", "低", "中"}:
        return True
    try:
        if float(row.get("retry_round") or 0) > 0:
            return True
    except ValueError:
        return True
    if row.get("ocr_collision_risk", "").strip().casefold() in {"high", "medium"}:
        return True
    if row.get("rights_status", "").strip() not in {
        "",
        "user_recording",
        "original",
        "public-domain",
    }:
        return True
    if Path(row.get("source_file", "")).suffix.casefold() in STILL_SUFFIXES:
        return True
    subject = row.get("subject", "").strip()
    return bool(subject and subject not in {"主题概念", "叙述者", "无"})


def parse_srt(path: Path) -> list[dict[str, Any]]:
    blocks = re.split(
        r"\n{2,}",
        path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip(),
    )
    entries = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        timing_index = next(
            (index for index, line in enumerate(lines) if "-->" in line), None
        )
        if timing_index is None:
            continue
        match = TIME_RE.search(lines[timing_index])
        if not match:
            raise ValueError(f"invalid SRT timing: {lines[timing_index]}")

        def seconds(prefix: str) -> float:
            return (
                int(match[f"{prefix}h"]) * 3600
                + int(match[f"{prefix}m"]) * 60
                + int(match[f"{prefix}s"])
                + int(match[f"{prefix}ms"]) / 1000
            )

        index = (
            int(lines[0])
            if timing_index > 0 and lines[0].isdigit()
            else len(entries) + 1
        )
        entries.append(
            {
                "line_id": index,
                "start": seconds("s"),
                "end": seconds("e"),
                "text": " ".join(lines[timing_index + 1 :]),
            }
        )
    return entries


def resolve_manifest_file(manifest_path: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (manifest_path.parent / path).resolve()


def validate_review_manifest(
    path: Path,
    match_sha: str,
    row_ids: set[int],
    automatic_risk_ids: set[int],
    stage: str,
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("match_sheet_sha256") != match_sha:
        errors.append("review manifest match_sheet_sha256 is stale")
    if data.get("status") != "PASS":
        errors.append("review manifest status must be PASS")
    if int(data.get("row_count") or -1) != len(row_ids):
        errors.append("review manifest row_count does not match match sheet")

    selected_reviewed = {
        int(item) for item in data.get("selected_reviewed_ids", [])
    }
    missing_selected = sorted(row_ids - selected_reviewed)
    if missing_selected:
        errors.append(
            f"review manifest missing selected-shot reviews: {missing_selected}"
        )

    declared_risk = {int(item) for item in data.get("risk_row_ids", [])}
    missing_automatic_risk = sorted(automatic_risk_ids - declared_risk)
    if missing_automatic_risk:
        errors.append(
            "review manifest omits automatically detected risk rows: "
            f"{missing_automatic_risk}"
        )
    candidate_reviewed = {
        int(item) for item in data.get("candidate_reviewed_ids", [])
    }
    missing_candidate_review = sorted(declared_risk - candidate_reviewed)
    if missing_candidate_review:
        errors.append(
            f"review manifest missing A/B/C reviews: {missing_candidate_review}"
        )

    identity_required = {
        int(item) for item in data.get("identity_required_ids", [])
    }
    identity_verified = {
        int(key): str(value)
        for key, value in data.get("identity_verified", {}).items()
    }
    missing_identity = sorted(
        item
        for item in identity_required
        if not identity_verified.get(item)
        or identity_verified[item].casefold() in {"unverified", "pending", "false"}
    )
    if missing_identity:
        errors.append(f"review manifest missing identity verdicts: {missing_identity}")

    unresolved = [int(item) for item in data.get("unresolved_ids", [])]
    if unresolved:
        errors.append(f"review manifest has unresolved rows: {sorted(unresolved)}")

    files = data.get("files")
    if not isinstance(files, list) or not files:
        errors.append("review manifest must list trusted evidence files")
        files = []
    trusted_paths: set[Path] = set()
    for index, record in enumerate(files):
        if not isinstance(record, dict) or not record.get("path") or not record.get("sha256"):
            errors.append(f"review manifest file record {index} lacks path/sha256")
            continue
        file_path = resolve_manifest_file(path, str(record["path"]))
        trusted_paths.add(file_path)
        if not file_path.is_file():
            errors.append(f"review evidence missing: {file_path}")
            continue
        if sha256_file(file_path) != str(record["sha256"]):
            errors.append(f"review evidence hash mismatch: {file_path}")

    for record in data.get("evidence", []):
        if isinstance(record, str):
            evidence_path = resolve_manifest_file(path, record)
        elif isinstance(record, dict) and record.get("path"):
            evidence_path = resolve_manifest_file(path, str(record["path"]))
        else:
            continue
        if evidence_path not in trusted_paths:
            errors.append(
                f"review evidence is not listed in trusted files: {evidence_path}"
            )

    if stage == "render-ready":
        for label in ("opening_review", "ending_review"):
            section = data.get(label)
            if not isinstance(section, dict) or section.get("status") != "PASS":
                errors.append(f"review manifest {label}.status must be PASS")
    else:
        for label in ("opening_review", "ending_review"):
            section = data.get(label)
            if isinstance(section, dict) and section.get("status") == "FAIL":
                errors.append(f"review manifest {label}.status is FAIL")

    unknown = (
        selected_reviewed
        | declared_risk
        | candidate_reviewed
        | identity_required
    ) - row_ids
    if unknown:
        errors.append(f"review manifest references unknown rows: {sorted(unknown)}")
    if len(trusted_paths) < len(files):
        warnings.append("review manifest contains duplicate trusted file paths")
    return data


def load_candidate_pool(path: Path) -> dict[int, dict[str, dict[str, Any]]]:
    result: dict[int, dict[str, dict[str, Any]]] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        identity = int(entry.get("cue_id") or entry.get("line_id"))
        if identity in result:
            raise ValueError(f"candidate pool duplicates cue {identity}")
        result[identity] = {
            str(candidate.get("candidate_id")): candidate
            for candidate in entry.get("candidates", [])
            if isinstance(candidate, dict) and candidate.get("candidate_id")
        }
    return result


def selection_is_traced(
    row: dict[str, str],
    candidate_pool: dict[int, dict[str, dict[str, Any]]],
) -> bool:
    line_id = int(row["line_id"])
    selected_file = Path(row["source_file"]).expanduser().resolve()
    selected_in = float(row["source_in"])
    selected_out = float(row["source_out"])
    selected_id = row.get("selected_candidate_id", "").strip()
    if not selected_id:
        return False
    candidate = candidate_pool.get(line_id, {}).get(selected_id)
    if candidate is None:
        return False
    try:
        return (
            Path(str(candidate["source_file"])).expanduser().resolve()
            == selected_file
            and abs(float(candidate["source_in"]) - selected_in) <= 0.002
            and abs(float(candidate["source_out"]) - selected_out) <= 0.022
            and (
                not candidate.get("source_id")
                or str(candidate["source_id"])
                == str(
                    row.get("selected_source_id")
                    or row.get("source_id")
                    or ""
                )
            )
        )
    except (KeyError, TypeError, ValueError):
        return False


def run_shared_review_check(
    *,
    match_sheet: Path,
    review_manifest: Path,
    evidence_manifest: Path,
    candidate_pool: Path,
    source_manifest: Path,
) -> tuple[bool, str, dict[str, Any]]:
    shared_scripts = (
        Path(__file__).resolve().parents[2]
        / "zhangyanfa-video-production"
        / "scripts"
    )
    if not shared_scripts.is_dir():
        return False, f"shared production checker missing: {shared_scripts}", {}
    sys.path.insert(0, str(shared_scripts))
    try:
        from run_objective_checks import run_check
    except ImportError as exc:
        return False, f"cannot import shared production checker: {exc}", {}
    return run_check(
        match_sheet.parent,
        {
            "type": "visual_selection_review_integrity",
            "path": str(review_manifest),
            "match_sheet_path": str(match_sheet),
            "evidence_manifest_path": str(evidence_manifest),
            "candidate_pool_path": str(candidate_pool),
            "source_manifest_path": str(source_manifest),
            "require_named_identity": True,
            "require_contact_sheets": True,
            "require_range_reviews": True,
            "require_opening_review": True,
            "require_ending_review": True,
            "require_layered_review": True,
            "require_risk_frame_matrix": True,
            "require_candidate_pool_binding": True,
            "require_source_manifest_binding": True,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("match_sheet", type=Path)
    parser.add_argument("--max-reuse", type=int, default=2)
    parser.add_argument(
        "--stage",
        choices=("proposed", "reviewed", "render-ready"),
        default="proposed",
    )
    parser.add_argument("--canonical-srt", type=Path)
    parser.add_argument("--review-manifest", type=Path)
    parser.add_argument("--candidate-pool", type=Path)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--selected-evidence-manifest", type=Path)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()

    match_sheet = args.match_sheet.expanduser().resolve()
    with match_sheet.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_FIELDS - fields)
        rows = list(reader)

    errors: list[str] = []
    warnings: list[str] = []
    candidate_pool_path = (
        args.candidate_pool.expanduser().resolve()
        if args.candidate_pool
        else None
    )
    candidate_pool: dict[int, dict[str, dict[str, Any]]] = {}
    if candidate_pool_path is None or not candidate_pool_path.is_file():
        errors.append("--candidate-pool is required and must exist")
    else:
        try:
            candidate_pool = load_candidate_pool(candidate_pool_path)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid candidate pool: {exc}")
    source_manifest_path = (
        args.source_manifest.expanduser().resolve()
        if args.source_manifest
        else None
    )
    if source_manifest_path is None or not source_manifest_path.is_file():
        errors.append("--source-manifest is required and must exist")
    if missing:
        errors.append(f"missing columns: {', '.join(missing)}")
    row_ids: list[int] = []
    reuse = Counter()
    automatic_risk_ids: set[int] = set()
    selected_ranges: list[dict[str, Any]] = []
    three_candidate_rows = 0
    duration_valid_rows = 0
    traced_selection_rows = 0

    for row_number, row in enumerate(rows, 1):
        line_id_text = row.get("line_id", "").strip() or str(row_number)
        try:
            line_id = int(line_id_text)
        except ValueError:
            errors.append(f"row {row_number}: invalid line_id={line_id_text!r}")
            continue
        row_ids.append(line_id)
        if is_risk_row(row):
            automatic_risk_ids.add(line_id)
        reuse_group = row.get("reuse_group", "").strip()
        if reuse_group:
            reuse[reuse_group] += 1

        status = row.get("qa_status", "").strip().casefold()
        accepted = {
            "machine_proposed",
            "planned",
            "reviewed",
            "verified",
            "render_ready",
            "card",
        }
        if status not in accepted:
            errors.append(
                f"line {line_id}: qa_status must be machine_proposed, planned, "
                "reviewed, verified, render_ready, or card"
            )

        candidates = [
            row.get(f"candidate_{letter}", "").strip() for letter in "abc"
        ]
        parsed = [parse_candidate(candidate) for candidate in candidates]
        distinct = {
            candidate for candidate in candidates if candidate
        }
        if len(distinct) >= 3 and all(parsed):
            three_candidate_rows += 1
        elif not (
            status == "card"
            and row.get("candidate_exception_reason", "").strip()
        ):
            errors.append(f"line {line_id}: fewer than three distinct candidates")
        scores = [
            row.get(f"candidate_{letter}_score", "").strip()
            for letter in "abc"
        ]
        if any(candidate and not score for candidate, score in zip(candidates, scores)):
            errors.append(f"line {line_id}: candidate score missing")
        if not row.get("source_file", "").strip():
            errors.append(f"line {line_id}: selected source_file missing")

        source_in = number(
            row.get("source_in", ""), "source_in", line_id_text, errors
        )
        source_out = number(
            row.get("source_out", ""), "source_out", line_id_text, errors
        )
        duration = number(
            row.get("duration", ""), "duration", line_id_text, errors
        )
        if None not in {source_in, source_out, duration}:
            assert source_in is not None and source_out is not None and duration is not None
            if source_out <= source_in:
                errors.append(f"line {line_id}: source_out must be after source_in")
            elif source_out - source_in + 0.04 < duration:
                errors.append(f"line {line_id}: selected source is shorter than caption")
            else:
                duration_valid_rows += 1
            selected_ranges.append(
                {
                    "line_id": line_id,
                    "source_file": str(
                        Path(row["source_file"]).expanduser().resolve()
                    ),
                    "source_in": source_in,
                    "source_out": source_out,
                    "is_still": (
                        Path(row["source_file"]).suffix.casefold()
                        in STILL_SUFFIXES
                    ),
                }
            )

        if not row.get("match_reason", "").strip():
            errors.append(f"line {line_id}: match_reason missing")
        confidence = row.get("confidence", "").strip().casefold()
        retry_round = number(
            row.get("retry_round", ""), "retry_round", line_id_text, errors
        )
        if (
            confidence in {"low", "低"}
            and retry_round is not None
            and retry_round < 1
        ):
            errors.append(
                f"line {line_id}: low confidence without expansion retry"
            )

        if args.stage in {"reviewed", "render-ready"}:
            try:
                if selection_is_traced(row, candidate_pool):
                    traced_selection_rows += 1
                else:
                    errors.append(
                        f"line {line_id}: selection is neither A/B/C nor a "
                        "hash-traced explicit override"
                    )
            except (KeyError, TypeError, ValueError):
                errors.append(f"line {line_id}: invalid selection trace")
        if args.stage == "render-ready":
            source = Path(row.get("source_file", "")).expanduser()
            if not source.is_file():
                errors.append(f"line {line_id}: source file missing: {source}")

    if len(row_ids) != len(set(row_ids)):
        errors.append("match sheet contains duplicate line_id values")

    over_reuse = {
        group: count
        for group, count in sorted(reuse.items())
        if count > args.max_reuse
    }
    for group, count in over_reuse.items():
        message = (
            f"reuse_group {group!r}: used {count} times "
            f"(limit {args.max_reuse})"
        )
        if args.stage == "render-ready":
            errors.append(message)
        else:
            warnings.append(message)

    overlap_count = 0
    reverse_pairs: list[tuple[int, int]] = []
    if args.stage == "render-ready":
        tolerance = 1 / 60 + 0.0005
        for index, left in enumerate(selected_ranges):
            if left["is_still"]:
                continue
            for right in selected_ranges[index + 1 :]:
                if right["is_still"] or left["source_file"] != right["source_file"]:
                    continue
                overlap = min(left["source_out"], right["source_out"]) - max(
                    left["source_in"], right["source_in"]
                )
                if overlap > tolerance:
                    overlap_count += 1
                    errors.append(
                        f"source overlap: lines {left['line_id']}/{right['line_id']} "
                        f"overlap {overlap:.3f}s"
                    )
        for left, right in zip(selected_ranges, selected_ranges[1:]):
            if (
                not left["is_still"]
                and not right["is_still"]
                and left["source_file"] == right["source_file"]
                and right["source_in"] + tolerance < left["source_in"]
            ):
                reverse_pairs.append((left["line_id"], right["line_id"]))

    match_sha = sha256_file(match_sheet)
    review_data: dict[str, Any] = {}
    if args.stage in {"reviewed", "render-ready"}:
        if args.review_manifest is None:
            errors.append(f"--review-manifest is required for stage {args.stage}")
        elif (
            args.selected_evidence_manifest is None
            or not args.selected_evidence_manifest.expanduser().resolve().is_file()
        ):
            errors.append(
                "--selected-evidence-manifest is required for "
                f"stage {args.stage}"
            )
        elif candidate_pool_path is None or not candidate_pool_path.is_file():
            errors.append(
                f"--candidate-pool is required for stage {args.stage}"
            )
        elif (
            source_manifest_path is None
            or not source_manifest_path.is_file()
        ):
            errors.append(
                f"--source-manifest is required for stage {args.stage}"
            )
        else:
            review_path = args.review_manifest.expanduser().resolve()
            review_data = validate_review_manifest(
                review_path,
                match_sha,
                set(row_ids),
                automatic_risk_ids,
                args.stage,
                errors,
                warnings,
            )
            shared_passed, shared_detail, shared_metrics = (
                run_shared_review_check(
                    match_sheet=match_sheet,
                    review_manifest=review_path,
                    evidence_manifest=args.selected_evidence_manifest.expanduser().resolve(),
                    candidate_pool=candidate_pool_path,
                    source_manifest=source_manifest_path,
                )
            )
            if not shared_passed:
                shared_failures = shared_metrics.get("failures", [])
                if shared_failures:
                    errors.extend(
                        f"shared review gate: {failure}"
                        for failure in shared_failures
                    )
                else:
                    errors.append(
                        f"shared review gate failed: {shared_detail}"
                    )
            if args.stage == "render-ready":
                allowed_reverse = {
                    tuple(int(value) for value in item)
                    for item in review_data.get("continuity_exceptions", [])
                    if isinstance(item, list) and len(item) == 2
                }
                unapproved_reverse = [
                    pair for pair in reverse_pairs if pair not in allowed_reverse
                ]
                for left, right in unapproved_reverse:
                    errors.append(
                        f"unapproved adjacent reverse playback: lines {left}/{right}"
                    )
                allowed_reuse = set(review_data.get("reuse_exceptions", []))
                for group in over_reuse:
                    if group in allowed_reuse:
                        errors[:] = [
                            item
                            for item in errors
                            if not item.startswith(f"reuse_group {group!r}:")
                        ]

    canonical_sha = ""
    if args.canonical_srt is None:
        errors.append("--canonical-srt is required")
    else:
        canonical_path = args.canonical_srt.expanduser().resolve()
        canonical_sha = sha256_file(canonical_path)
        try:
            captions = parse_srt(canonical_path)
        except ValueError as error:
            errors.append(str(error))
            captions = []
        if len(captions) != len(rows):
            errors.append(
                f"canonical SRT rows={len(captions)} match-sheet rows={len(rows)}"
            )
        for caption, row in zip(captions, rows):
            line_id = int(row["line_id"])
            if caption["line_id"] != line_id:
                errors.append(f"line {line_id}: canonical index mismatch")
            if caption["text"] != row["text"]:
                errors.append(f"line {line_id}: canonical text mismatch")
            start_field = "caption_start" if row.get("caption_start") else "start"
            end_field = "caption_end" if row.get("caption_end") else "end"
            try:
                if abs(float(row[start_field]) - caption["start"]) > 0.001:
                    errors.append(f"line {line_id}: canonical start mismatch")
                if abs(float(row[end_field]) - caption["end"]) > 0.001:
                    errors.append(f"line {line_id}: canonical end mismatch")
            except (KeyError, ValueError):
                errors.append(f"line {line_id}: invalid canonical timing fields")

    report = {
        "schema_version": 2,
        "status": "PASS" if not errors else "FAIL",
        "stage": args.stage,
        "match_sheet": str(match_sheet),
        "match_sheet_sha256": match_sha,
        "canonical_srt": (
            str(args.canonical_srt.expanduser().resolve())
            if args.canonical_srt
            else ""
        ),
        "canonical_srt_sha256": canonical_sha,
        "review_manifest": (
            str(args.review_manifest.expanduser().resolve())
            if args.review_manifest
            else ""
        ),
        "review_manifest_sha256": (
            sha256_file(args.review_manifest.expanduser().resolve())
            if args.review_manifest and args.review_manifest.is_file()
            else ""
        ),
        "candidate_pool": str(candidate_pool_path or ""),
        "candidate_pool_sha256": (
            sha256_file(candidate_pool_path)
            if candidate_pool_path and candidate_pool_path.is_file()
            else ""
        ),
        "selected_evidence_manifest": (
            str(args.selected_evidence_manifest.expanduser().resolve())
            if args.selected_evidence_manifest
            else ""
        ),
        "source_manifest": str(source_manifest_path or ""),
        "source_manifest_sha256": (
            sha256_file(source_manifest_path)
            if source_manifest_path and source_manifest_path.is_file()
            else ""
        ),
        "row_count": len(rows),
        "three_candidate_rows": three_candidate_rows,
        "duration_valid_rows": duration_valid_rows,
        "automatic_risk_row_count": len(automatic_risk_ids),
        "traced_selection_rows": traced_selection_rows,
        "max_reuse_count": max(reuse.values(), default=0),
        "reuse_over_limit": over_reuse,
        "source_overlap_count": overlap_count,
        "adjacent_reverse_count": len(reverse_pairs),
        "errors": errors,
        "warnings": warnings,
    }
    if args.output_json:
        atomic_json(args.output_json.expanduser().resolve(), report)

    print(
        f"stage={args.stage} rows={len(rows)} "
        f"errors={len(errors)} warnings={len(warnings)}"
    )
    for item in errors:
        print(f"ERROR {item}")
    for item in warnings:
        print(f"WARN  {item}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
