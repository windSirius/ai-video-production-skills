#!/usr/bin/env python3
"""Run a whitelist of objective file, caption, TSV, JSON, and media checks."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import unicodedata
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any


SUPPORTED_TYPES = {
    "authority_chain_integrity",
    "file_exists",
    "file_nonempty",
    "glob_count",
    "json_fields",
    "json_assert",
    "text_contains",
    "tsv_status",
    "tsv_row_count_match",
    "mission_flow_coverage",
    "srt_no_adjacent_duplicates",
    "srt_integrity",
    "bgm_sources_within_root",
    "generated_bgm_manifest_integrity",
    "media_probe",
    "media_frame_contract",
    "live_state_assert",
    "image_evidence_set",
    "visual_index_integrity",
    "visual_match_plan_integrity",
    "visual_selection_review_integrity",
    "visual_match_repair_integrity",
    "source_proxy_manifest_integrity",
    "hyperframes_stress_test_integrity",
    "aesthetic_proxy_approval_integrity",
    "picture_master_integrity",
    "picture_patch_integrity",
}
CAPTION_FORBIDDEN_TERMINAL_PUNCTUATION = ("，", "。", "：", "；", ",", ".", ":", ";")
CAPTION_TRAILING_CLOSING_MARKS = ("」", "』", "”", "’", "》", "〉", "）", "】")
TRUE_VALUES = {"1", "true", "yes", "y", "是", "required"}
STILL_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
SEMANTIC_VISUAL_UNIT_GRANULARITY = "semantic_visual_units_v2"
ALLOWED_SEMANTIC_RISK_FLAGS = {
    "identity",
    "quotation_evidence",
    "opening",
    "ending",
    "low_confidence",
    "ocr_ui_black",
    "reuse_overlap",
    "user_reported",
}


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def dotted_value(data: Any, dotted: str) -> Any:
    current = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(dotted)
        current = current[part]
    return current


def parse_srt_texts(path: Path) -> list[str]:
    blocks = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip().split("\n\n")
    texts: list[str] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) >= 3 and "-->" in lines[1]:
            texts.append(" ".join(lines[2:]).strip())
    return texts


def srt_seconds(value: str) -> float:
    match = re.fullmatch(r"(\d+):(\d{2}):(\d{2})[,.](\d{3})", value.strip())
    if not match:
        raise ValueError(f"invalid SRT time: {value}")
    hours, minutes, seconds, milliseconds = (int(part) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000


def parse_srt_entries(path: Path) -> list[dict[str, Any]]:
    blocks = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip().split("\n\n")
    entries = []
    for block_number, block in enumerate(blocks, start=1):
        lines = [line.rstrip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            raise ValueError(f"invalid SRT block {block_number}")
        try:
            index = int(lines[0].strip())
        except ValueError as exc:
            raise ValueError(f"invalid SRT index at block {block_number}") from exc
        start_text, end_text = (part.strip() for part in lines[1].split("-->", 1))
        entries.append(
            {
                "index": index,
                "start": srt_seconds(start_text),
                "end": srt_seconds(end_text.split()[0]),
                "text": " ".join(line.strip() for line in lines[2:]).strip(),
            }
        )
    return entries


def lexical_text(value: str) -> str:
    return "".join(
        char
        for char in value
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )


def find_forbidden_terminal_punctuation(text: str) -> str | None:
    candidate = text.rstrip()
    while candidate and candidate[-1] in CAPTION_TRAILING_CLOSING_MARKS:
        candidate = candidate[:-1].rstrip()
    if candidate and candidate[-1] in CAPTION_FORBIDDEN_TERMINAL_PUNCTUATION:
        return candidate[-1]
    return None


def assert_json_values(data: dict[str, Any], assertions: list[dict[str, Any]]) -> list[str]:
    failures = []
    for assertion in assertions:
        field = assertion.get("field")
        op = assertion.get("op", "eq")
        try:
            actual = dotted_value(data, field)
        except KeyError:
            failures.append(f"{field}: missing")
            continue
        expected = assertion.get("value")
        if op == "eq_field":
            try:
                expected = dotted_value(data, expected)
            except KeyError:
                failures.append(f"{field}: comparison field {assertion.get('value')} missing")
                continue
        if op == "eq" and actual != expected:
            failures.append(f"{field}={actual!r}, expected {expected!r}")
        elif op == "eq_field" and actual != expected:
            failures.append(
                f"{field}={actual!r}, expected value of {assertion.get('value')}={expected!r}"
            )
        elif op == "ne" and actual == expected:
            failures.append(f"{field} must not equal {expected!r}")
        elif op == "gte" and not actual >= expected:
            failures.append(f"{field}={actual!r}, expected >= {expected!r}")
        elif op == "lte" and not actual <= expected:
            failures.append(f"{field}={actual!r}, expected <= {expected!r}")
        elif op == "nonempty" and actual in (None, "", [], {}):
            failures.append(f"{field} is empty")
        elif op not in {"eq", "eq_field", "ne", "gte", "lte", "nonempty"}:
            failures.append(f"{field}: unsupported assertion op {op}")
    return failures


def ffprobe_json(path: Path, count_frames: bool = False) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe not found")
    command = [ffprobe, "-v", "error"]
    if count_frames:
        command.append("-count_frames")
    command.extend(["-show_streams", "-show_format", "-of", "json", str(path)])
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffprobe failed")
    return json.loads(completed.stdout)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader.fieldnames or []), list(reader)


def resolved_existing_file(root: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = resolve_path(root, value.strip()).expanduser().resolve()
    return candidate if candidate.is_file() else None


def manifest_hash_value(data: dict[str, Any], *fields: str) -> str:
    for field in fields:
        try:
            value = dotted_value(data, field)
        except KeyError:
            continue
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return ""


def split_identity_values(value: object) -> list[str]:
    if isinstance(value, list):
        return sorted({str(item).strip() for item in value if str(item).strip()})
    if not isinstance(value, str):
        return []
    return sorted(
        {
            item.strip()
            for item in re.split(r"[|,，;；/]+", value)
            if item.strip()
        }
    )


def truthy(value: object) -> bool:
    return str(value or "").strip().casefold() in TRUE_VALUES


def visual_row_is_risk(row: dict[str, str]) -> bool:
    explicit = " ".join(
        row.get(key, "")
        for key in ("risk_flags", "risk_reason", "review_risk", "identity_review")
    ).strip()
    if explicit or truthy(row.get("identity_required")):
        return True
    if split_identity_values(row.get("named_entities_expected", "")):
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
    if row.get("confidence", "").strip().casefold() in {
        "low",
        "medium",
        "低",
        "中",
    }:
        return True
    try:
        if float(row.get("retry_round") or 0) > 0:
            return True
    except ValueError:
        return True
    if row.get("ocr_collision_risk", "").strip().casefold() in {
        "high",
        "medium",
    }:
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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL line {line_number} is not an object")
        rows.append(value)
    return rows


def cue_id(row: dict[str, str], fallback: int) -> int | None:
    raw = row.get("line_id") or row.get("cue_id") or str(fallback)
    try:
        value = int(str(raw).strip())
    except ValueError:
        return None
    return value if value > 0 else None


def candidate_values(row: dict[str, str]) -> list[str]:
    return [row.get(f"candidate_{letter}", "").strip() for letter in "abc"]


def selected_range(row: dict[str, str]) -> tuple[float, float] | None:
    try:
        return float(row.get("source_in", "")), float(row.get("source_out", ""))
    except ValueError:
        return None


def caption_range(row: dict[str, str]) -> tuple[float, float] | None:
    start_value = row.get("caption_start", "") or row.get("start", "")
    end_value = row.get("caption_end", "") or row.get("end", "")
    try:
        return float(start_value), float(end_value)
    except ValueError:
        return None


def tsv_rows_differ(
    before: dict[str, str], after: dict[str, str]
) -> bool:
    return any(
        before.get(field, "") != after.get(field, "")
        for field in set(before) | set(after)
    )


def selected_candidate_pool_binding_failures(
    root: Path,
    rows: list[dict[str, str]],
    pool_rows: list[dict[str, Any]],
) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    match_by_id = {
        identity: row
        for index, row in enumerate(rows, start=1)
        if (identity := cue_id(row, index)) is not None
    }
    pool_by_id: dict[int, dict[str, Any]] = {}
    duplicate_ids: list[int] = []
    for index, entry in enumerate(pool_rows, start=1):
        try:
            identity = int(entry.get("cue_id") or entry.get("line_id"))
        except (AttributeError, TypeError, ValueError):
            failures.append(f"candidate pool row {index}: invalid cue ID")
            continue
        if identity in pool_by_id:
            duplicate_ids.append(identity)
        pool_by_id[identity] = entry
    if duplicate_ids:
        failures.append(f"duplicate candidate-pool cue IDs={duplicate_ids}")
    if set(pool_by_id) != set(match_by_id):
        failures.append(
            "candidate pool binding coverage missing="
            f"{sorted(set(match_by_id) - set(pool_by_id))}, "
            f"extra={sorted(set(pool_by_id) - set(match_by_id))}"
        )
    bound_ids: list[int] = []
    for identity in sorted(set(match_by_id) & set(pool_by_id)):
        row = match_by_id[identity]
        candidates = pool_by_id[identity].get("candidates", [])
        if not isinstance(candidates, list):
            failures.append(f"cue {identity}: candidate pool candidates is not a list")
            continue
        candidates_by_id = {
            str(candidate.get("candidate_id")): candidate
            for candidate in candidates
            if isinstance(candidate, dict) and candidate.get("candidate_id")
        }
        selected_id = str(row.get("selected_candidate_id", "")).strip()
        if not selected_id:
            failures.append(f"cue {identity}: selected_candidate_id is required")
            continue
        selected = candidates_by_id.get(selected_id)
        if selected is None:
            failures.append(
                f"cue {identity}: selected_candidate_id is not in candidate pool"
            )
            continue
        pool_source_id = str(selected.get("source_id") or "").strip()
        row_source_id = str(
            row.get("selected_source_id") or row.get("source_id") or ""
        ).strip()
        if pool_source_id and pool_source_id != row_source_id:
            failures.append(
                f"cue {identity}: selected pool source_id differs from match sheet"
            )
        pool_source_file = resolved_existing_file(
            root, selected.get("source_file", "")
        )
        row_source_file = resolved_existing_file(root, row.get("source_file", ""))
        if (
            pool_source_file is None
            or row_source_file is None
            or pool_source_file.resolve() != row_source_file.resolve()
        ):
            failures.append(
                f"cue {identity}: selected pool source_file differs from match sheet"
            )
        if {"source_in", "source_out"}.issubset(selected):
            try:
                if (
                    abs(float(selected["source_in"]) - float(row["source_in"]))
                    > 0.002
                    or abs(float(selected["source_out"]) - float(row["source_out"]))
                    > 0.022
                ):
                    failures.append(
                        f"cue {identity}: selected pool range differs from match sheet"
                    )
            except (KeyError, TypeError, ValueError):
                failures.append(
                    f"cue {identity}: selected pool range binding is invalid"
                )
        elif {"source_in_frame", "source_out_frame"}.issubset(selected):
            try:
                if (
                    int(selected["source_in_frame"])
                    != int(row["selected_source_in_frame"])
                    or int(selected["source_out_frame"])
                    != int(row["selected_source_out_frame"])
                ):
                    failures.append(
                        f"cue {identity}: selected pool frame range differs from match sheet"
                    )
            except (KeyError, TypeError, ValueError):
                failures.append(
                    f"cue {identity}: selected pool frame binding is missing"
                )
        else:
            failures.append(
                f"cue {identity}: selected candidate lacks a source range"
            )
        bound_ids.append(identity)
    return failures, {
        "candidate_pool_binding_rows": len(bound_ids),
        "candidate_pool_binding_failures": failures,
    }


def semantic_candidate_pool_failures(
    root: Path,
    rows: list[dict[str, str]],
    pool_rows: list[dict[str, Any]],
    *,
    normal_min_candidates: int,
    normal_max_candidates: int,
    risk_max_candidates: int,
    require_evidence: bool,
) -> tuple[list[str], dict[str, Any]]:
    """Bind one candidate-pool row to each semantic visual unit."""

    failures: list[str] = []
    units: dict[str, list[tuple[int, dict[str, str]]]] = {}
    unit_order: list[str] = []
    previous = ""
    closed: set[str] = set()
    for index, row in enumerate(rows, start=1):
        unit_id = row.get("visual_unit_id", "").strip()
        if not unit_id:
            failures.append(f"cue {index}: visual_unit_id is required")
            continue
        if unit_id != previous:
            if unit_id in closed:
                failures.append(f"visual unit {unit_id!r} is non-contiguous")
            if previous:
                closed.add(previous)
            unit_order.append(unit_id)
            previous = unit_id
        units.setdefault(unit_id, []).append((index, row))
    pool_by_unit: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(pool_rows, start=1):
        unit_id = str(entry.get("visual_unit_id", "")).strip()
        if not unit_id:
            failures.append(f"candidate pool row {index}: visual_unit_id is required")
            continue
        if unit_id in pool_by_unit:
            failures.append(f"duplicate candidate-pool visual_unit_id={unit_id!r}")
        pool_by_unit[unit_id] = entry
    if set(pool_by_unit) != set(units):
        failures.append(
            "semantic candidate pool coverage missing="
            f"{sorted(set(units) - set(pool_by_unit))}, "
            f"extra={sorted(set(pool_by_unit) - set(units))}"
        )
    cue_coverage: list[int] = []
    risk_units: list[str] = []
    normal_units: list[str] = []
    for position, unit_id in enumerate(unit_order):
        unit_rows = units.get(unit_id, [])
        entry = pool_by_unit.get(unit_id)
        if entry is None or not unit_rows:
            continue
        expected_cues = [identity for identity, _ in unit_rows]
        declared_cues: list[int] = []
        for raw in entry.get("cue_ids", []):
            try:
                declared_cues.append(int(raw))
            except (TypeError, ValueError):
                failures.append(f"visual unit {unit_id}: invalid cue ID={raw!r}")
        if declared_cues != expected_cues:
            failures.append(
                f"visual unit {unit_id}: cue_ids={declared_cues}, "
                f"expected={expected_cues}"
            )
        cue_coverage.extend(declared_cues)
        pool_id = str(entry.get("pool_id") or unit_id).strip()
        representative = unit_rows[0][1]
        shared_unit_fields = (
            "candidate_pool_id",
            "candidate_a",
            "candidate_a_id",
            "candidate_a_score",
            "candidate_a_source_id",
            "candidate_a_evidence",
            "candidate_b",
            "candidate_b_id",
            "candidate_b_score",
            "candidate_b_source_id",
            "candidate_b_evidence",
            "candidate_c",
            "candidate_c_id",
            "candidate_c_score",
            "candidate_c_source_id",
            "candidate_c_evidence",
            "selected_candidate",
            "selected_candidate_id",
            "selected_source_id",
            "source_id",
            "source_file",
            "source_in",
            "source_out",
        )
        for cue_identity, row in unit_rows:
            row_pool_id = str(row.get("candidate_pool_id") or unit_id).strip()
            if row_pool_id != pool_id:
                failures.append(
                    f"cue {cue_identity}: candidate_pool_id does not bind unit pool"
                )
            for field in shared_unit_fields:
                if row.get(field, "").strip() != representative.get(field, "").strip():
                    failures.append(
                        f"visual unit {unit_id}: cue {cue_identity} changes shared {field}"
                    )
        raw_flags = entry.get("risk_flags", [])
        if isinstance(raw_flags, str):
            raw_flags = split_identity_values(raw_flags)
        flags = {
            str(value).strip()
            for value in raw_flags
            if str(value).strip()
        } if isinstance(raw_flags, list) else set()
        unknown_flags = flags - ALLOWED_SEMANTIC_RISK_FLAGS
        if unknown_flags:
            failures.append(
                f"visual unit {unit_id}: unsupported risk_flags={sorted(unknown_flags)}"
            )
        if "user_reported" in flags and not str(
            entry.get("user_feedback_ref", "")
        ).strip():
            failures.append(
                f"visual unit {unit_id}: user_reported requires user_feedback_ref"
            )
        required_flags: set[str] = set()
        if position == 0:
            required_flags.add("opening")
        if position + 1 == len(unit_order):
            required_flags.add("ending")
        if any(
            split_identity_values(row.get("named_entities_expected", ""))
            or truthy(row.get("identity_required"))
            for _, row in unit_rows
        ):
            required_flags.add("identity")
        if any(
            row.get("confidence", "").strip().casefold()
            in {"low", "medium", "低", "中"}
            for _, row in unit_rows
        ):
            required_flags.add("low_confidence")
        if any(
            row.get("narrative_job", "").strip().casefold()
            in {"quote", "quote_or_evidence", "quotation", "evidence"}
            for _, row in unit_rows
        ):
            required_flags.add("quotation_evidence")
        missing_flags = required_flags - flags
        if missing_flags:
            failures.append(
                f"visual unit {unit_id}: missing derived risk_flags={sorted(missing_flags)}"
            )
        candidates = entry.get("candidates", [])
        if not isinstance(candidates, list):
            failures.append(f"visual unit {unit_id}: candidates must be a list")
            continue
        is_risk = bool(flags)
        if is_risk:
            risk_units.append(unit_id)
            if len(candidates) < 3 or len(candidates) > risk_max_candidates:
                failures.append(
                    f"visual unit {unit_id}: risk pool has {len(candidates)}, "
                    f"expected 3..{risk_max_candidates}"
                )
        else:
            normal_units.append(unit_id)
            if not normal_min_candidates <= len(candidates) <= normal_max_candidates:
                failures.append(
                    f"visual unit {unit_id}: normal pool has {len(candidates)}, "
                    f"expected {normal_min_candidates}..{normal_max_candidates}"
                )
        candidate_ids: set[str] = set()
        candidates_by_id: dict[str, dict[str, Any]] = {}
        for candidate_index, candidate in enumerate(candidates, start=1):
            if not isinstance(candidate, dict):
                failures.append(
                    f"visual unit {unit_id}: candidate {candidate_index} is not an object"
                )
                continue
            candidate_id = str(candidate.get("candidate_id", "")).strip()
            if not candidate_id or candidate_id in candidate_ids:
                failures.append(
                    f"visual unit {unit_id}: candidate {candidate_index} has "
                    "missing/duplicate candidate_id"
                )
            candidate_ids.add(candidate_id)
            candidates_by_id[candidate_id] = candidate
            if resolved_existing_file(root, candidate.get("source_file", "")) is None:
                failures.append(
                    f"visual unit {unit_id}: candidate {candidate_index} source missing"
                )
            if require_evidence:
                evidence = candidate.get("evidence", {})
                for sample in ("head", "mid", "tail"):
                    raw = candidate.get(f"{sample}_evidence")
                    if not raw and isinstance(evidence, dict):
                        raw = evidence.get(sample)
                    if isinstance(raw, dict):
                        raw = raw.get("path")
                    if resolved_existing_file(root, raw) is None:
                        failures.append(
                            f"visual unit {unit_id}: candidate {candidate_index} "
                            f"missing {sample} evidence"
                        )
        top_ids = [
            representative.get(f"candidate_{letter}_id", "").strip()
            for letter in "abc"
        ]
        if len(set(top_ids)) != 3 or any(not value for value in top_ids):
            failures.append(
                f"visual unit {unit_id}: requires three distinct A/B/C candidate IDs"
            )
        elif any(value not in candidate_ids for value in top_ids):
            failures.append(
                f"visual unit {unit_id}: A/B/C candidate IDs are outside unit pool"
            )
        selected_id = representative.get("selected_candidate_id", "").strip()
        selected = candidates_by_id.get(selected_id)
        if selected is None:
            failures.append(
                f"visual unit {unit_id}: selected_candidate_id is outside unit pool"
            )
            continue
        first_range = caption_range(unit_rows[0][1])
        last_range = caption_range(unit_rows[-1][1])
        unit_duration = (
            last_range[1] - first_range[0]
            if first_range is not None and last_range is not None
            else 0.0
        )
        try:
            source_in = float(representative.get("source_in", ""))
            source_out = float(representative.get("source_out", ""))
            if source_out - source_in + 0.05 < unit_duration:
                failures.append(
                    f"visual unit {unit_id}: selected source range is shorter "
                    "than the full semantic unit"
                )
            if (
                abs(float(selected["source_in"]) - source_in) > 0.002
                or abs(float(selected["source_out"]) - source_out) > 0.022
            ):
                failures.append(
                    f"visual unit {unit_id}: selected pool range differs from match sheet"
                )
        except (KeyError, TypeError, ValueError):
            failures.append(
                f"visual unit {unit_id}: selected source range binding is invalid"
            )
        selected_file = resolved_existing_file(root, selected.get("source_file", ""))
        row_file = resolved_existing_file(root, representative.get("source_file", ""))
        selected_source_id = str(selected.get("source_id", "")).strip()
        row_source_id = str(
            representative.get("selected_source_id")
            or representative.get("source_id")
            or ""
        ).strip()
        if selected_source_id and selected_source_id != row_source_id:
            failures.append(
                f"visual unit {unit_id}: selected pool source_id differs from match sheet"
            )
        if (
            selected_file is None
            or row_file is None
            or selected_file.resolve() != row_file.resolve()
        ):
            failures.append(
                f"visual unit {unit_id}: selected pool source differs from match sheet"
            )
    expected_cues = list(range(1, len(rows) + 1))
    if cue_coverage != expected_cues:
        failures.append(
            "semantic candidate pool cue/frame mapping must cover every cue "
            f"exactly once: got={cue_coverage}, expected={expected_cues}"
        )
    return failures, {
        "semantic_visual_units": len(units),
        "candidate_pool_rows": len(pool_rows),
        "normal_unit_ids": normal_units,
        "risk_unit_ids": risk_units,
        "cue_coverage": cue_coverage,
        "failures": failures,
    }


def candidate_pool_quality_failures(
    root: Path,
    rows: list[dict[str, str]],
    pool_rows: list[dict[str, Any]],
    *,
    min_candidates: int,
    preferred_candidates: int,
    require_evidence: bool,
    require_shortfall_evidence: bool,
    normal_max_candidates: int | None = None,
    risk_max_candidates: int | None = None,
) -> tuple[list[str], dict[str, Any]]:
    failures, metrics = selected_candidate_pool_binding_failures(
        root, rows, pool_rows
    )
    shortfall_ids: list[int] = []
    invalid_candidates: list[str] = []
    missing_evidence: list[str] = []
    for index, entry in enumerate(pool_rows, start=1):
        try:
            identity = int(entry.get("cue_id") or entry.get("line_id"))
        except (AttributeError, TypeError, ValueError):
            continue
        candidates = entry.get("candidates", [])
        if not isinstance(candidates, list):
            continue
        if len(candidates) < min_candidates:
            failures.append(
                f"cue {identity}: candidate pool has {len(candidates)}, "
                f"expected>={min_candidates}"
            )
            continue
        if len(candidates) < preferred_candidates:
            shortfall_ids.append(identity)
            if require_shortfall_evidence:
                if not str(
                    entry.get("candidate_shortfall_reason") or ""
                ).strip():
                    failures.append(
                        f"cue {identity}: candidate pool below preferred size "
                        "without candidate_shortfall_reason"
                    )
                expansion_attempts = entry.get("candidate_expansion_attempts")
                if not isinstance(expansion_attempts, list) or not (
                    expansion_attempts
                ):
                    failures.append(
                        f"cue {identity}: candidate pool below preferred size "
                        "without candidate_expansion_attempts"
                    )
        risk_values = entry.get("risk_flags") or entry.get("risk_reasons") or []
        is_risk = bool(risk_values) or str(entry.get("risk_tier", "")).strip().lower() in {
            "risk",
            "high",
            "medium",
            "风险",
            "高",
            "中",
        }
        maximum = risk_max_candidates if is_risk else normal_max_candidates
        if maximum is not None and len(candidates) > maximum:
            failures.append(
                f"cue {identity}: {'risk' if is_risk else 'normal'} candidate "
                f"pool has {len(candidates)}, expected<={maximum}"
            )
        candidate_ids: set[str] = set()
        for candidate_index, candidate in enumerate(candidates, start=1):
            if not isinstance(candidate, dict):
                invalid_candidates.append(
                    f"{identity}:{candidate_index}:not_object"
                )
                continue
            candidate_id_value = str(
                candidate.get("candidate_id") or ""
            ).strip()
            if not candidate_id_value or candidate_id_value in candidate_ids:
                invalid_candidates.append(
                    f"{identity}:{candidate_index}:candidate_id"
                )
            candidate_ids.add(candidate_id_value)
            if resolved_existing_file(
                root, candidate.get("source_file", "")
            ) is None:
                invalid_candidates.append(
                    f"{identity}:{candidate_index}:source_file"
                )
            try:
                if (
                    "source_in_frame" in candidate
                    or "source_out_frame" in candidate
                ):
                    source_in = int(candidate["source_in_frame"])
                    source_out = int(candidate["source_out_frame"])
                else:
                    source_in = float(candidate["source_in"])
                    source_out = float(candidate["source_out"])
                if source_out <= source_in:
                    raise ValueError
            except (KeyError, TypeError, ValueError):
                invalid_candidates.append(
                    f"{identity}:{candidate_index}:source_range"
                )
            if require_evidence:
                evidence = candidate.get("evidence", {})
                for sample in ("head", "mid", "tail"):
                    raw_evidence = candidate.get(f"{sample}_evidence")
                    if not raw_evidence and isinstance(evidence, dict):
                        raw_evidence = evidence.get(sample)
                    if isinstance(raw_evidence, dict):
                        raw_evidence = raw_evidence.get("path")
                    if resolved_existing_file(root, raw_evidence) is None:
                        missing_evidence.append(
                            f"{identity}:{candidate_index}:{sample}"
                        )
    if invalid_candidates:
        failures.append(
            f"invalid candidate-pool entries={invalid_candidates[:30]}"
        )
    if missing_evidence:
        failures.append(
            "missing candidate-pool head/mid/tail evidence="
            f"{missing_evidence[:30]}"
        )
    return failures, {
        **metrics,
        "min_candidates": min_candidates,
        "preferred_candidates": preferred_candidates,
        "shortfall_cue_ids": shortfall_ids,
        "invalid_candidates": invalid_candidates,
        "missing_candidate_evidence": missing_evidence,
    }


def semantic_review_failures(
    root: Path,
    review_path: Path,
    review: dict[str, Any],
    match_sheet_path: Path,
    evidence_manifest_path: Path,
    candidate_pool_path: Path,
    check: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    """Verify selected/risk evidence once per semantic visual unit."""

    failures: list[str] = []
    _, match_rows = read_tsv(match_sheet_path)
    _, evidence_rows = read_tsv(evidence_manifest_path)
    pool_rows = read_jsonl(candidate_pool_path)
    units: dict[str, list[tuple[int, dict[str, str]]]] = {}
    unit_order: list[str] = []
    for cue_identity, row in enumerate(match_rows, start=1):
        unit_id = row.get("visual_unit_id", "").strip()
        if not unit_id:
            failures.append(f"cue {cue_identity}: visual_unit_id is required")
            continue
        if unit_id not in units:
            unit_order.append(unit_id)
        units.setdefault(unit_id, []).append((cue_identity, row))
    pool_by_unit: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(pool_rows, start=1):
        unit_id = str(entry.get("visual_unit_id", "")).strip()
        if not unit_id or unit_id in pool_by_unit:
            failures.append(
                f"candidate pool row {index}: missing/duplicate visual_unit_id"
            )
            continue
        pool_by_unit[unit_id] = entry
    if set(pool_by_unit) != set(units):
        failures.append("semantic review candidate-pool unit coverage is invalid")
    layered_review = bool(check.get("require_layered_review", False))
    trusted_paths: dict[Path, dict[str, Any]] = {}
    selected_sheet_units: set[str] = set()
    risk_sheet_units: set[str] = set()
    cue_to_unit = {
        cue_identity: unit_id
        for unit_id, unit_rows in units.items()
        for cue_identity, _ in unit_rows
    }
    raw_files = review.get("files", [])
    if layered_review and (not isinstance(raw_files, list) or not raw_files):
        failures.append("semantic review must list trusted evidence files")
        raw_files = []
    for file_index, record in enumerate(
        raw_files if isinstance(raw_files, list) else []
    ):
        if (
            not isinstance(record, dict)
            or not str(record.get("path", "")).strip()
            or not str(record.get("sha256", "")).strip()
        ):
            failures.append(
                f"semantic trusted-file record {file_index} lacks path/sha256"
            )
            continue
        raw_path = Path(str(record["path"])).expanduser()
        file_path = (
            raw_path.resolve()
            if raw_path.is_absolute()
            else (review_path.parent / raw_path).resolve()
        )
        if file_path in trusted_paths:
            failures.append(
                f"semantic review duplicates trusted evidence file={file_path}"
            )
        trusted_paths[file_path] = record
        if not file_path.is_file():
            failures.append(f"semantic review evidence file is missing={file_path}")
        elif file_sha256(file_path) != str(record["sha256"]).strip().lower():
            failures.append(
                f"semantic review evidence file hash mismatch={file_path}"
            )
        referenced_units = {
            str(value).strip()
            for value in record.get("visual_unit_ids", [])
            if str(value).strip()
        } if isinstance(record.get("visual_unit_ids", []), list) else set()
        if isinstance(record.get("cue_ids", []), list):
            for raw_cue in record.get("cue_ids", []):
                try:
                    cue_identity = int(raw_cue)
                except (TypeError, ValueError):
                    failures.append(
                        f"semantic trusted-file record {file_index} has invalid cue={raw_cue!r}"
                    )
                    continue
                if cue_identity in cue_to_unit:
                    referenced_units.add(cue_to_unit[cue_identity])
        if record.get("kind") == "selected_sheet":
            selected_sheet_units.update(referenced_units)
        elif record.get("kind") == "risk_abc_sheet":
            risk_sheet_units.update(referenced_units)
    evidence_by_unit: dict[str, dict[str, str]] = {}
    for index, row in enumerate(evidence_rows, start=1):
        unit_id = row.get("visual_unit_id", "").strip()
        if not unit_id or unit_id in evidence_by_unit:
            failures.append(
                f"semantic evidence row {index}: missing/duplicate visual_unit_id"
            )
            continue
        evidence_by_unit[unit_id] = row
    if set(evidence_by_unit) != set(units):
        failures.append(
            "semantic selected evidence coverage missing="
            f"{sorted(set(units) - set(evidence_by_unit))}, "
            f"extra={sorted(set(evidence_by_unit) - set(units))}"
        )
    for unit_id in unit_order:
        unit_rows = units.get(unit_id, [])
        evidence = evidence_by_unit.get(unit_id)
        if not unit_rows or evidence is None:
            continue
        expected_cues = [identity for identity, _ in unit_rows]
        declared_cues: list[int] = []
        for raw in split_identity_values(evidence.get("cue_ids", "")):
            try:
                declared_cues.append(int(raw))
            except ValueError:
                failures.append(f"visual unit {unit_id}: invalid evidence cue={raw!r}")
        if declared_cues != expected_cues:
            failures.append(
                f"visual unit {unit_id}: evidence cue_ids={declared_cues}, "
                f"expected={expected_cues}"
            )
        selected = unit_rows[0][1]
        selected_candidate_id = selected.get("selected_candidate_id", "").strip()
        if evidence.get("selected_candidate_id", "").strip() != selected_candidate_id:
            failures.append(
                f"visual unit {unit_id}: evidence selected_candidate_id differs "
                "from match sheet"
            )
        evidence_source_id = evidence.get("source_id", "").strip()
        selected_source_id = (
            selected.get("selected_source_id", "").strip()
            or selected.get("source_id", "").strip()
        )
        if evidence_source_id != selected_source_id:
            failures.append(
                f"visual unit {unit_id}: evidence source_id differs from match sheet"
            )
        evidence_source = resolved_existing_file(root, evidence.get("source_file", ""))
        selected_source = resolved_existing_file(root, selected.get("source_file", ""))
        if (
            evidence_source is None
            or selected_source is None
            or evidence_source.resolve() != selected_source.resolve()
        ):
            failures.append(
                f"visual unit {unit_id}: evidence source_file differs from match sheet"
            )
        try:
            evidence_in = float(evidence.get("source_in", ""))
            evidence_out = float(evidence.get("source_out", ""))
            selected_in = float(selected.get("source_in", ""))
            selected_out = float(selected.get("source_out", ""))
            timestamp = float(evidence.get("timestamp", ""))
            if (
                abs(evidence_in - selected_in) > 0.002
                or abs(evidence_out - selected_out) > 0.022
                or timestamp < evidence_in - 0.002
                or timestamp > evidence_out + 0.002
            ):
                raise ValueError
        except (TypeError, ValueError):
            failures.append(
                f"visual unit {unit_id}: selected evidence range/timestamp mismatch"
            )
        image = resolved_existing_file(
            root,
            evidence.get("evidence_image", "")
            or evidence.get("evidence_path", ""),
        )
        if image is None:
            failures.append(f"visual unit {unit_id}: evidence image is missing")
        else:
            image_sha = file_sha256(image)
            declared_image_sha = (
                evidence.get("evidence_sha256", "").strip()
                or evidence.get("sha256", "").strip()
            ).lower()
            if declared_image_sha != image_sha:
                failures.append(
                    f"visual unit {unit_id}: selected evidence image SHA mismatch"
                )
            if layered_review and image.resolve() not in trusted_paths:
                failures.append(
                    f"visual unit {unit_id}: selected evidence is not in trusted files"
                )
        if evidence.get("visual_review", "").strip().lower() not in {
            "approved_manual",
            "approved",
            "verified",
            "pass",
        }:
            failures.append(f"visual unit {unit_id}: evidence is not approved")
    selected_reviewed = [
        str(value).strip()
        for value in review.get("selected_reviewed_visual_unit_ids", [])
        if str(value).strip()
    ]
    if selected_reviewed != unit_order:
        failures.append(
            "selected review must cover every visual unit exactly once in order"
        )
    risk_units = {
        unit_id
        for unit_id, entry in pool_by_unit.items()
        if entry.get("risk_flags")
    }
    declared_risk = {
        str(value).strip()
        for value in review.get("risk_visual_unit_ids", [])
        if str(value).strip()
    }
    if declared_risk != risk_units:
        failures.append("risk visual-unit declaration differs from candidate pool")
    if check.get("require_contact_sheets", False):
        if selected_sheet_units != set(units):
            failures.append(
                "selected contact-sheet unit coverage missing="
                f"{sorted(set(units) - selected_sheet_units)}, "
                f"extra={sorted(selected_sheet_units - set(units))}"
            )
        if risk_sheet_units != risk_units:
            failures.append(
                "risk A/B/C contact-sheet unit coverage missing="
                f"{sorted(risk_units - risk_sheet_units)}, "
                f"extra={sorted(risk_sheet_units - risk_units)}"
            )
    if check.get("require_risk_frame_matrix", False):
        actual: set[tuple[str, str, str]] = set()
        raw_matrix = review.get("risk_matrix", [])
        for index, item in enumerate(raw_matrix if isinstance(raw_matrix, list) else []):
            if not isinstance(item, dict):
                failures.append(f"risk matrix row {index} is not an object")
                continue
            key = (
                str(item.get("visual_unit_id", "")).strip(),
                str(item.get("candidate", "")).strip().upper(),
                str(item.get("sample", "")).strip().lower(),
            )
            if key in actual:
                failures.append(f"duplicate semantic risk evidence={key}")
            actual.add(key)
            unit_id, view, sample = key
            match_unit_rows = units.get(unit_id, [])
            representative = match_unit_rows[0][1] if match_unit_rows else {}
            expected_candidate_id = representative.get(
                f"candidate_{view.lower()}_id", ""
            ).strip()
            pool_candidates = {
                str(candidate.get("candidate_id", "")).strip(): candidate
                for candidate in pool_by_unit.get(unit_id, {}).get("candidates", [])
                if isinstance(candidate, dict)
                and str(candidate.get("candidate_id", "")).strip()
            }
            pool_candidate = pool_candidates.get(expected_candidate_id)
            if not expected_candidate_id:
                failures.append(
                    f"visual unit {unit_id}: candidate {view} ID is missing"
                )
            elif pool_candidate is None:
                failures.append(
                    f"visual unit {unit_id}: candidate {view} is outside unit pool"
                )
            if str(item.get("candidate_id", "")).strip() != expected_candidate_id:
                failures.append(f"risk evidence candidate_id mismatch={key}")
            image = resolved_existing_file(
                root, item.get("evidence_path") or item.get("path")
            )
            if image is None:
                failures.append(f"risk evidence is missing={key}")
            elif str(item.get("sha256", "")).lower() != file_sha256(image):
                failures.append(f"risk evidence hash mismatch={key}")
            elif layered_review and image.resolve() not in trusted_paths:
                failures.append(f"risk evidence is not in trusted files={key}")
            if str(item.get("status", "")).upper() != "PASS":
                failures.append(f"risk evidence did not pass={key}")
            if pool_candidate is not None:
                record_source = resolved_existing_file(
                    root, item.get("source_file", "")
                )
                pool_source = resolved_existing_file(
                    root, pool_candidate.get("source_file", "")
                )
                if (
                    record_source is None
                    or pool_source is None
                    or record_source.resolve() != pool_source.resolve()
                ):
                    failures.append(f"risk evidence source_file mismatch={key}")
                if str(item.get("source_id", "")).strip() != str(
                    pool_candidate.get("source_id", "")
                ).strip():
                    failures.append(f"risk evidence source_id mismatch={key}")
                try:
                    record_in = float(item["source_in"])
                    record_out = float(item["source_out"])
                    pool_in = float(pool_candidate["source_in"])
                    pool_out = float(pool_candidate["source_out"])
                    timestamp = float(item["timestamp"])
                    if (
                        abs(record_in - pool_in) > 0.002
                        or abs(record_out - pool_out) > 0.022
                        or timestamp < record_in - 0.002
                        or timestamp > record_out + 0.002
                    ):
                        raise ValueError
                except (KeyError, TypeError, ValueError):
                    failures.append(
                        f"risk evidence source range/timestamp mismatch={key}"
                    )
        expected = {
            (unit_id, candidate, sample)
            for unit_id in risk_units
            for candidate in ("A", "B", "C")
            for sample in ("head", "mid", "tail")
        }
        if actual != expected:
            failures.append(
                f"semantic risk matrix missing={sorted(expected - actual)}, "
                f"extra={sorted(actual - expected)}"
            )
    raw_ranges = review.get("unit_range_reviews", [])
    reviewed_units = [
        str(item.get("visual_unit_id", "")).strip()
        for item in raw_ranges
        if isinstance(item, dict)
        and str(item.get("status", "")).upper() == "PASS"
    ] if isinstance(raw_ranges, list) else []
    if check.get("require_range_reviews", True) and reviewed_units != unit_order:
        failures.append(
            "unit range reviews must cover every visual unit exactly once in order"
        )
    mapping = review.get("cue_frame_mapping", [])
    mapped_cues: list[int] = []
    previous_end = 0
    for index, item in enumerate(mapping if isinstance(mapping, list) else [], start=1):
        if not isinstance(item, dict):
            failures.append(f"cue/frame mapping row {index} is not an object")
            continue
        try:
            cue_identity = int(item["cue_id"])
            start_frame = int(item["output_start_frame"])
            end_frame = int(item["output_end_frame"])
        except (KeyError, TypeError, ValueError):
            failures.append(f"cue/frame mapping row {index} is invalid")
            continue
        mapped_cues.append(cue_identity)
        if start_frame != previous_end or end_frame <= start_frame:
            failures.append(f"cue {cue_identity}: frame mapping is not continuous")
        previous_end = end_frame
        expected_unit = (
            match_rows[cue_identity - 1].get("visual_unit_id", "").strip()
            if 0 < cue_identity <= len(match_rows)
            else ""
        )
        if str(item.get("visual_unit_id", "")).strip() != expected_unit:
            failures.append(f"cue {cue_identity}: frame mapping unit mismatch")
    if mapped_cues != list(range(1, len(match_rows) + 1)):
        failures.append("cue/frame mapping must cover every cue exactly once in order")
    identity_checks = {
        str(item.get("visual_unit_id", "")).strip(): item
        for item in review.get("identity_checks", [])
        if isinstance(item, dict)
    }
    if check.get("require_named_identity", True):
        for unit_id, unit_rows in units.items():
            if not any(
                split_identity_values(row.get("named_entities_expected", ""))
                for _, row in unit_rows
            ):
                continue
            if str(identity_checks.get(unit_id, {}).get("status", "")).upper() != "PASS":
                failures.append(
                    f"visual unit {unit_id}: named identity check is unresolved"
                )
    for section_name, required in (
        ("opening_review", check.get("require_opening_review", False)),
        ("ending_review", check.get("require_ending_review", False)),
    ):
        if required and str(review.get(section_name, {}).get("status", "")).upper() != "PASS":
            failures.append(f"semantic review lacks PASS {section_name}")
    match_sha = file_sha256(match_sheet_path)
    evidence_sha = file_sha256(evidence_manifest_path)
    pool_sha = file_sha256(candidate_pool_path)
    for label, actual, expected in (
        ("match_sheet", match_sha, manifest_hash_value(review, "match_sheet_sha256")),
        ("evidence_manifest", evidence_sha, manifest_hash_value(review, "evidence_manifest_sha256")),
        ("candidate_pool", pool_sha, manifest_hash_value(review, "candidate_pool_sha256")),
    ):
        if actual != expected:
            failures.append(f"review manifest has stale {label}_sha256")
    if int(review.get("row_count", -1)) != len(match_rows):
        failures.append("review manifest row_count mismatch")
    if int(review.get("visual_unit_count", -1)) != len(units):
        failures.append("review manifest visual_unit_count mismatch")
    unresolved = sorted(
        {
            str(value).strip()
            for value in review.get("unresolved_visual_unit_ids", [])
            if str(value).strip()
        }
    )
    allow_unresolved = bool(check.get("allow_unresolved", False))
    status = str(review.get("status", "")).upper()
    allowed = {"PASS", "NEEDS_REPAIR"} if allow_unresolved else {"PASS"}
    if status not in allowed:
        failures.append(f"semantic review status={status!r} is invalid")
    if status == "NEEDS_REPAIR" and not unresolved:
        failures.append("NEEDS_REPAIR review must name unresolved visual units")
    if not allow_unresolved and unresolved:
        failures.append(f"unresolved visual units remain={unresolved}")
    workflow_ready = status == "PASS" and not unresolved and not failures
    return failures, {
        "status": status,
        "rows": len(match_rows),
        "visual_units": len(units),
        "evidence_rows": len(evidence_rows),
        "risk_visual_unit_ids": sorted(risk_units),
        "unresolved_visual_unit_ids": unresolved,
        "cue_frame_mapping_rows": len(mapped_cues),
        "workflow_ready": workflow_ready,
        "match_sheet_sha256": match_sha,
        "evidence_manifest_sha256": evidence_sha,
        "candidate_pool_sha256": pool_sha,
        "review_manifest_sha256": file_sha256(review_path),
        "failures": failures,
    }


def candidate_source_manifest_failures(
    root: Path,
    pool_rows: list[dict[str, Any]],
    source_manifest_path: Path,
) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    source_manifest = json.loads(
        source_manifest_path.read_text(encoding="utf-8")
    )
    source_entries: list[dict[str, Any]] = []
    if isinstance(source_manifest, dict):
        for field in ("sources", "primary_sources", "auxiliary_assets"):
            values = source_manifest.get(field, [])
            if isinstance(values, list):
                source_entries.extend(
                    item for item in values if isinstance(item, dict)
                )
    elif isinstance(source_manifest, list):
        source_entries = [
            item for item in source_manifest if isinstance(item, dict)
        ]
    source_paths: dict[str, Path] = {}
    for entry in source_entries:
        identity = str(
            entry.get("source_id") or entry.get("asset_id") or ""
        ).strip()
        source_file = resolved_existing_file(
            root,
            entry.get("real_path")
            or entry.get("path")
            or entry.get("local_path"),
        )
        if identity and source_file is not None:
            source_paths[identity] = source_file.resolve()
    if not source_paths:
        failures.append("bound source manifest has no usable sources")
    invalid: list[str] = []
    for entry_index, pool_entry in enumerate(pool_rows, start=1):
        identity = pool_entry.get("cue_id") or pool_entry.get("line_id")
        for candidate_index, candidate in enumerate(
            pool_entry.get("candidates", []), start=1
        ):
            if not isinstance(candidate, dict):
                continue
            source_id = str(candidate.get("source_id") or "").strip()
            source_file = resolved_existing_file(
                root, candidate.get("source_file", "")
            )
            expected = source_paths.get(source_id)
            if expected is None:
                invalid.append(
                    f"{identity}:{candidate_index}:unknown_source_id"
                )
            elif (
                source_file is None or source_file.resolve() != expected
            ):
                invalid.append(
                    f"{identity}:{candidate_index}:source_identity_file"
                )
    if invalid:
        failures.append(
            f"candidate sources are outside bound source manifest={invalid[:30]}"
        )
    return failures, {
        "source_manifest_sha256": file_sha256(source_manifest_path),
        "source_count": len(source_paths),
        "invalid_candidate_sources": invalid,
    }


def _match_plan_failures(
    root: Path,
    match_sheet_path: Path,
    canonical_srt_path: Path | None,
    *,
    min_candidates: int,
    max_reuse: int | None,
    timing_tolerance_ms: float,
    require_candidate_evidence: bool,
    required_qa_status: str | None = None,
    require_candidate_ids: bool = False,
    require_semantic_visual_units: bool = False,
    min_semantic_unit_duration_seconds: float = 4.0,
    max_semantic_unit_duration_seconds: float = 8.0,
) -> tuple[list[str], dict[str, Any], list[dict[str, str]]]:
    fields, rows = read_tsv(match_sheet_path)
    failures: list[str] = []
    required_fields = {
        "line_id",
        "text",
        "candidate_a",
        "candidate_a_score",
        "candidate_b",
        "candidate_b_score",
        "candidate_c",
        "candidate_c_score",
        "source_id",
        "source_file",
        "source_in",
        "source_out",
        "match_reason",
        "confidence",
        "retry_round",
        "reuse_group",
        "qa_status",
    }
    if not {"caption_start", "start"} & set(fields):
        required_fields.add("start")
    if not {"caption_end", "end"} & set(fields):
        required_fields.add("end")
    missing_fields = sorted(required_fields - set(fields))
    if require_candidate_ids:
        candidate_id_fields = {
            "candidate_a_id",
            "candidate_b_id",
            "candidate_c_id",
            "selected_candidate_id",
        }
        missing_fields.extend(
            sorted(candidate_id_fields - set(fields))
        )
        missing_fields = sorted(set(missing_fields))
    if require_semantic_visual_units and "visual_unit_id" not in fields:
        missing_fields.append("visual_unit_id")
        missing_fields = sorted(set(missing_fields))
    if missing_fields:
        failures.append(f"missing columns={missing_fields}")

    ids: list[int] = []
    three_candidate_rows = 0
    selected_rows = 0
    low_confidence_rows: list[int] = []
    candidate_exception_rows: list[int] = []
    reuse_counts: dict[str, int] = {}
    tolerance = timing_tolerance_ms / 1000.0
    srt_entries = parse_srt_entries(canonical_srt_path) if canonical_srt_path else []
    if canonical_srt_path and len(rows) != len(srt_entries):
        failures.append(f"row_count={len(rows)}, srt_count={len(srt_entries)}")

    for row_number, row in enumerate(rows, start=1):
        line_id = cue_id(row, row_number)
        if line_id is None:
            failures.append(f"row {row_number}: invalid line_id={row.get('line_id')!r}")
            continue
        ids.append(line_id)
        candidates = candidate_values(row)
        candidate_ids = [
            row.get(f"candidate_{letter}_id", "").strip()
            for letter in "abc"
        ]
        if require_candidate_ids and (
            any(not value for value in candidate_ids)
            or len(set(candidate_ids)) != 3
        ):
            failures.append(
                f"cue {line_id}: requires three nonempty distinct candidate IDs"
            )
        candidate_exception = row.get("candidate_exception", "").strip()
        nonempty = [value for value in candidates if value]
        normalized = [unicodedata.normalize("NFKC", value).strip().casefold() for value in nonempty]
        if len(nonempty) >= min_candidates and len(set(normalized)) == len(nonempty):
            three_candidate_rows += 1
        elif candidate_exception:
            candidate_exception_rows.append(line_id)
        else:
            failures.append(
                f"cue {line_id}: requires {min_candidates} nonempty distinct candidates"
            )
        for letter, candidate in zip("abc", candidates):
            score = row.get(f"candidate_{letter}_score", "").strip()
            if candidate:
                try:
                    float(score)
                except ValueError:
                    failures.append(f"cue {line_id}: candidate_{letter}_score is not numeric")
                if require_candidate_evidence:
                    evidence = resolved_existing_file(
                        root, row.get(f"candidate_{letter}_evidence", "")
                    )
                    if evidence is None:
                        failures.append(f"cue {line_id}: candidate_{letter}_evidence missing")

        status = row.get("qa_status", "").strip().lower()
        if status not in {
            "machine_proposed",
            "planned",
            "reviewed",
            "verified",
            "render_ready",
            "card",
            "approved",
        }:
            failures.append(f"cue {line_id}: invalid qa_status={status!r}")
        if required_qa_status and status != required_qa_status.casefold():
            failures.append(
                f"cue {line_id}: qa_status={status!r}, "
                f"expected {required_qa_status!r}"
            )
        selected_file = resolved_existing_file(root, row.get("source_file", ""))
        if selected_file is None:
            failures.append(f"cue {line_id}: selected source_file is missing")
        else:
            selected_rows += 1
        if not row.get("match_reason", "").strip():
            failures.append(f"cue {line_id}: match_reason missing")
        chosen = row.get("selected_candidate", "").strip().upper()
        if chosen and chosen not in {"A", "B", "C", "CARD", "MANUAL"}:
            failures.append(f"cue {line_id}: invalid selected_candidate={chosen!r}")
        elif chosen in {"A", "B", "C"} and not row.get(
            f"candidate_{chosen.lower()}", ""
        ).strip():
            failures.append(f"cue {line_id}: selected candidate {chosen} is empty")
        elif chosen in {"A", "B", "C"}:
            letter = chosen.lower()
            if require_candidate_ids and row.get(
                "selected_candidate_id", ""
            ).strip() != row.get(f"candidate_{letter}_id", "").strip():
                failures.append(
                    f"cue {line_id}: selected_candidate_id does not match "
                    f"candidate {chosen}"
                )
            chosen_reference = row.get(f"candidate_{letter}", "").strip()
            selected_source_id = row.get("source_id", "").strip()
            candidate_source_id = row.get(
                f"candidate_{letter}_source_id", ""
            ).strip()
            if candidate_source_id:
                if candidate_source_id != selected_source_id:
                    failures.append(
                        f"cue {line_id}: selected source_id does not match "
                        f"candidate {chosen}"
                    )
            elif selected_source_id and selected_source_id.casefold() not in (
                chosen_reference.casefold()
            ):
                failures.append(
                    f"cue {line_id}: candidate {chosen} does not bind selected "
                    f"source_id={selected_source_id!r}"
                )

        source_range = selected_range(row)
        cue_range = caption_range(row)
        if source_range is None:
            failures.append(f"cue {line_id}: invalid selected source range")
        elif source_range[1] <= source_range[0]:
            failures.append(f"cue {line_id}: source_out must be after source_in")
        elif cue_range and status != "card":
            cue_duration = cue_range[1] - cue_range[0]
            if source_range[1] - source_range[0] + 0.05 < cue_duration:
                failures.append(f"cue {line_id}: selected source is shorter than cue")
        if cue_range is None or cue_range[1] <= cue_range[0]:
            failures.append(f"cue {line_id}: invalid caption range")

        confidence = row.get("confidence", "").strip().lower()
        try:
            retry_round = int(float(row.get("retry_round", "0") or 0))
        except ValueError:
            failures.append(f"cue {line_id}: retry_round is not numeric")
            retry_round = 0
        if confidence in {"low", "低"}:
            low_confidence_rows.append(line_id)
            if retry_round < 1:
                failures.append(f"cue {line_id}: low confidence without retry")

        group = row.get("reuse_group", "").strip()
        if group:
            reuse_counts[group] = reuse_counts.get(group, 0) + 1

        if canonical_srt_path and row_number <= len(srt_entries):
            entry = srt_entries[row_number - 1]
            if line_id != entry["index"]:
                failures.append(
                    f"cue {line_id}: expected SRT index {entry['index']} at row {row_number}"
                )
            if row.get("text", "").strip() != entry["text"]:
                failures.append(f"cue {line_id}: text differs from canonical SRT")
            if cue_range:
                if abs(cue_range[0] - entry["start"]) > tolerance:
                    failures.append(f"cue {line_id}: start differs from canonical SRT")
                if abs(cue_range[1] - entry["end"]) > tolerance:
                    failures.append(f"cue {line_id}: end differs from canonical SRT")

    expected_ids = list(range(1, len(rows) + 1))
    if ids != expected_ids:
        failures.append("line_id sequence must be continuous from 1")
    reuse_over_limit = (
        {
            group: count
            for group, count in reuse_counts.items()
            if max_reuse is not None and count > max_reuse
        }
        if max_reuse is not None
        else {}
    )
    if reuse_over_limit:
        failures.append(f"reuse_over_limit={reuse_over_limit}")
    semantic_unit_count = 0
    semantic_unit_durations: dict[str, float] = {}
    if require_semantic_visual_units and "visual_unit_id" in fields:
        grouped: dict[str, list[tuple[int, dict[str, str]]]] = {}
        unit_order: list[str] = []
        closed_units: set[str] = set()
        previous_unit = ""
        for row_number, row in enumerate(rows, start=1):
            unit_id = row.get("visual_unit_id", "").strip()
            if not unit_id:
                failures.append(f"cue {row_number}: visual_unit_id is empty")
                continue
            if unit_id != previous_unit:
                if unit_id in closed_units:
                    failures.append(
                        f"visual unit {unit_id!r} is non-contiguous in the match sheet"
                    )
                if previous_unit:
                    closed_units.add(previous_unit)
                unit_order.append(unit_id)
                previous_unit = unit_id
            grouped.setdefault(unit_id, []).append((row_number, row))
        semantic_unit_count = len(grouped)
        for unit_id in unit_order:
            unit_rows = grouped.get(unit_id, [])
            ranges = [caption_range(row) for _, row in unit_rows]
            if not ranges or any(value is None for value in ranges):
                failures.append(f"visual unit {unit_id!r} has an invalid caption range")
                continue
            concrete_ranges = [value for value in ranges if value is not None]
            duration = concrete_ranges[-1][1] - concrete_ranges[0][0]
            semantic_unit_durations[unit_id] = duration
            exception = next(
                (
                    row.get("visual_unit_exception", "").strip()
                    for _, row in unit_rows
                    if row.get("visual_unit_exception", "").strip()
                ),
                "",
            )
            if (
                duration < min_semantic_unit_duration_seconds
                or duration > max_semantic_unit_duration_seconds
            ) and not exception:
                failures.append(
                    f"visual unit {unit_id!r} duration={duration:.3f}s is outside "
                    f"{min_semantic_unit_duration_seconds:.3f}.."
                    f"{max_semantic_unit_duration_seconds:.3f}s without "
                    "visual_unit_exception"
                )
            shared_fields = (
                "candidate_pool_id",
                "candidate_a",
                "candidate_a_id",
                "candidate_a_score",
                "candidate_a_source_id",
                "candidate_a_evidence",
                "candidate_b",
                "candidate_b_id",
                "candidate_b_score",
                "candidate_b_source_id",
                "candidate_b_evidence",
                "candidate_c",
                "candidate_c_id",
                "candidate_c_score",
                "candidate_c_source_id",
                "candidate_c_evidence",
                "selected_candidate",
                "source_id",
                "source_file",
                "source_in",
                "source_out",
                "selected_candidate_id",
                "selected_source_id",
            )
            for field in shared_fields:
                values = {
                    row.get(field, "").strip()
                    for _, row in unit_rows
                }
                if len(values) > 1:
                    failures.append(
                        f"visual unit {unit_id!r} does not share one {field}"
                    )
    metrics = {
        "rows": len(rows),
        "three_candidate_rows": three_candidate_rows,
        "candidate_exception_rows": candidate_exception_rows,
        "selected_rows": selected_rows,
        "low_confidence_rows": low_confidence_rows,
        "reuse_over_limit": reuse_over_limit,
        "semantic_visual_units": semantic_unit_count,
        "semantic_visual_unit_durations": semantic_unit_durations,
        "match_sheet_sha256": file_sha256(match_sheet_path),
        "canonical_srt_sha256": file_sha256(canonical_srt_path)
        if canonical_srt_path
        else "",
        "failures": failures,
    }
    return failures, metrics, rows


def _parse_review_range(value: object) -> tuple[int, int] | None:
    if isinstance(value, dict):
        try:
            return int(value["start"]), int(value["end"])
        except (KeyError, TypeError, ValueError):
            return None
    match = re.fullmatch(r"\s*(\d+)\s*[-–—]\s*(\d+)\s*", str(value))
    return (int(match.group(1)), int(match.group(2))) if match else None


def _media_contract(
    path: Path,
    timing_contract_path: Path,
    *,
    frame_tolerance: int = 0,
    fps_tolerance: float = 0.02,
) -> tuple[list[str], dict[str, Any]]:
    contract = json.loads(timing_contract_path.read_text(encoding="utf-8"))
    probe = ffprobe_json(path, count_frames=True)
    streams = probe.get("streams", [])
    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    video = video_streams[0] if video_streams else {}
    duration = float(probe.get("format", {}).get("duration", 0.0) or 0.0)
    fps_text = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
    fps = float(Fraction(fps_text)) if fps_text != "0/0" else 0.0
    frames = int(
        video.get("nb_read_frames")
        or video.get("nb_frames")
        or round(duration * fps)
    )
    expected_frames = int(contract["target_frame_count"])
    expected_fps = float(contract["fps"])
    failures = []
    if len(video_streams) != 1:
        failures.append(f"video_streams={len(video_streams)}, expected=1")
    if audio_streams:
        failures.append(f"audio_streams={len(audio_streams)}, expected=0")
    if abs(frames - expected_frames) > frame_tolerance:
        failures.append(
            f"frames={frames}, expected={expected_frames}±{frame_tolerance}"
        )
    if abs(fps - expected_fps) > fps_tolerance:
        failures.append(f"fps={fps}, expected={expected_fps}")
    metrics = {
        "path": str(path),
        "sha256": file_sha256(path),
        "frames": frames,
        "fps": fps,
        "duration": duration,
        "width": int(video.get("width", 0) or 0),
        "height": int(video.get("height", 0) or 0),
        "video_streams": len(video_streams),
        "audio_streams": len(audio_streams),
        "timing_contract_sha256": file_sha256(timing_contract_path),
        "failures": failures,
    }
    return failures, metrics


def _black_events(path: Path, duration: float = 0.05, pixel_threshold: float = 0.02) -> list[str]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found for strict black detection")
    completed = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "info",
            "-i",
            str(path),
            "-vf",
            f"blackdetect=d={duration}:pix_th={pixel_threshold}",
            "-an",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffmpeg blackdetect failed")
    return re.findall(r"black_start:[^\r\n]+", completed.stderr)


def decoded_frame_hashes(path: Path) -> list[str]:
    """Return one deterministic decoded-pixel MD5 per video frame."""

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found for decoded frame hashing")
    completed = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-an",
            "-f",
            "framemd5",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            completed.stderr.strip() or "ffmpeg decoded frame hashing failed"
        )
    hashes = []
    for line in completed.stdout.splitlines():
        if not line or line.startswith("#"):
            continue
        fields = [field.strip() for field in line.split(",")]
        if len(fields) >= 6 and re.fullmatch(r"[0-9a-fA-F]{32}", fields[-1]):
            hashes.append(fields[-1].lower())
    if not hashes:
        raise RuntimeError(f"decoded frame hashing produced no frames: {path}")
    return hashes


def decoded_frame_sequence_sha256(path: Path) -> tuple[str, int]:
    hashes = decoded_frame_hashes(path)
    return frame_slice_sha256(hashes, 0, len(hashes)), len(hashes)


def decoded_frame_sha256(path: Path, frame_number: int) -> str:
    """Hash the RGB pixels of one exact decoded output frame."""

    if frame_number < 0:
        raise ValueError("decoded frame number must be non-negative")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found for decoded frame evidence")
    completed = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-vf",
            f"select=eq(n\\,{frame_number})",
            "-frames:v",
            "1",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "-",
        ],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            detail or f"decoded frame evidence is missing for frame {frame_number}"
        )
    return hashlib.sha256(completed.stdout).hexdigest()


def full_decode_once(path: Path) -> tuple[bool, str]:
    """Decode the final video exactly once for corruption detection."""

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False, "ffmpeg not found for full decode"
    completed = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-an",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode == 0, completed.stderr.strip()


def seam_black_frames(
    path: Path,
    boundary_frames: list[int],
    *,
    total_frames: int,
    amount: float = 99.0,
    threshold: int = 16,
) -> tuple[list[int], int]:
    """Scan both sides of every seam in one FFmpeg decode pass."""

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found for seam scan")
    selected_frames = sorted(
        {
            frame
            for boundary in boundary_frames
            for frame in (boundary - 1, boundary)
            if 0 <= frame < total_frames
        }
    )
    if not selected_frames:
        raise ValueError("seam scan requires at least one in-range boundary")
    expression = "+".join(f"eq(n\\,{frame})" for frame in selected_frames)
    completed = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "info",
            "-i",
            str(path),
            "-vf",
            (
                f"select='{expression}',"
                f"blackframe=amount={amount}:threshold={threshold},showinfo"
            ),
            "-an",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffmpeg seam scan failed")
    observed = len(re.findall(r"Parsed_showinfo[^\r\n]*\bn:\s*\d+", completed.stderr))
    black_selected_indexes = [
        int(value)
        for value in re.findall(
            r"Parsed_blackframe[^\r\n]*frame:(\d+)", completed.stderr
        )
    ]
    black_source_frames = [
        selected_frames[index]
        for index in black_selected_indexes
        if 0 <= index < len(selected_frames)
    ]
    return black_source_frames, observed


def maximum_keyframe_gap_frames(path: Path, fps: float) -> int:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe not found for GOP verification")
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "packet=pts_time,flags",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffprobe packet scan failed")
    key_times: list[float] = []
    for line in completed.stdout.splitlines():
        fields = [field.strip() for field in line.split(",")]
        if len(fields) >= 2 and "K" in fields[-1]:
            try:
                key_times.append(float(fields[0]))
            except ValueError:
                continue
    if not key_times:
        raise RuntimeError("proxy contains no detectable keyframe")
    if len(key_times) == 1:
        probe = ffprobe_json(path)
        duration = float(probe.get("format", {}).get("duration", 0.0) or 0.0)
        return max(1, round(duration * fps))
    return max(round((right - left) * fps) for left, right in zip(key_times, key_times[1:]))


def frame_slice_sha256(
    hashes: list[str],
    start_frame: int,
    end_frame: int,
) -> str:
    if start_frame < 0 or end_frame <= start_frame or end_frame > len(hashes):
        raise ValueError(
            f"invalid decoded frame slice {start_frame}:{end_frame} "
            f"for {len(hashes)} frames"
        )
    payload = "\n".join(hashes[start_frame:end_frame]).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def run_check(root: Path, check: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    check_type = check.get("type")
    if check_type not in SUPPORTED_TYPES:
        return False, f"unsupported check type: {check_type}", {}

    if check_type == "authority_chain_integrity":
        from audit_authority_chain import audit_authority_bundle

        bundle_path = resolve_path(root, check.get("path", "authority_bundle.json")).resolve()
        required_descendants = {
            str(value).strip()
            for value in check.get("require_descendants", [])
            if str(value).strip()
        }
        result = audit_authority_bundle(
            root,
            bundle_path,
            require_descendants=required_descendants,
            allow_provisional=bool(check.get("allow_provisional", False)),
        )
        message = (
            "authority chain is current"
            if result["ok"]
            else "; ".join(result.get("errors", [])) or "authority chain failed"
        )
        return bool(result["ok"]), message, result

    if check_type == "glob_count":
        matches = sorted(root.glob(check["pattern"]))
        count = len(matches)
        minimum = int(check.get("min_count", 0))
        maximum = check.get("max_count")
        passed = count >= minimum and (maximum is None or count <= int(maximum))
        return passed, f"count={count}, expected {minimum}..{maximum if maximum is not None else '∞'}", {"count": count}

    path = resolve_path(root, check["path"])
    if check_type == "file_exists":
        return path.exists(), f"exists={path.exists()}", {"path": str(path)}
    if check_type == "file_nonempty":
        size = path.stat().st_size if path.is_file() else 0
        return path.is_file() and size > 0, f"size={size}", {"path": str(path), "size": size}
    if not path.exists():
        return False, f"missing path: {path}", {"path": str(path)}

    if check_type == "source_proxy_manifest_integrity":
        failures: list[str] = []
        contract_path = (
            resolve_path(root, check["contract_path"])
            if check.get("contract_path")
            else None
        )
        if contract_path is None or not contract_path.is_file():
            return False, "source proxy check requires contract_path", {}
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        policy = contract.get("render_policy", {}).get("source_proxy", {})
        if not isinstance(policy, dict) or not policy:
            failures.append("contract lacks render_policy.source_proxy")
            policy = {}
        cache_root_value = str(policy.get("cache_root", "")).strip()
        if cache_root_value and not Path(cache_root_value).expanduser().is_absolute():
            failures.append("source proxy cache_root must be absolute")
        cache_root = (
            Path(cache_root_value).expanduser().resolve()
            if cache_root_value
            else None
        )
        if cache_root is None:
            failures.append("source proxy policy lacks cache_root")
        elif policy.get("require_outside_icloud", True) and "Library/Mobile Documents" in str(
            cache_root
        ):
            failures.append("source proxy cache_root must resolve outside iCloud")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        required_profile = str(check.get("required_profile", "")).strip()
        policy_profile = str(policy.get("profile", "")).strip()
        manifest_profile = str(manifest.get("profile", "")).strip()
        if not required_profile or required_profile != policy_profile:
            failures.append("source proxy check profile is not bound to the contract")
        if manifest_profile != policy_profile:
            failures.append("source proxy manifest profile is not bound to the contract")
        contract_sha = file_sha256(contract_path)
        if manifest_hash_value(manifest, "contract_sha256", "contract.sha256") != contract_sha:
            failures.append("source proxy manifest has stale contract SHA")
        if str(manifest.get("status", "")).upper() != "PASS":
            failures.append("source proxy manifest status must be PASS")
        entries = manifest.get("sources", [])
        if not isinstance(entries, list) or not entries:
            failures.append("source proxy manifest requires nonempty sources")
            entries = []
        production_asset_classes = {
            str(value).strip()
            for value in manifest.get("production_asset_classes", [])
            if str(value).strip()
        }
        if not production_asset_classes:
            failures.append(
                "source proxy manifest requires production_asset_classes"
            )
        seen_ids: set[str] = set()
        proxy_metrics: list[dict[str, Any]] = []
        for index, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                failures.append(f"source proxy row {index} is not an object")
                continue
            source_id = str(entry.get("source_id", "")).strip()
            if not source_id or source_id in seen_ids:
                failures.append(f"source proxy row {index} has missing/duplicate source_id")
            seen_ids.add(source_id)
            source_file = resolved_existing_file(
                root, entry.get("source_path") or entry.get("source_file")
            )
            proxy_file = resolved_existing_file(
                root, entry.get("proxy_path") or entry.get("proxy_file")
            )
            raw_proxy_path = str(
                entry.get("proxy_path") or entry.get("proxy_file") or ""
            ).strip()
            if raw_proxy_path and not Path(raw_proxy_path).expanduser().is_absolute():
                failures.append(f"source {source_id}: proxy path must be absolute")
            asset_class = str(entry.get("asset_class", "")).strip()
            if not asset_class or asset_class not in production_asset_classes:
                failures.append(
                    f"source {source_id}: asset_class is absent from "
                    "production_asset_classes"
                )
            if source_file is None:
                failures.append(f"source {source_id}: source file is missing")
            if proxy_file is None:
                failures.append(f"source {source_id}: proxy file is missing")
                continue
            if cache_root is not None:
                try:
                    proxy_file.resolve().relative_to(cache_root)
                except ValueError:
                    failures.append(
                        f"source {source_id}: proxy resolves outside cache_root"
                    )
            if policy.get("require_outside_icloud", True) and (
                "Library/Mobile Documents" in str(proxy_file.resolve())
            ):
                failures.append(f"source {source_id}: proxy resolves inside iCloud")
            source_sha = file_sha256(source_file) if source_file is not None else ""
            if source_file is not None and check.get("verify_source_sha256", True):
                if str(entry.get("source_sha256", "")).lower() != source_sha:
                    failures.append(f"source {source_id}: stale source SHA")
            proxy_sha = file_sha256(proxy_file)
            if check.get("verify_proxy_sha256", True) and str(
                entry.get("proxy_sha256", "")
            ).lower() != proxy_sha:
                failures.append(f"source {source_id}: stale proxy SHA")
            try:
                probe = ffprobe_json(proxy_file)
            except RuntimeError as exc:
                failures.append(f"source {source_id}: {exc}")
                continue
            streams = probe.get("streams", [])
            videos = [item for item in streams if item.get("codec_type") == "video"]
            video = videos[0] if videos else {}
            if len(videos) != 1:
                failures.append(f"source {source_id}: video_streams={len(videos)}, expected=1")
            fps_text = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
            fps = float(Fraction(fps_text)) if fps_text != "0/0" else 0.0
            expected_values = {
                "width": int(policy.get("width", 1920)),
                "height": int(policy.get("height", 1080)),
                "codec_name": str(policy.get("codec", "h264")),
                "pix_fmt": str(policy.get("pixel_format", "yuv420p")),
                "color_space": str(policy.get("color_space", "bt709")),
                "color_primaries": str(policy.get("color_primaries", "bt709")),
                "color_transfer": str(policy.get("color_transfer", "bt709")),
            }
            for field, expected in expected_values.items():
                actual = video.get(field)
                if actual != expected:
                    failures.append(
                        f"source {source_id}: {field}={actual!r}, expected={expected!r}"
                    )
            expected_fps = float(policy.get("fps", 30))
            if abs(fps - expected_fps) > float(check.get("fps_tolerance", 0.02)):
                failures.append(
                    f"source {source_id}: fps={fps}, expected={expected_fps}"
                )
            max_gop = None
            if check.get("verify_max_gop_frames", True):
                try:
                    max_gop = maximum_keyframe_gap_frames(proxy_file, fps)
                except RuntimeError as exc:
                    failures.append(f"source {source_id}: {exc}")
                allowed_gop = int(policy.get("max_gop_frames", 30))
                if max_gop is not None and max_gop > allowed_gop:
                    failures.append(
                        f"source {source_id}: max_gop_frames={max_gop}, "
                        f"expected<={allowed_gop}"
                    )
            decode_pass = None
            if check.get("check_full_decode", True):
                decode_pass, decode_detail = full_decode_once(proxy_file)
                if not decode_pass:
                    failures.append(
                        f"source {source_id}: proxy full decode failed: {decode_detail}"
                    )
            proxy_metrics.append(
                {
                    "source_id": source_id,
                    "source_path": str(source_file) if source_file is not None else "",
                    "source_sha256": source_sha,
                    "proxy_path": str(proxy_file),
                    "proxy_sha256": proxy_sha,
                    "fps": fps,
                    "max_gop_frames": max_gop,
                    "full_decode_pass": decode_pass,
                }
            )
        metrics = {
            "profile": manifest_profile,
            "source_count": len(entries),
            "contract_sha256": contract_sha,
            "cache_root": str(cache_root) if cache_root is not None else "",
            "production_asset_classes": sorted(production_asset_classes),
            "proxy_manifest_sha256": file_sha256(path),
            "proxies": proxy_metrics,
            "workflow_ready": bool(entries) and not failures,
            "failures": failures,
        }
        return not failures, f"sources={len(entries)}, failures={failures}", metrics

    if check_type == "hyperframes_stress_test_integrity":
        required = [
            field
            for field in (
                "sample_path",
                "source_proxy_manifest_path",
                "match_sheet_path",
                "composition_path",
                "render_plan_path",
            )
            if not check.get(field)
        ]
        if required:
            return False, f"check config missing {required}", {"config_missing": required}
        failures: list[str] = []
        manifest = json.loads(path.read_text(encoding="utf-8"))
        sample_path = resolve_path(root, check["sample_path"])
        proxy_manifest_path = resolve_path(root, check["source_proxy_manifest_path"])
        match_sheet_path = resolve_path(root, check["match_sheet_path"])
        composition_path = resolve_path(root, check["composition_path"])
        render_plan_path = resolve_path(root, check["render_plan_path"])
        for label, candidate in (
            ("sample_path", sample_path),
            ("source_proxy_manifest_path", proxy_manifest_path),
            ("match_sheet_path", match_sheet_path),
            ("composition_path", composition_path),
            ("render_plan_path", render_plan_path),
        ):
            if not candidate.is_file():
                failures.append(f"{label} is missing: {candidate}")
        if failures:
            return False, f"failures={failures}", {"failures": failures}
        sample_sha = file_sha256(sample_path)
        proxy_sha = file_sha256(proxy_manifest_path)
        match_sha = file_sha256(match_sheet_path)
        composition_sha = file_sha256(composition_path)
        render_plan_sha = file_sha256(render_plan_path)
        if str(manifest.get("status", "")).upper() != "PASS":
            failures.append("stress manifest status must be PASS")
        if str(manifest.get("engine", "")).lower() != str(
            check.get("required_engine", "hyperframes")
        ).lower():
            failures.append("stress sample was not rendered by required engine")
        if manifest_hash_value(manifest, "sample_sha256", "sample.sha256") != sample_sha:
            failures.append("stress manifest has stale sample SHA")
        if manifest_hash_value(
            manifest, "source_proxy_manifest_sha256", "source_proxy_manifest.sha256"
        ) != proxy_sha:
            failures.append("stress manifest has stale source-proxy manifest SHA")
        if manifest_hash_value(manifest, "match_sheet_sha256", "match_sheet.sha256") != match_sha:
            failures.append("stress manifest has stale match-sheet SHA")
        if manifest_hash_value(
            manifest, "composition_sha256", "composition.sha256"
        ) != composition_sha:
            failures.append("stress manifest has stale HyperFrames composition SHA")
        if manifest_hash_value(
            manifest, "render_plan_sha256", "render_plan.sha256"
        ) != render_plan_sha:
            failures.append("stress manifest has stale HyperFrames render-plan SHA")
        probe = ffprobe_json(sample_path, count_frames=True)
        streams = probe.get("streams", [])
        video = next((item for item in streams if item.get("codec_type") == "video"), {})
        duration = float(probe.get("format", {}).get("duration", 0.0) or 0.0)
        fps_text = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
        fps = float(Fraction(fps_text)) if fps_text != "0/0" else 0.0
        frames = int(video.get("nb_read_frames") or video.get("nb_frames") or round(duration * fps))
        minimum = float(check.get("minimum_duration_seconds", 30))
        maximum = float(check.get("maximum_duration_seconds", 60))
        if duration < minimum or duration > maximum:
            failures.append(f"stress duration={duration}, expected {minimum}..{maximum}")
        if any(item.get("codec_type") == "audio" for item in streams):
            failures.append("stress sample must be video-only")
        proxy_manifest = json.loads(proxy_manifest_path.read_text(encoding="utf-8"))
        expected_asset_classes = {
            str(value).strip()
            for value in proxy_manifest.get("production_asset_classes", [])
            if str(value).strip()
        }
        coverage = manifest.get("coverage", {})
        declared_risk_classes = {
            str(value).strip()
            for value in coverage.get("risk_classes", [])
            if str(value).strip()
        }
        declared_asset_classes = {
            str(value).strip()
            for value in coverage.get("asset_classes", [])
            if str(value).strip()
        }
        required_risk_classes = {
            str(value).strip()
            for value in check.get("required_risk_classes", [])
            if str(value).strip()
        }
        card_asset_classes = {"card", "overlay", "still"}
        if {value.casefold() for value in expected_asset_classes} & card_asset_classes:
            required_risk_classes.add("card")

        _, match_rows = read_tsv(match_sheet_path)
        unit_ranges: dict[str, tuple[float, float]] = {}
        for row in match_rows:
            unit_id = row.get("visual_unit_id", "").strip()
            cue_range = caption_range(row)
            if not unit_id or cue_range is None:
                continue
            if unit_id not in unit_ranges:
                unit_ranges[unit_id] = cue_range
            else:
                unit_ranges[unit_id] = (
                    min(unit_ranges[unit_id][0], cue_range[0]),
                    max(unit_ranges[unit_id][1], cue_range[1]),
                )
        if not unit_ranges:
            failures.append(
                "stress match sheet has no semantic visual-unit ranges"
            )
        shortest_duration = min(
            (end - start for start, end in unit_ranges.values()),
            default=0.0,
        )

        sample_assets = manifest.get("sample_assets", [])
        if not isinstance(sample_assets, list) or not sample_assets:
            failures.append("stress manifest must list concrete sample_assets")
            sample_assets = []
        asset_ids: set[str] = set()
        derived_asset_classes: set[str] = set()
        derived_risk_classes: set[str] = set()
        asset_boundaries: set[int] = set()
        frame_evidence_checks = 0
        frame_evidence_metrics: list[dict[str, Any]] = []
        for asset_index, asset in enumerate(sample_assets, start=1):
            if not isinstance(asset, dict):
                failures.append(f"stress sample asset {asset_index} is not an object")
                continue
            asset_id = str(asset.get("asset_id", "")).strip()
            if not asset_id or asset_id in asset_ids:
                failures.append(
                    f"stress sample asset {asset_index} has missing/duplicate asset_id"
                )
            asset_ids.add(asset_id)
            asset_class = str(asset.get("asset_class", "")).strip()
            if not asset_class:
                failures.append(f"stress sample asset {asset_id!r} lacks asset_class")
            else:
                derived_asset_classes.add(asset_class)
            try:
                output_start = int(asset["output_start_frame"])
                output_end = int(asset["output_end_frame"])
                if output_start < 0 or output_end <= output_start or output_end > frames:
                    raise ValueError
            except (KeyError, TypeError, ValueError):
                failures.append(
                    f"stress sample asset {asset_id!r} has invalid output frame range"
                )
                continue
            if output_start > 0:
                asset_boundaries.add(output_start)
            if output_end < frames:
                asset_boundaries.add(output_end)
            raw_risks = asset.get("risk_classes", [])
            if isinstance(raw_risks, str):
                raw_risks = split_identity_values(raw_risks)
            risks = {
                str(value).strip()
                for value in raw_risks
                if str(value).strip()
            } if isinstance(raw_risks, list) else set()
            derived_risk_classes.update(risks)
            unit_id = str(asset.get("visual_unit_id", "")).strip()
            if "shortest_unit" in risks:
                unit_range = unit_ranges.get(unit_id)
                if unit_range is None or abs(
                    (unit_range[1] - unit_range[0]) - shortest_duration
                ) > 0.002:
                    failures.append(
                        f"stress sample asset {asset_id!r} is not a shortest visual unit"
                    )
            if "hard_cut" in risks and (
                output_start <= 0
                or str(asset.get("transition_in", "")).strip().casefold()
                not in {"hard_cut", "cut"}
            ):
                failures.append(
                    f"stress sample asset {asset_id!r} lacks a concrete hard-cut boundary"
                )
            if "card" in risks and asset_class.casefold() not in card_asset_classes:
                failures.append(
                    f"stress sample asset {asset_id!r} marks card on class={asset_class!r}"
                )

            evidence = asset.get("frame_evidence", {})
            if not isinstance(evidence, dict):
                evidence = {}
            expected_samples = {
                "head": output_start,
                "tail": output_end - 1,
            }
            if "media_element_activation" in risks:
                try:
                    activation_frame = int(asset["activation_frame"])
                    if not output_start <= activation_frame < output_end:
                        raise ValueError
                except (KeyError, TypeError, ValueError):
                    failures.append(
                        f"stress sample asset {asset_id!r} has invalid activation_frame"
                    )
                    activation_frame = output_start
                expected_samples["activation"] = activation_frame
            for sample_name, expected_frame in expected_samples.items():
                record = evidence.get(sample_name)
                if not isinstance(record, dict):
                    failures.append(
                        f"stress sample asset {asset_id!r} lacks {sample_name} frame evidence"
                    )
                    continue
                evidence_path = resolved_existing_file(
                    root, record.get("path") or record.get("evidence_path")
                )
                if evidence_path is None:
                    failures.append(
                        f"stress sample asset {asset_id!r} {sample_name} evidence is missing"
                    )
                elif str(record.get("sha256", "")).strip().lower() != file_sha256(
                    evidence_path
                ):
                    failures.append(
                        f"stress sample asset {asset_id!r} {sample_name} evidence SHA mismatch"
                    )
                try:
                    declared_frame = int(record["output_frame"])
                    if declared_frame != expected_frame:
                        raise ValueError
                except (KeyError, TypeError, ValueError):
                    failures.append(
                        f"stress sample asset {asset_id!r} {sample_name} output_frame mismatch"
                    )
                    continue
                try:
                    actual_frame_sha = decoded_frame_sha256(
                        sample_path, declared_frame
                    )
                except (RuntimeError, ValueError) as exc:
                    failures.append(
                        f"stress sample asset {asset_id!r} {sample_name}: {exc}"
                    )
                    continue
                if str(record.get("decoded_frame_sha256", "")).strip().lower() != (
                    actual_frame_sha
                ):
                    failures.append(
                        f"stress sample asset {asset_id!r} {sample_name} decoded-frame SHA mismatch"
                    )
                frame_evidence_metrics.append(
                    {
                        "asset_id": asset_id,
                        "sample": sample_name,
                        "output_frame": declared_frame,
                        "evidence_path": str(evidence_path)
                        if evidence_path is not None
                        else "",
                        "evidence_sha256": file_sha256(evidence_path)
                        if evidence_path is not None
                        else "",
                        "decoded_frame_sha256": actual_frame_sha,
                    }
                )
                frame_evidence_checks += 1

        if declared_asset_classes != derived_asset_classes:
            failures.append(
                "stress declared asset coverage is not derived from sample_assets: "
                f"declared={sorted(declared_asset_classes)}, "
                f"derived={sorted(derived_asset_classes)}"
            )
        if declared_risk_classes != derived_risk_classes:
            failures.append(
                "stress declared risk coverage is not derived from sample_assets: "
                f"declared={sorted(declared_risk_classes)}, "
                f"derived={sorted(derived_risk_classes)}"
            )
        missing_risk_classes = required_risk_classes - derived_risk_classes
        if missing_risk_classes:
            failures.append(
                f"stress coverage missing concrete risk classes={sorted(missing_risk_classes)}"
            )
        if check.get("require_all_declared_asset_classes", False) and (
            derived_asset_classes != expected_asset_classes
        ):
            failures.append(
                "stress asset-class coverage differs from proxy manifest: "
                f"missing={sorted(expected_asset_classes - derived_asset_classes)}, "
                f"extra={sorted(derived_asset_classes - expected_asset_classes)}"
            )
        decode_pass = None
        if check.get("check_full_decode", True):
            decode_pass, decode_detail = full_decode_once(sample_path)
            if not decode_pass:
                failures.append(f"stress full decode failed: {decode_detail}")
        black_events: list[str] = []
        if check.get("check_black_frames", True):
            try:
                black_events = _black_events(
                    sample_path,
                    duration=float(check.get("black_duration", 0.03)),
                    pixel_threshold=float(check.get("black_pixel_threshold", 0.02)),
                )
            except RuntimeError as exc:
                failures.append(str(exc))
            if black_events:
                failures.append(f"stress black frame events={black_events[:20]}")
        seam_black: list[int] = []
        seam_observed = 0
        raw_seam_frames = manifest.get("seam_frames", [])
        try:
            boundaries = [int(value) for value in raw_seam_frames]
        except (TypeError, ValueError):
            boundaries = []
            failures.append("stress seam_frames must be a list of integers")
        if len(boundaries) != len(set(boundaries)):
            failures.append("stress seam_frames contain duplicates")
        if any(value <= 0 or value >= frames for value in boundaries):
            failures.append("stress seam_frames contain out-of-range boundaries")
        if sample_assets and not boundaries:
            failures.append("stress seam_frames must be non-empty")
        missing_asset_boundaries = asset_boundaries - set(boundaries)
        if missing_asset_boundaries:
            failures.append(
                "stress seam_frames omit sample-asset boundaries="
                f"{sorted(missing_asset_boundaries)}"
            )
        if check.get("check_transition_seams", True):
            try:
                seam_black, seam_observed = seam_black_frames(
                    sample_path,
                    boundaries,
                    total_frames=frames,
                    amount=float(check.get("seam_black_amount", 99)),
                    threshold=int(check.get("seam_black_threshold", 16)),
                )
            except (RuntimeError, ValueError) as exc:
                failures.append(str(exc))
            if seam_black:
                failures.append(f"stress black seam frames={seam_black[:20]}")
        metrics = {
            "sample_sha256": sample_sha,
            "duration": duration,
            "frames": frames,
            "fps": fps,
            "full_decode_pass": decode_pass,
            "black_events": black_events,
            "seam_black_frames": seam_black,
            "seam_frames_observed": seam_observed,
            "covered_risk_classes": sorted(derived_risk_classes),
            "covered_asset_classes": sorted(derived_asset_classes),
            "sample_asset_count": len(sample_assets),
            "frame_evidence_checks": frame_evidence_checks,
            "frame_evidence": frame_evidence_metrics,
            "composition_sha256": composition_sha,
            "render_plan_sha256": render_plan_sha,
            "workflow_ready": not failures,
            "failures": failures,
        }
        return not failures, f"duration={duration}, failures={failures}", metrics

    if check_type == "aesthetic_proxy_approval_integrity":
        required = [
            field
            for field in (
                "proxy_path",
                "stress_manifest_path",
                "match_sheet_path",
                "composition_path",
                "render_plan_path",
            )
            if not check.get(field)
        ]
        if required:
            return False, f"check config missing {required}", {"config_missing": required}
        failures: list[str] = []
        approval = json.loads(path.read_text(encoding="utf-8"))
        proxy_path = resolve_path(root, check["proxy_path"])
        stress_path = resolve_path(root, check["stress_manifest_path"])
        match_path = resolve_path(root, check["match_sheet_path"])
        composition_path = resolve_path(root, check["composition_path"])
        render_plan_path = resolve_path(root, check["render_plan_path"])
        for label, candidate in (
            ("proxy_path", proxy_path),
            ("stress_manifest_path", stress_path),
            ("match_sheet_path", match_path),
            ("composition_path", composition_path),
            ("render_plan_path", render_plan_path),
        ):
            if not candidate.is_file():
                failures.append(f"{label} is missing: {candidate}")
        if failures:
            return False, f"failures={failures}", {"failures": failures}
        proxy_sha = file_sha256(proxy_path)
        stress_sha = file_sha256(stress_path)
        match_sha = file_sha256(match_path)
        composition_sha = file_sha256(composition_path)
        render_plan_sha = file_sha256(render_plan_path)
        stress_manifest = json.loads(stress_path.read_text(encoding="utf-8"))
        if str(approval.get("status", "")).upper() != "PASS":
            failures.append("aesthetic proxy approval status must be PASS")
        if str(approval.get("engine", "")).lower() != str(
            check.get("required_engine", "hyperframes")
        ).lower():
            failures.append("aesthetic proxy was not rendered by required engine")
        if manifest_hash_value(approval, "proxy_sha256", "proxy.sha256") != proxy_sha:
            failures.append("aesthetic approval has stale proxy SHA")
        if manifest_hash_value(
            approval, "stress_manifest_sha256", "stress_manifest.sha256"
        ) != stress_sha:
            failures.append("aesthetic approval has stale stress-manifest SHA")
        if manifest_hash_value(approval, "match_sheet_sha256", "match_sheet.sha256") != match_sha:
            failures.append("aesthetic approval has stale match-sheet SHA")
        for label, actual_hash, approval_fields, stress_fields in (
            (
                "composition",
                composition_sha,
                ("composition_sha256", "composition.sha256"),
                ("composition_sha256", "composition.sha256"),
            ),
            (
                "render plan",
                render_plan_sha,
                ("render_plan_sha256", "render_plan.sha256"),
                ("render_plan_sha256", "render_plan.sha256"),
            ),
        ):
            if manifest_hash_value(approval, *approval_fields) != actual_hash:
                failures.append(f"aesthetic approval has stale HyperFrames {label} SHA")
            if manifest_hash_value(stress_manifest, *stress_fields) != actual_hash:
                failures.append(
                    f"aesthetic approval points to a stress test with stale {label} SHA"
                )
        probe = ffprobe_json(proxy_path)
        streams = probe.get("streams", [])
        videos = [item for item in streams if item.get("codec_type") == "video"]
        video = videos[0] if videos else {}
        width = int(video.get("width", 0) or 0)
        height = int(video.get("height", 0) or 0)
        if width != int(check.get("expected_width", 1280)):
            failures.append(f"aesthetic proxy width={width}")
        if height != int(check.get("expected_height", 720)):
            failures.append(f"aesthetic proxy height={height}")
        if len(videos) != 1 or any(item.get("codec_type") == "audio" for item in streams):
            failures.append("aesthetic proxy must contain one video stream and no audio")
        review = approval.get("review", {})
        for config_field, section_name in (
            ("require_opening_review", "opening"),
            ("require_middle_review", "middle"),
            ("require_ending_review", "ending"),
        ):
            section = review.get(section_name, {}) if isinstance(review, dict) else {}
            if check.get(config_field, False) and str(section.get("status", "")).upper() != "PASS":
                failures.append(f"aesthetic approval lacks PASS {section_name} review")
        decisions = approval.get("decisions", {})
        required_decisions = check.get("required_decisions", [])
        if not isinstance(required_decisions, list):
            failures.append("aesthetic required_decisions must be a list")
            required_decisions = []
        for decision in required_decisions:
            if not str(
                decisions.get(str(decision), "")
                if isinstance(decisions, dict)
                else ""
            ).strip():
                failures.append(
                    f"aesthetic approval lacks {decision} decision"
                )
        metrics = {
            "proxy_sha256": proxy_sha,
            "stress_manifest_sha256": stress_sha,
            "match_sheet_sha256": match_sha,
            "composition_sha256": composition_sha,
            "render_plan_sha256": render_plan_sha,
            "width": width,
            "height": height,
            "workflow_ready": not failures,
            "failures": failures,
        }
        return not failures, f"proxy={width}x{height}, failures={failures}", metrics

    if check_type == "visual_index_integrity":
        failures: list[str] = []
        required_config = [
            field
            for field in ("ocr_index_path", "source_manifest_path")
            if field not in check
        ]
        if required_config:
            return False, f"check config missing {required_config}", {
                "config_missing": required_config
            }
        ocr_path = resolve_path(root, check["ocr_index_path"])
        source_manifest_path = resolve_path(root, check["source_manifest_path"])
        for label, candidate in (
            ("ocr_index_path", ocr_path),
            ("source_manifest_path", source_manifest_path),
        ):
            if not candidate.is_file():
                failures.append(f"{label} is missing: {candidate}")
        if failures:
            return False, f"failures={failures}", {"failures": failures}

        shot_fields, shot_rows = read_tsv(path)
        ocr_fields, ocr_rows = read_tsv(ocr_path)
        required_shot_fields = {"source_id", "source_file", "frame_path"}
        required_ocr_fields = {"source_id", "source_file", "evidence_frame"}
        missing_shot = sorted(required_shot_fields - set(shot_fields))
        missing_ocr = sorted(required_ocr_fields - set(ocr_fields))
        if missing_shot:
            failures.append(f"shot index missing columns={missing_shot}")
        if missing_ocr:
            failures.append(f"OCR index missing columns={missing_ocr}")
        if len(shot_rows) < int(check.get("min_shot_rows", 1)):
            failures.append(
                f"shot_rows={len(shot_rows)}, expected>={int(check.get('min_shot_rows', 1))}"
            )
        if len(ocr_rows) < int(check.get("min_ocr_rows", 1)):
            failures.append(
                f"ocr_rows={len(ocr_rows)}, expected>={int(check.get('min_ocr_rows', 1))}"
            )

        source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
        source_entries: list[dict[str, Any]] = []
        if isinstance(source_manifest, dict):
            for field in ("sources", "primary_sources", "auxiliary_assets"):
                values = source_manifest.get(field, [])
                if isinstance(values, list):
                    source_entries.extend(
                        item for item in values if isinstance(item, dict)
                    )
        elif isinstance(source_manifest, list):
            source_entries = [
                item for item in source_manifest if isinstance(item, dict)
            ]
        source_by_id: dict[str, dict[str, Any]] = {}
        source_paths_by_id: dict[str, Path] = {}
        for entry in source_entries:
            identity = str(
                entry.get("source_id") or entry.get("asset_id") or ""
            ).strip()
            if not identity:
                failures.append("source manifest entry missing source_id/asset_id")
                continue
            if identity in source_by_id:
                failures.append(f"duplicate source identity={identity}")
                continue
            source_by_id[identity] = entry
            source_file = resolved_existing_file(
                root, entry.get("real_path") or entry.get("path")
            )
            if source_file is None:
                failures.append(f"source {identity}: file is missing")
                continue
            source_paths_by_id[identity] = source_file.resolve()
            probe = entry.get("probe")
            if isinstance(probe, dict):
                if probe.get("ok") is not True:
                    failures.append(f"source {identity}: probe.ok is not true")
                try:
                    if float(probe.get("duration_s", 0)) <= 0:
                        failures.append(f"source {identity}: probe duration is not positive")
                except (TypeError, ValueError):
                    failures.append(f"source {identity}: probe duration is invalid")
            if check.get("verify_source_sha256", False):
                expected_sha = str(entry.get("sha256", "")).lower()
                if not expected_sha or file_sha256(source_file) != expected_sha:
                    failures.append(f"source {identity}: SHA-256 mismatch")
        if not source_by_id:
            failures.append("source manifest contains no usable identities")

        proxy_manifest_sha = ""
        if check.get("proxy_manifest_path"):
            proxy_manifest_path = resolve_path(root, check["proxy_manifest_path"])
            if not proxy_manifest_path.is_file():
                failures.append(
                    f"proxy_manifest_path is missing: {proxy_manifest_path}"
                )
            else:
                proxy_manifest_sha = file_sha256(proxy_manifest_path)
                proxy_manifest = json.loads(
                    proxy_manifest_path.read_text(encoding="utf-8")
                )
                if manifest_hash_value(
                    source_manifest,
                    "source_proxy_manifest_sha256",
                    "proxy_manifest_sha256",
                ) != proxy_manifest_sha:
                    failures.append(
                        "source identity manifest has stale source-proxy manifest SHA"
                    )
                for proxy_entry in proxy_manifest.get("sources", []):
                    if not isinstance(proxy_entry, dict):
                        continue
                    proxy_source_id = str(
                        proxy_entry.get("source_id", "")
                    ).strip()
                    proxy_file = resolved_existing_file(
                        root,
                        proxy_entry.get("proxy_path")
                        or proxy_entry.get("proxy_file"),
                    )
                    if proxy_source_id not in source_paths_by_id:
                        failures.append(
                            f"indexed source manifest omits proxy source={proxy_source_id!r}"
                        )
                    elif (
                        proxy_file is None
                        or source_paths_by_id[proxy_source_id] != proxy_file.resolve()
                    ):
                        failures.append(
                            f"indexed source {proxy_source_id!r} is not bound to its proxy"
                        )

        require_frame_files = bool(check.get("require_frame_files", True))
        missing_frame_files: list[str] = []
        unknown_source_rows: list[str] = []
        mismatched_source_files: list[str] = []
        duplicate_shot_ids: list[str] = []
        seen_shot_ids: set[str] = set()
        for row_number, row in enumerate(shot_rows, start=2):
            identity = row.get("source_id", "").strip()
            if identity not in source_by_id:
                unknown_source_rows.append(f"shot:{row_number}:{identity}")
            else:
                indexed_source = resolved_existing_file(
                    root, row.get("source_file", "")
                )
                if (
                    indexed_source is None
                    or indexed_source.resolve() != source_paths_by_id.get(identity)
                ):
                    mismatched_source_files.append(
                        f"shot:{row_number}:{identity}"
                    )
            shot_id = row.get("shot_id", "").strip()
            if shot_id:
                if shot_id in seen_shot_ids:
                    duplicate_shot_ids.append(shot_id)
                seen_shot_ids.add(shot_id)
            if require_frame_files and resolved_existing_file(
                root, row.get("frame_path", "")
            ) is None:
                missing_frame_files.append(f"shot:{row_number}")
        for row_number, row in enumerate(ocr_rows, start=2):
            identity = row.get("source_id", "").strip()
            if identity not in source_by_id:
                unknown_source_rows.append(f"ocr:{row_number}:{identity}")
            else:
                indexed_source = resolved_existing_file(
                    root, row.get("source_file", "")
                )
                if (
                    indexed_source is None
                    or indexed_source.resolve() != source_paths_by_id.get(identity)
                ):
                    mismatched_source_files.append(
                        f"ocr:{row_number}:{identity}"
                    )
            if require_frame_files and resolved_existing_file(
                root, row.get("evidence_frame", "")
            ) is None:
                missing_frame_files.append(f"ocr:{row_number}")
        if unknown_source_rows:
            failures.append(
                f"rows reference unknown sources={unknown_source_rows[:20]}"
            )
        if mismatched_source_files:
            failures.append(
                "indexed source_file does not match source manifest="
                f"{mismatched_source_files[:20]}"
            )
        if duplicate_shot_ids:
            failures.append(f"duplicate shot IDs={duplicate_shot_ids[:20]}")
        if missing_frame_files:
            failures.append(
                f"missing indexed evidence frames={missing_frame_files[:20]}"
            )

        contact_paths: list[Path] = []
        if check.get("contact_sheet_manifest_path"):
            contact_manifest_path = resolve_path(
                root, check["contact_sheet_manifest_path"]
            )
            if not contact_manifest_path.is_file():
                failures.append(
                    f"contact_sheet_manifest_path is missing: {contact_manifest_path}"
                )
            else:
                contact_manifest = json.loads(
                    contact_manifest_path.read_text(encoding="utf-8")
                )
                raw_contacts = (
                    contact_manifest.get("contact_sheets", [])
                    if isinstance(contact_manifest, dict)
                    else []
                )
                for item in raw_contacts:
                    raw_path = item.get("path") if isinstance(item, dict) else item
                    contact = resolved_existing_file(root, raw_path)
                    if contact is None:
                        failures.append(f"missing contact sheet={raw_path}")
                    else:
                        contact_paths.append(contact)
                if not contact_paths:
                    failures.append("contact sheet manifest contains no files")

        shot_sha = file_sha256(path)
        ocr_sha = file_sha256(ocr_path)
        source_manifest_sha = file_sha256(source_manifest_path)
        for label, actual, expected in (
            (
                "shot_index_sha256",
                shot_sha,
                str(check.get("expected_shot_index_sha256", "")).lower(),
            ),
            (
                "ocr_index_sha256",
                ocr_sha,
                str(check.get("expected_ocr_index_sha256", "")).lower(),
            ),
            (
                "source_manifest_sha256",
                source_manifest_sha,
                str(check.get("expected_source_manifest_sha256", "")).lower(),
            ),
        ):
            if expected and actual != expected:
                failures.append(f"{label} mismatch")
        metrics = {
            "shot_rows": len(shot_rows),
            "ocr_rows": len(ocr_rows),
            "source_count": len(source_by_id),
            "contact_sheet_count": len(contact_paths),
            "shot_index_sha256": shot_sha,
            "ocr_index_sha256": ocr_sha,
            "source_manifest_sha256": source_manifest_sha,
            "source_proxy_manifest_sha256": proxy_manifest_sha,
            "failures": failures,
        }
        return (
            not failures,
            (
                f"shots={len(shot_rows)}, ocr={len(ocr_rows)}, "
                f"sources={len(source_by_id)}, failures={failures}"
            ),
            metrics,
        )

    if check_type == "visual_match_plan_integrity":
        if "canonical_srt_path" not in check:
            return False, "check config missing ['canonical_srt_path']", {
                "config_missing": ["canonical_srt_path"]
            }
        canonical_srt_path = resolve_path(root, check["canonical_srt_path"])
        if not canonical_srt_path.is_file():
            return False, f"missing canonical SRT: {canonical_srt_path}", {}
        failures, metrics, rows = _match_plan_failures(
            root,
            path,
            canonical_srt_path,
            min_candidates=int(check.get("min_candidates", 3)),
            max_reuse=(
                int(check["max_reuse"])
                if check.get("max_reuse") is not None
                else None
            ),
            timing_tolerance_ms=float(check.get("timing_tolerance_ms", 2)),
            require_candidate_evidence=bool(
                check.get("require_candidate_evidence", False)
            ),
            required_qa_status=(
                str(check["required_qa_status"])
                if check.get("required_qa_status")
                else None
            ),
            require_candidate_ids=bool(
                check.get("require_candidate_ids", False)
            ),
            require_semantic_visual_units=bool(
                check.get("require_semantic_visual_units", False)
            ),
            min_semantic_unit_duration_seconds=float(
                check.get("min_semantic_unit_duration_seconds", 4)
            ),
            max_semantic_unit_duration_seconds=float(
                check.get("max_semantic_unit_duration_seconds", 8)
            ),
        )
        semantic_pool_mode = (
            check.get("candidate_pool_granularity")
            == SEMANTIC_VISUAL_UNIT_GRANULARITY
        )
        if semantic_pool_mode:
            candidate_pool_path = (
                resolve_path(root, check["candidate_pool_path"])
                if check.get("candidate_pool_path")
                else None
            )
            manifest_path = (
                resolve_path(root, check["manifest_path"])
                if check.get("manifest_path")
                else None
            )
            pool_metrics: dict[str, Any] = {}
            pool_rows: list[dict[str, Any]] = []
            candidate_pool_sha = ""
            if candidate_pool_path is None or not candidate_pool_path.is_file():
                failures.append("semantic match plan requires candidate_pool_path")
            else:
                candidate_pool_sha = file_sha256(candidate_pool_path)
                try:
                    pool_rows = read_jsonl(candidate_pool_path)
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    failures.append(f"candidate pool is invalid: {exc}")
                pool_failures, pool_metrics = semantic_candidate_pool_failures(
                    root,
                    rows,
                    pool_rows,
                    normal_min_candidates=int(check.get("min_pool_candidates", 8)),
                    normal_max_candidates=int(
                        check.get("normal_pool_max_candidates", 12)
                    ),
                    risk_max_candidates=int(check.get("risk_pool_max_candidates", 32)),
                    require_evidence=bool(
                        check.get("require_candidate_pool_evidence", False)
                    ),
                )
                failures.extend(pool_failures)
                if check.get("require_source_manifest_binding", False):
                    source_manifest_path = (
                        resolve_path(root, check["source_manifest_path"])
                        if check.get("source_manifest_path")
                        else None
                    )
                    if source_manifest_path is None or not source_manifest_path.is_file():
                        failures.append(
                            "semantic candidate pool requires source_manifest_path"
                        )
                    else:
                        source_failures, source_metrics = (
                            candidate_source_manifest_failures(
                                root, pool_rows, source_manifest_path
                            )
                        )
                        failures.extend(source_failures)
                        pool_metrics["source_binding"] = source_metrics
            if manifest_path is None or not manifest_path.is_file():
                failures.append("semantic match plan requires manifest_path")
            else:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if str(manifest.get("status", "")).upper() != "PASS":
                    failures.append("match plan manifest status must be PASS")
                if manifest_hash_value(
                    manifest, "match_sheet_sha256", "match_sheet.sha256"
                ) != metrics["match_sheet_sha256"]:
                    failures.append("match plan manifest has stale match_sheet_sha256")
                if manifest_hash_value(
                    manifest, "canonical_srt_sha256", "canonical_srt.sha256"
                ) != metrics["canonical_srt_sha256"]:
                    failures.append("match plan manifest has stale canonical_srt_sha256")
                if manifest_hash_value(
                    manifest, "candidate_pool_sha256", "candidate_pool.sha256"
                ) != candidate_pool_sha:
                    failures.append("match plan manifest has stale candidate_pool_sha256")
                if int(manifest.get("row_count", -1)) != len(rows):
                    failures.append("match plan manifest row_count mismatch")
                if int(manifest.get("visual_unit_count", -1)) != int(
                    metrics.get("semantic_visual_units", -2)
                ):
                    failures.append("match plan manifest visual_unit_count mismatch")
                if check.get("require_index_binding", False):
                    for field, manifest_fields in (
                        ("shot_index_path", ("shot_index_sha256", "shot_index.sha256")),
                        ("ocr_index_path", ("ocr_index_sha256", "shot_ocr_index_sha256")),
                        (
                            "source_manifest_path",
                            ("source_manifest_sha256", "source_identity_manifest_sha256"),
                        ),
                    ):
                        bound_path = (
                            resolve_path(root, check[field])
                            if check.get(field)
                            else None
                        )
                        if bound_path is None or not bound_path.is_file():
                            failures.append(
                                f"match plan index binding is missing {field}"
                            )
                        elif manifest_hash_value(
                            manifest, *manifest_fields
                        ) != file_sha256(bound_path):
                            failures.append(
                                f"match plan manifest has stale {field} SHA"
                            )
                metrics["manifest_sha256"] = file_sha256(manifest_path)
            metrics["failures"] = failures
            metrics["candidate_pool_sha256"] = candidate_pool_sha
            metrics["candidate_pool"] = pool_metrics
            return (
                not failures,
                f"rows={len(rows)}, units={metrics.get('semantic_visual_units', 0)}, failures={failures}",
                metrics,
            )
        candidate_pool_path = (
            resolve_path(root, check["candidate_pool_path"])
            if check.get("candidate_pool_path")
            else None
        )
        candidate_pool_sha = ""
        pool_metrics: dict[str, Any] = {}
        if candidate_pool_path is not None:
            if not candidate_pool_path.is_file():
                failures.append(f"missing candidate pool={candidate_pool_path}")
            else:
                candidate_pool_sha = file_sha256(candidate_pool_path)
                try:
                    pool_rows = read_jsonl(candidate_pool_path)
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    failures.append(f"candidate pool is invalid: {exc}")
                    pool_rows = []
                pool_by_id: dict[int, dict[str, Any]] = {}
                duplicate_pool_ids: list[int] = []
                missing_candidate_evidence: list[str] = []
                invalid_candidates: list[str] = []
                min_pool_candidates = int(check.get("min_pool_candidates", 3))
                preferred_pool_candidates = int(
                    check.get("preferred_pool_candidates", min_pool_candidates)
                )
                require_shortfall_evidence = bool(
                    check.get("require_candidate_shortfall_evidence", False)
                )
                normal_pool_max_candidates = (
                    int(check["normal_pool_max_candidates"])
                    if check.get("normal_pool_max_candidates") is not None
                    else None
                )
                risk_pool_max_candidates = (
                    int(check["risk_pool_max_candidates"])
                    if check.get("risk_pool_max_candidates") is not None
                    else None
                )
                shortfall_ids: list[int] = []
                require_pool_evidence = bool(
                    check.get("require_candidate_pool_evidence", False)
                )
                source_paths_by_id: dict[str, Path] = {}
                if check.get("require_source_manifest_binding", False):
                    source_manifest_path = (
                        resolve_path(root, check["source_manifest_path"])
                        if check.get("source_manifest_path")
                        else None
                    )
                    if (
                        source_manifest_path is None
                        or not source_manifest_path.is_file()
                    ):
                        failures.append(
                            "candidate pool source binding requires "
                            "source_manifest_path"
                        )
                    else:
                        source_manifest = json.loads(
                            source_manifest_path.read_text(encoding="utf-8")
                        )
                        source_entries: list[dict[str, Any]] = []
                        if isinstance(source_manifest, dict):
                            for source_field in (
                                "sources",
                                "primary_sources",
                                "auxiliary_assets",
                            ):
                                values = source_manifest.get(
                                    source_field, []
                                )
                                if isinstance(values, list):
                                    source_entries.extend(
                                        item
                                        for item in values
                                        if isinstance(item, dict)
                                    )
                        elif isinstance(source_manifest, list):
                            source_entries = [
                                item
                                for item in source_manifest
                                if isinstance(item, dict)
                            ]
                        for source_entry in source_entries:
                            source_identity = str(
                                source_entry.get("source_id")
                                or source_entry.get("asset_id")
                                or ""
                            ).strip()
                            source_file = resolved_existing_file(
                                root,
                                source_entry.get("real_path")
                                or source_entry.get("path")
                                or source_entry.get("local_path"),
                            )
                            if (
                                source_identity
                                and source_file is not None
                            ):
                                source_paths_by_id[source_identity] = (
                                    source_file.resolve()
                                )
                        if not source_paths_by_id:
                            failures.append(
                                "bound source manifest has no usable sources"
                            )
                for index, entry in enumerate(pool_rows, start=1):
                    try:
                        identity = int(
                            entry.get("cue_id") or entry.get("line_id")
                        )
                    except (TypeError, ValueError):
                        failures.append(f"candidate pool row {index}: invalid cue ID")
                        continue
                    if identity in pool_by_id:
                        duplicate_pool_ids.append(identity)
                    pool_by_id[identity] = entry
                    candidates = entry.get("candidates", [])
                    if not isinstance(candidates, list) or len(candidates) < min_pool_candidates:
                        failures.append(
                            f"cue {identity}: candidate pool has "
                            f"{len(candidates) if isinstance(candidates, list) else 0}, "
                            f"expected>={min_pool_candidates}"
                        )
                        continue
                    if len(candidates) < preferred_pool_candidates:
                        shortfall_ids.append(identity)
                        if require_shortfall_evidence:
                            if not str(
                                entry.get("candidate_shortfall_reason") or ""
                            ).strip():
                                failures.append(
                                    f"cue {identity}: candidate pool below preferred "
                                    "size without candidate_shortfall_reason"
                                )
                            expansion_attempts = entry.get(
                                "candidate_expansion_attempts"
                            )
                            if not isinstance(expansion_attempts, list) or not (
                                expansion_attempts
                            ):
                                failures.append(
                                    f"cue {identity}: candidate pool below preferred "
                                    "size without candidate_expansion_attempts"
                                )
                    risk_values = entry.get("risk_flags") or entry.get("risk_reasons") or []
                    is_risk = bool(risk_values) or str(
                        entry.get("risk_tier", "")
                    ).strip().lower() in {
                        "risk",
                        "high",
                        "medium",
                        "风险",
                        "高",
                        "中",
                    }
                    maximum = (
                        risk_pool_max_candidates
                        if is_risk
                        else normal_pool_max_candidates
                    )
                    if maximum is not None and len(candidates) > maximum:
                        failures.append(
                            f"cue {identity}: {'risk' if is_risk else 'normal'} "
                            f"candidate pool has {len(candidates)}, expected<={maximum}"
                        )
                    candidate_ids: set[str] = set()
                    candidates_by_id: dict[str, dict[str, Any]] = {}
                    for candidate_index, candidate in enumerate(candidates, start=1):
                        if not isinstance(candidate, dict):
                            invalid_candidates.append(
                                f"{identity}:{candidate_index}:not_object"
                            )
                            continue
                        candidate_id_value = str(
                            candidate.get("candidate_id") or ""
                        ).strip()
                        if not candidate_id_value or candidate_id_value in candidate_ids:
                            invalid_candidates.append(
                                f"{identity}:{candidate_index}:candidate_id"
                            )
                        candidate_ids.add(candidate_id_value)
                        if candidate_id_value:
                            candidates_by_id[candidate_id_value] = candidate
                        source_file = resolved_existing_file(
                            root, candidate.get("source_file", "")
                        )
                        if source_file is None:
                            invalid_candidates.append(
                                f"{identity}:{candidate_index}:source_file"
                            )
                        if check.get(
                            "require_source_manifest_binding", False
                        ):
                            candidate_source_id = str(
                                candidate.get("source_id") or ""
                            ).strip()
                            expected_source_file = source_paths_by_id.get(
                                candidate_source_id
                            )
                            if expected_source_file is None:
                                invalid_candidates.append(
                                    f"{identity}:{candidate_index}:unknown_source_id"
                                )
                            elif (
                                source_file is None
                                or source_file.resolve()
                                != expected_source_file
                            ):
                                invalid_candidates.append(
                                    f"{identity}:{candidate_index}:source_identity_file"
                                )
                        try:
                            if "source_in_frame" in candidate or "source_out_frame" in candidate:
                                source_in = int(candidate["source_in_frame"])
                                source_out = int(candidate["source_out_frame"])
                            else:
                                source_in = float(candidate["source_in"])
                                source_out = float(candidate["source_out"])
                            if source_out <= source_in:
                                raise ValueError
                        except (KeyError, TypeError, ValueError):
                            invalid_candidates.append(
                                f"{identity}:{candidate_index}:source_range"
                            )
                        if require_pool_evidence:
                            evidence = candidate.get("evidence", {})
                            for sample in ("head", "mid", "tail"):
                                raw_evidence = candidate.get(
                                    f"{sample}_evidence"
                                )
                                if not raw_evidence and isinstance(evidence, dict):
                                    raw_evidence = evidence.get(sample)
                                if isinstance(raw_evidence, dict):
                                    raw_evidence = raw_evidence.get("path")
                                if resolved_existing_file(root, raw_evidence) is None:
                                    missing_candidate_evidence.append(
                                        f"{identity}:{candidate_index}:{sample}"
                                    )
                    selected_id = str(
                        next(
                            (
                                row.get("selected_candidate_id", "")
                                for row in rows
                                if cue_id(row, 0) == identity
                            ),
                            "",
                        )
                    ).strip()
                    if selected_id and selected_id not in candidate_ids:
                        failures.append(
                            f"cue {identity}: selected_candidate_id is not in candidate pool"
                        )
                    elif not selected_id:
                        failures.append(
                            f"cue {identity}: selected_candidate_id is required"
                        )
                    else:
                        selected_pool_candidate = candidates_by_id[selected_id]
                        selected_row = next(
                            (
                                row
                                for row in rows
                                if cue_id(row, 0) == identity
                            ),
                            {},
                        )
                        pool_source_id = str(
                            selected_pool_candidate.get("source_id") or ""
                        ).strip()
                        row_source_id = str(
                            selected_row.get("selected_source_id")
                            or selected_row.get("source_id")
                            or ""
                        ).strip()
                        if pool_source_id and row_source_id != pool_source_id:
                            failures.append(
                                f"cue {identity}: selected pool source_id differs "
                                "from match sheet"
                            )
                        pool_source_file = resolved_existing_file(
                            root,
                            selected_pool_candidate.get("source_file", ""),
                        )
                        row_source_file = resolved_existing_file(
                            root, selected_row.get("source_file", "")
                        )
                        if (
                            pool_source_file is None
                            or row_source_file is None
                            or pool_source_file.resolve()
                            != row_source_file.resolve()
                        ):
                            failures.append(
                                f"cue {identity}: selected pool source_file differs "
                                "from match sheet"
                            )
                        if {
                            "source_in",
                            "source_out",
                        }.issubset(selected_pool_candidate):
                            try:
                                if (
                                    abs(
                                        float(selected_pool_candidate["source_in"])
                                        - float(selected_row.get("source_in", ""))
                                    )
                                    > 0.002
                                    or abs(
                                        float(selected_pool_candidate["source_out"])
                                        - float(selected_row.get("source_out", ""))
                                    )
                                    > 0.022
                                ):
                                    failures.append(
                                        f"cue {identity}: selected pool range differs "
                                        "from match sheet"
                                    )
                            except (TypeError, ValueError):
                                failures.append(
                                    f"cue {identity}: selected pool range is invalid"
                                )
                        elif {
                            "source_in_frame",
                            "source_out_frame",
                        }.issubset(selected_pool_candidate):
                            try:
                                if (
                                    int(selected_pool_candidate["source_in_frame"])
                                    != int(
                                        selected_row.get(
                                            "selected_source_in_frame", ""
                                        )
                                    )
                                    or int(
                                        selected_pool_candidate["source_out_frame"]
                                    )
                                    != int(
                                        selected_row.get(
                                            "selected_source_out_frame", ""
                                        )
                                    )
                                ):
                                    failures.append(
                                        f"cue {identity}: selected pool frame range "
                                        "differs from match sheet"
                                    )
                            except (TypeError, ValueError):
                                failures.append(
                                    f"cue {identity}: selected pool frame binding is missing"
                                )
                    if check.get("require_candidate_ids", False):
                        selected_row = next(
                            (
                                row
                                for row in rows
                                if cue_id(row, 0) == identity
                            ),
                            {},
                        )
                        for letter in "abc":
                            top_id = str(
                                selected_row.get(
                                    f"candidate_{letter}_id", ""
                                )
                            ).strip()
                            if top_id not in candidate_ids:
                                failures.append(
                                    f"cue {identity}: candidate_{letter}_id "
                                    "is not in candidate pool"
                                )
                expected_pool_ids = {
                    identity
                    for index, row in enumerate(rows, start=1)
                    if (identity := cue_id(row, index)) is not None
                }
                if set(pool_by_id) != expected_pool_ids:
                    failures.append(
                        "candidate pool coverage missing="
                        f"{sorted(expected_pool_ids - set(pool_by_id))}, "
                        f"extra={sorted(set(pool_by_id) - expected_pool_ids)}"
                    )
                if duplicate_pool_ids:
                    failures.append(
                        f"duplicate candidate-pool cue IDs={duplicate_pool_ids}"
                    )
                if invalid_candidates:
                    failures.append(
                        f"invalid candidate-pool entries={invalid_candidates[:30]}"
                    )
                if missing_candidate_evidence:
                    failures.append(
                        "missing candidate-pool head/mid/tail evidence="
                        f"{missing_candidate_evidence[:30]}"
                    )
                pool_metrics = {
                    "rows": len(pool_rows),
                    "min_candidates": min_pool_candidates,
                    "preferred_candidates": preferred_pool_candidates,
                    "shortfall_cue_ids": shortfall_ids,
                    "invalid_candidates": invalid_candidates,
                    "missing_candidate_evidence": missing_candidate_evidence,
                }
        elif check.get("require_candidate_pool", False):
            failures.append("visual match plan requires candidate_pool_path")
        manifest_path = (
            resolve_path(root, check["manifest_path"])
            if check.get("manifest_path")
            else None
        )
        if check.get("require_manifest", True) and not (
            manifest_path and manifest_path.is_file()
        ):
            failures.append("visual match plan requires a nonempty manifest_path")
        elif manifest_path and manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("status") != "PASS":
                failures.append("match plan manifest status must be PASS")
            expected_sheet_sha = manifest_hash_value(
                manifest, "match_sheet_sha256", "match_sheet.sha256"
            )
            expected_srt_sha = manifest_hash_value(
                manifest, "canonical_srt_sha256", "canonical_srt.sha256"
            )
            if expected_sheet_sha != metrics["match_sheet_sha256"]:
                failures.append("match plan manifest has stale match_sheet_sha256")
            if expected_srt_sha != metrics["canonical_srt_sha256"]:
                failures.append("match plan manifest has stale canonical_srt_sha256")
            if candidate_pool_path is not None:
                expected_pool_sha = manifest_hash_value(
                    manifest,
                    "candidate_pool_sha256",
                    "candidate_pool.sha256",
                )
                if expected_pool_sha != candidate_pool_sha:
                    failures.append(
                        "match plan manifest has stale candidate_pool_sha256"
                    )
            if check.get("require_index_binding", False):
                for field, manifest_fields in (
                    (
                        "shot_index_path",
                        ("shot_index_sha256", "shot_index.sha256"),
                    ),
                    (
                        "ocr_index_path",
                        ("ocr_index_sha256", "shot_ocr_index_sha256"),
                    ),
                    (
                        "source_manifest_path",
                        (
                            "source_manifest_sha256",
                            "source_identity_manifest_sha256",
                        ),
                    ),
                ):
                    bound_path = (
                        resolve_path(root, check[field])
                        if check.get(field)
                        else None
                    )
                    if bound_path is None or not bound_path.is_file():
                        failures.append(
                            f"match plan index binding is missing {field}"
                        )
                        continue
                    if manifest_hash_value(
                        manifest, *manifest_fields
                    ) != file_sha256(bound_path):
                        failures.append(
                            f"match plan manifest has stale {field} SHA"
                        )
            if int(manifest.get("row_count", -1)) != len(rows):
                failures.append("match plan manifest row_count mismatch")
            if check.get("index_manifest_path"):
                index_manifest_path = resolve_path(
                    root, check["index_manifest_path"]
                )
                if not index_manifest_path.is_file():
                    failures.append(f"missing index manifest={index_manifest_path}")
                else:
                    expected_index_sha = manifest_hash_value(
                        manifest,
                        "visual_index_manifest_sha256",
                        "index_manifest_sha256",
                    )
                    if expected_index_sha != file_sha256(index_manifest_path):
                        failures.append(
                            "match plan manifest has stale visual index hash"
                        )
            metrics["manifest_sha256"] = file_sha256(manifest_path)
        metrics["failures"] = failures
        metrics["candidate_pool_sha256"] = candidate_pool_sha
        metrics["candidate_pool"] = pool_metrics
        return (
            not failures,
            f"rows={len(rows)}, candidates={metrics['three_candidate_rows']}, failures={failures}",
            metrics,
        )

    if check_type == "visual_selection_review_integrity":
        required_config = [
            field
            for field in ("match_sheet_path", "evidence_manifest_path")
            if field not in check
        ]
        if required_config:
            return False, f"check config missing {required_config}", {
                "config_missing": required_config
            }
        review = json.loads(path.read_text(encoding="utf-8"))
        match_sheet_path = resolve_path(root, check["match_sheet_path"])
        evidence_manifest_path = resolve_path(root, check["evidence_manifest_path"])
        candidate_pool_path = (
            resolve_path(root, check["candidate_pool_path"])
            if check.get("candidate_pool_path")
            else None
        )
        failures: list[str] = []
        if not match_sheet_path.is_file():
            failures.append(f"missing match sheet={match_sheet_path}")
        if not evidence_manifest_path.is_file():
            failures.append(f"missing evidence manifest={evidence_manifest_path}")
        if check.get("require_candidate_pool_binding", False) and (
            candidate_pool_path is None
            or not candidate_pool_path.is_file()
        ):
            failures.append("review requires a current candidate_pool_path")
        if failures:
            return False, f"failures={failures}", {"failures": failures}
        _, match_rows = read_tsv(match_sheet_path)
        _, evidence_rows = read_tsv(evidence_manifest_path)
        if check.get("review_granularity") == SEMANTIC_VISUAL_UNIT_GRANULARITY:
            if candidate_pool_path is None or not candidate_pool_path.is_file():
                return False, "semantic review requires candidate_pool_path", {}
            semantic_failures, semantic_metrics = semantic_review_failures(
                root,
                path,
                review,
                match_sheet_path,
                evidence_manifest_path,
                candidate_pool_path,
                check,
            )
            failures.extend(semantic_failures)
            source_metrics: dict[str, Any] = {}
            if check.get("require_source_manifest_binding", False):
                source_manifest_path = (
                    resolve_path(root, check["source_manifest_path"])
                    if check.get("source_manifest_path")
                    else None
                )
                if source_manifest_path is None or not source_manifest_path.is_file():
                    failures.append("semantic review requires source_manifest_path")
                else:
                    source_failures, source_metrics = candidate_source_manifest_failures(
                        root, read_jsonl(candidate_pool_path), source_manifest_path
                    )
                    failures.extend(source_failures)
                    source_sha = file_sha256(source_manifest_path)
                    if manifest_hash_value(
                        review,
                        "source_manifest_sha256",
                        "source_identity_manifest_sha256",
                    ) != source_sha:
                        failures.append(
                            "review manifest has stale source_manifest_sha256"
                        )
                    semantic_metrics["source_manifest_sha256"] = source_sha
            semantic_metrics["source_binding"] = source_metrics
            semantic_metrics["failures"] = failures
            semantic_metrics["workflow_ready"] = (
                semantic_metrics.get("status") == "PASS"
                and not semantic_metrics.get("unresolved_visual_unit_ids")
                and not failures
            )
            return (
                not failures,
                (
                    f"rows={len(match_rows)}, "
                    f"units={semantic_metrics.get('visual_units', 0)}, "
                    f"failures={failures}"
                ),
                semantic_metrics,
            )
        match_by_id = {
            identity: row
            for index, row in enumerate(match_rows, start=1)
            if (identity := cue_id(row, index)) is not None
        }
        layered_review = bool(check.get("require_layered_review", False))
        derived_risk_ids = {
            identity
            for identity, row in match_by_id.items()
            if visual_row_is_risk(row)
        }
        derived_identity_ids = {
            identity
            for identity, row in match_by_id.items()
            if truthy(row.get("identity_required"))
            or split_identity_values(row.get("named_entities_expected", ""))
        }
        trusted_paths: set[Path] = set()
        trusted_selected_contact_paths: list[Path] = []
        selected_sheet_ids: set[int] = set()
        risk_sheet_ids: set[int] = set()
        declared_identity: set[int] = set()
        risk_frame_records: dict[
            tuple[int, str, str], dict[str, Any]
        ] = {}
        if layered_review:
            files = review.get("files")
            if not isinstance(files, list) or not files:
                failures.append("review manifest must list trusted evidence files")
                files = []
            for file_index, record in enumerate(files):
                if (
                    not isinstance(record, dict)
                    or not record.get("path")
                    or not record.get("sha256")
                ):
                    failures.append(
                        f"review manifest file record {file_index} lacks path/sha256"
                    )
                    continue
                raw_path = Path(str(record["path"])).expanduser()
                file_path = (
                    raw_path.resolve()
                    if raw_path.is_absolute()
                    else (path.parent / raw_path).resolve()
                )
                if file_path in trusted_paths:
                    failures.append(
                        f"review manifest duplicates trusted file={file_path}"
                    )
                trusted_paths.add(file_path)
                if not file_path.is_file():
                    failures.append(f"review evidence file is missing={file_path}")
                elif file_sha256(file_path) != str(record["sha256"]).lower():
                    failures.append(f"review evidence file hash mismatch={file_path}")
                cue_ids = record.get("cue_ids", [])
                parsed_file_ids = set()
                if isinstance(cue_ids, list):
                    for raw_id in cue_ids:
                        try:
                            parsed_file_ids.add(int(raw_id))
                        except (TypeError, ValueError):
                            failures.append(
                                f"review file {file_index} has invalid cue ID={raw_id!r}"
                            )
                if record.get("kind") == "selected_sheet":
                    selected_sheet_ids.update(parsed_file_ids)
                    trusted_selected_contact_paths.append(file_path)
                if record.get("kind") == "risk_abc_sheet":
                    risk_sheet_ids.update(parsed_file_ids)
                if record.get("kind") == "evidence_frame":
                    view = str(record.get("view", "")).upper()
                    sample = str(record.get("sample", "")).lower()
                    if (
                        len(parsed_file_ids) == 1
                        and view in {"A", "B", "C"}
                        and sample in {"head", "mid", "tail"}
                    ):
                        identity = next(iter(parsed_file_ids))
                        matrix_key = (identity, view, sample)
                        if matrix_key in risk_frame_records:
                            failures.append(
                                "duplicate risk evidence frame="
                                f"{matrix_key}"
                            )
                        risk_frame_records[matrix_key] = record

            selected_reviewed = {
                int(item) for item in review.get("selected_reviewed_ids", [])
            }
            declared_risk = {
                int(item) for item in review.get("risk_row_ids", [])
            }
            candidate_reviewed = {
                int(item) for item in review.get("candidate_reviewed_ids", [])
            }
            declared_identity = {
                int(item) for item in review.get("identity_required_ids", [])
            }
            unknown_review_ids = (
                selected_reviewed
                | declared_risk
                | candidate_reviewed
                | declared_identity
            ) - set(match_by_id)
            if unknown_review_ids:
                failures.append(
                    f"review manifest references unknown cues={sorted(unknown_review_ids)}"
                )
            if selected_reviewed != set(match_by_id):
                failures.append(
                    "selected review coverage missing="
                    f"{sorted(set(match_by_id) - selected_reviewed)}, "
                    f"extra={sorted(selected_reviewed - set(match_by_id))}"
                )
            if not derived_risk_ids.issubset(declared_risk):
                failures.append(
                    "review manifest omits derived risk cues="
                    f"{sorted(derived_risk_ids - declared_risk)}"
                )
            if not declared_risk.issubset(candidate_reviewed):
                failures.append(
                    "candidate review coverage missing="
                    f"{sorted(declared_risk - candidate_reviewed)}"
                )
            if not derived_identity_ids.issubset(declared_identity):
                failures.append(
                    "identity-required coverage missing="
                    f"{sorted(derived_identity_ids - declared_identity)}"
                )
            if not set(match_by_id).issubset(selected_sheet_ids):
                failures.append(
                    "selected contact sheets omit cues="
                    f"{sorted(set(match_by_id) - selected_sheet_ids)}"
                )
            if not declared_risk.issubset(risk_sheet_ids):
                failures.append(
                    "risk A/B/C contact sheets omit cues="
                    f"{sorted(declared_risk - risk_sheet_ids)}"
                )
            if check.get("require_risk_frame_matrix", False):
                candidate_pool_path = (
                    resolve_path(root, check["candidate_pool_path"])
                    if check.get("candidate_pool_path")
                    else None
                )
                if (
                    candidate_pool_path is None
                    or not candidate_pool_path.is_file()
                ):
                    failures.append(
                        "risk-frame review requires candidate_pool_path"
                    )
                    candidate_pool_rows: list[dict[str, Any]] = []
                else:
                    candidate_pool_rows = read_jsonl(candidate_pool_path)
                candidate_pool_by_id: dict[
                    int, dict[str, dict[str, Any]]
                ] = {}
                for pool_entry in candidate_pool_rows:
                    try:
                        pool_identity = int(
                            pool_entry.get("cue_id")
                            or pool_entry.get("line_id")
                        )
                    except (AttributeError, TypeError, ValueError):
                        continue
                    candidate_pool_by_id[pool_identity] = {
                        str(candidate.get("candidate_id")): candidate
                        for candidate in pool_entry.get("candidates", [])
                        if isinstance(candidate, dict)
                        and candidate.get("candidate_id")
                    }
                for identity in sorted(declared_risk):
                    match_row = match_by_id.get(identity, {})
                    for view in ("A", "B", "C"):
                        expected_candidate_id = str(
                            match_row.get(
                                f"candidate_{view.lower()}_id", ""
                            )
                        ).strip()
                        pool_candidate = candidate_pool_by_id.get(
                            identity, {}
                        ).get(expected_candidate_id)
                        if not expected_candidate_id:
                            failures.append(
                                f"cue {identity}: candidate_{view.lower()}_id "
                                "is required for risk review"
                            )
                        elif pool_candidate is None:
                            failures.append(
                                f"cue {identity}: risk candidate {view} "
                                "is not in candidate pool"
                            )
                        for sample in ("head", "mid", "tail"):
                            record = risk_frame_records.get(
                                (identity, view, sample)
                            )
                            if record is None:
                                failures.append(
                                    "missing risk evidence frame="
                                    f"{(identity, view, sample)}"
                                )
                                continue
                            if (
                                str(record.get("candidate_id") or "")
                                != expected_candidate_id
                            ):
                                failures.append(
                                    f"cue {identity} {view} {sample}: "
                                    "evidence candidate_id mismatch"
                                )
                            if pool_candidate is None:
                                continue
                            record_source = resolved_existing_file(
                                root, record.get("source_file", "")
                            )
                            pool_source = resolved_existing_file(
                                root,
                                pool_candidate.get("source_file", ""),
                            )
                            if (
                                record_source is None
                                or pool_source is None
                                or record_source.resolve()
                                != pool_source.resolve()
                            ):
                                failures.append(
                                    f"cue {identity} {view} {sample}: "
                                    "evidence source_file mismatch"
                                )
                            if (
                                str(record.get("source_id") or "")
                                != str(
                                    pool_candidate.get("source_id") or ""
                                )
                            ):
                                failures.append(
                                    f"cue {identity} {view} {sample}: "
                                    "evidence source_id mismatch"
                                )
                            try:
                                record_in = float(record["source_in"])
                                record_out = float(record["source_out"])
                                pool_in = float(pool_candidate["source_in"])
                                pool_out = float(pool_candidate["source_out"])
                                timestamp = float(record["timestamp"])
                                if (
                                    abs(record_in - pool_in) > 0.002
                                    or abs(record_out - pool_out) > 0.022
                                    or timestamp < record_in - 0.002
                                    or timestamp > record_out + 0.002
                                ):
                                    raise ValueError
                            except (KeyError, TypeError, ValueError):
                                failures.append(
                                    f"cue {identity} {view} {sample}: "
                                    "evidence source range mismatch"
                                )
        evidence_by_id: dict[int, dict[str, str]] = {}
        duplicate_evidence_ids: list[int] = []
        for index, row in enumerate(evidence_rows, start=1):
            identity = cue_id(row, index)
            if identity is None:
                failures.append(f"evidence row {index}: invalid cue ID")
                continue
            if identity in evidence_by_id:
                duplicate_evidence_ids.append(identity)
            evidence_by_id[identity] = row
        expected_ids = set(match_by_id)
        evidence_ids = set(evidence_by_id)
        if duplicate_evidence_ids:
            failures.append(f"duplicate evidence cue IDs={duplicate_evidence_ids}")
        if evidence_ids != expected_ids:
            failures.append(
                f"evidence coverage missing={sorted(expected_ids - evidence_ids)}, "
                f"extra={sorted(evidence_ids - expected_ids)}"
            )
        accepted_review_statuses = {
            value.lower()
            for value in check.get(
                "accepted_visual_review_statuses",
                ["approved_manual", "approved", "verified", "pass"],
            )
        }
        for identity in sorted(expected_ids & evidence_ids):
            selected = match_by_id[identity]
            evidence_row = evidence_by_id[identity]
            if evidence_row.get("caption", selected.get("text", "")).strip() != selected.get(
                "text", ""
            ).strip():
                failures.append(f"cue {identity}: evidence caption mismatch")
            for field in ("source_id", "source_file"):
                if evidence_row.get(field, "").strip() != selected.get(field, "").strip():
                    failures.append(f"cue {identity}: evidence {field} mismatch")
            for field in ("source_in", "source_out"):
                try:
                    evidence_value = float(evidence_row.get(field, ""))
                    selected_value = float(selected.get(field, ""))
                    if abs(evidence_value - selected_value) > 0.002:
                        failures.append(f"cue {identity}: evidence {field} mismatch")
                except ValueError:
                    failures.append(f"cue {identity}: invalid evidence {field}")
            evidence_path = resolved_existing_file(
                root,
                evidence_row.get("evidence_image", "")
                or evidence_row.get("evidence_path", ""),
            )
            if evidence_path is None:
                failures.append(f"cue {identity}: evidence image missing")
            elif layered_review and evidence_path.resolve() not in trusted_paths:
                failures.append(
                    f"cue {identity}: selected evidence is not in trusted files"
                )
            review_status = evidence_row.get("visual_review", "").strip().lower()
            if review_status not in accepted_review_statuses:
                failures.append(
                    f"cue {identity}: visual_review={review_status!r} is not approved"
                )
            black_value = (
                evidence_row.get("black_midpoint", "")
                or evidence_row.get("black", "")
            ).strip().lower()
            if black_value in {"1", "true", "yes"}:
                failures.append(f"cue {identity}: selected evidence is black")

        match_sha = file_sha256(match_sheet_path)
        evidence_sha = file_sha256(evidence_manifest_path)
        candidate_pool_sha = (
            file_sha256(candidate_pool_path)
            if candidate_pool_path is not None
            and candidate_pool_path.is_file()
            else ""
        )
        source_binding_metrics: dict[str, Any] = {}
        source_manifest_sha = ""
        if check.get("require_source_manifest_binding", False):
            source_manifest_path = (
                resolve_path(root, check["source_manifest_path"])
                if check.get("source_manifest_path")
                else None
            )
            if (
                source_manifest_path is None
                or not source_manifest_path.is_file()
                or candidate_pool_path is None
                or not candidate_pool_path.is_file()
            ):
                failures.append(
                    "review source binding requires current source manifest "
                    "and candidate pool"
                )
            else:
                source_manifest_sha = file_sha256(source_manifest_path)
                source_failures, source_binding_metrics = (
                    candidate_source_manifest_failures(
                        root,
                        read_jsonl(candidate_pool_path),
                        source_manifest_path,
                    )
                )
                failures.extend(source_failures)
                if manifest_hash_value(
                    review,
                    "source_manifest_sha256",
                    "source_identity_manifest_sha256",
                ) != source_manifest_sha:
                    failures.append(
                        "review manifest has stale source_manifest_sha256"
                    )
        review_match_sha = manifest_hash_value(
            review, "match_sheet_sha256", "final_match_sheet_sha256"
        )
        if review_match_sha != match_sha:
            failures.append("review manifest has stale match_sheet_sha256")
        if check.get("require_candidate_pool_binding", False) and (
            manifest_hash_value(
                review,
                "candidate_pool_sha256",
                "candidate_pool.sha256",
            )
            != candidate_pool_sha
        ):
            failures.append(
                "review manifest has stale candidate_pool_sha256"
            )
        review_evidence_sha = manifest_hash_value(
            review, "evidence_manifest_sha256", "selected_evidence_manifest_sha256"
        )
        if review_evidence_sha and review_evidence_sha != evidence_sha:
            failures.append("review manifest has stale evidence_manifest_sha256")
        if int(review.get("row_count", -1)) != len(match_rows):
            failures.append("review manifest row_count mismatch")

        contact_sheets: list[object] = []
        raw_contact_sheets = review.get("contact_sheets")
        if isinstance(raw_contact_sheets, list):
            contact_sheets = raw_contact_sheets
        elif check.get("contact_sheet_audit_path"):
            contact_audit_path = resolve_path(
                root, check["contact_sheet_audit_path"]
            )
            if not contact_audit_path.is_file():
                failures.append(f"missing contact sheet audit={contact_audit_path}")
            else:
                contact_audit = json.loads(
                    contact_audit_path.read_text(encoding="utf-8")
                )
                if manifest_hash_value(
                    contact_audit, "match_sheet_sha256"
                ) != match_sha:
                    failures.append("contact sheet audit has stale match_sheet_sha256")
                contact_sheets = contact_audit.get("contact_sheets", [])
        if not contact_sheets and layered_review:
            contact_sheets = [
                {"path": str(contact_path)}
                for contact_path in trusted_selected_contact_paths
            ]
        for item in contact_sheets:
            raw_path = item.get("path") if isinstance(item, dict) else item
            contact_path = resolved_existing_file(root, raw_path)
            if contact_path is None:
                failures.append(f"missing selected contact sheet={raw_path}")
            elif layered_review and contact_path.resolve() not in trusted_paths:
                failures.append(
                    f"selected contact sheet is not in trusted files={contact_path}"
                )
        if check.get("require_contact_sheets", True) and not contact_sheets:
            failures.append("selected contact sheets are required")

        range_reviews = review.get("range_reviews")
        if not isinstance(range_reviews, list):
            human_review = review.get("human_review", {})
            range_reviews = (
                human_review.get("range_reviews", [])
                if isinstance(human_review, dict)
                else []
            )
        covered_ids: list[int] = []
        for item in range_reviews:
            if not isinstance(item, dict):
                failures.append("range review must be an object")
                continue
            parsed_range = _parse_review_range(
                item.get("range")
                or {"start": item.get("start"), "end": item.get("end")}
            )
            if parsed_range is None or parsed_range[0] > parsed_range[1]:
                failures.append(f"invalid review range={item.get('range')!r}")
                continue
            if str(item.get("status", "")).upper() != "PASS":
                failures.append(f"review range {parsed_range} did not pass")
            covered_ids.extend(range(parsed_range[0], parsed_range[1] + 1))
        if check.get("require_range_reviews", True):
            if covered_ids != list(range(1, len(match_rows) + 1)):
                failures.append(
                    "range reviews must cover every cue exactly once in order"
                )

        identity_checks_raw = review.get("identity_checks")
        if not isinstance(identity_checks_raw, list):
            human_review = review.get("human_review", {})
            identity_checks_raw = (
                human_review.get("identity_checks", [])
                if isinstance(human_review, dict)
                else []
            )
        identity_checks = {
            int(item.get("cue_id")): item
            for item in identity_checks_raw
            if isinstance(item, dict)
            and str(item.get("cue_id", "")).isdigit()
        }
        named_identity_rows = []
        identity_verified_raw = review.get("identity_verified", {})
        identity_verified = (
            {
                int(key): str(value)
                for key, value in identity_verified_raw.items()
                if str(key).isdigit()
            }
            if isinstance(identity_verified_raw, dict)
            else {}
        )
        if layered_review:
            verified_identity_ids = {
                identity
                for identity, value in identity_verified.items()
                if value.strip().casefold()
                not in {"", "unverified", "pending", "false", "needs_repair"}
            } | {
                identity
                for identity, identity_check in identity_checks.items()
                if str(identity_check.get("status", "")).upper() == "PASS"
                and split_identity_values(identity_check.get("visible", []))
            }
            if not declared_identity.issubset(verified_identity_ids):
                failures.append(
                    "identity verdict coverage missing="
                    f"{sorted(declared_identity - verified_identity_ids)}"
                )
        if check.get("require_named_identity", True):
            for identity, row in match_by_id.items():
                expected = split_identity_values(
                    row.get("named_entities_expected", "")
                )
                if not expected:
                    continue
                named_identity_rows.append(identity)
                identity_check = identity_checks.get(identity)
                if identity_check:
                    declared_expected = split_identity_values(
                        identity_check.get("expected", [])
                    )
                    visible = split_identity_values(identity_check.get("visible", []))
                    if declared_expected != expected:
                        failures.append(
                            f"cue {identity}: identity expected set does not match match sheet"
                        )
                    if not set(expected).issubset(visible):
                        failures.append(
                            f"cue {identity}: expected named identity is not visibly verified"
                        )
                    if str(identity_check.get("status", "")).upper() != "PASS":
                        failures.append(f"cue {identity}: identity check did not pass")
                    continue
                verified_value = identity_verified.get(identity, "").strip()
                if not verified_value:
                    failures.append(f"cue {identity}: named identity check missing")
                    continue
                if verified_value.casefold() in {
                    "unverified",
                    "pending",
                    "false",
                    "needs_repair",
                }:
                    failures.append(f"cue {identity}: named identity is unresolved")
                    continue
                visible = split_identity_values(verified_value)
                if visible and not set(expected).issubset(visible):
                    failures.append(
                        f"cue {identity}: expected named identity is not visibly verified"
                    )

        unresolved_raw = review.get("unresolved_cue_ids")
        if unresolved_raw is None:
            unresolved_raw = review.get("unresolved_ids")
        if unresolved_raw is None:
            human_review = review.get("human_review", {})
            unresolved_raw = (
                human_review.get("unresolved_hard_failures", [])
                if isinstance(human_review, dict)
                else []
            )
        unresolved: list[int] = []
        for item in unresolved_raw if isinstance(unresolved_raw, list) else []:
            raw_id = item.get("cue_id") if isinstance(item, dict) else item
            try:
                unresolved.append(int(raw_id))
            except (TypeError, ValueError):
                failures.append(f"invalid unresolved cue={raw_id!r}")
        unresolved = sorted(set(unresolved))
        allow_unresolved = bool(check.get("allow_unresolved", False))
        review_status = str(review.get("status", "")).upper()
        allowed_statuses = {"PASS", "NEEDS_REPAIR"} if allow_unresolved else {"PASS"}
        if review_status not in allowed_statuses:
            failures.append(
                f"review status={review_status!r}, expected one of {sorted(allowed_statuses)}"
            )
        if allow_unresolved:
            if review_status == "NEEDS_REPAIR" and not unresolved:
                failures.append("NEEDS_REPAIR review must name unresolved cue IDs")
        elif unresolved:
            failures.append(f"unresolved cue IDs remain={unresolved}")

        special_sequences_ready = True
        for label, required in (
            ("opening_review", bool(check.get("require_opening_review", False))),
            ("ending_review", bool(check.get("require_ending_review", False))),
        ):
            if not required:
                continue
            section = review.get(label)
            section_status = (
                str(section.get("status", "")).upper()
                if isinstance(section, dict)
                else ""
            )
            acceptable = (
                {"PASS", "NEEDS_REPAIR"}
                if allow_unresolved
                else {"PASS"}
            )
            if section_status not in acceptable:
                failures.append(
                    f"{label} is required and must be one of {sorted(acceptable)}"
                )
            if section_status != "PASS":
                special_sequences_ready = False

        workflow_ready = (
            review_status == "PASS"
            and not unresolved
            and special_sequences_ready
        )
        metrics = {
            "status": review_status,
            "rows": len(match_rows),
            "evidence_rows": len(evidence_rows),
            "contact_sheet_count": len(contact_sheets),
            "range_review_count": len(range_reviews),
            "named_identity_rows": named_identity_rows,
            "derived_risk_row_ids": sorted(derived_risk_ids),
            "selected_sheet_ids": sorted(selected_sheet_ids),
            "risk_sheet_ids": sorted(risk_sheet_ids),
            "unresolved_cue_ids": unresolved,
            "workflow_ready": workflow_ready,
            "match_sheet_sha256": match_sha,
            "evidence_manifest_sha256": evidence_sha,
            "candidate_pool_sha256": candidate_pool_sha,
            "source_binding": source_binding_metrics,
            "source_manifest_sha256": source_manifest_sha,
            "review_manifest_sha256": file_sha256(path),
            "failures": failures,
        }
        return (
            not failures,
            (
                f"rows={len(match_rows)}, reviewed={len(evidence_rows)}, "
                f"unresolved={unresolved}, workflow_ready={workflow_ready}, failures={failures}"
            ),
            metrics,
        )

    if check_type == "visual_match_repair_integrity":
        required_config = [
            field
            for field in ("before_match_sheet_path", "after_match_sheet_path")
            if field not in check
        ]
        if required_config:
            return False, f"check config missing {required_config}", {
                "config_missing": required_config
            }
        manifest = json.loads(path.read_text(encoding="utf-8"))
        before_path = resolve_path(root, check["before_match_sheet_path"])
        after_path = resolve_path(root, check["after_match_sheet_path"])
        before_pool_path = (
            resolve_path(root, check["before_candidate_pool_path"])
            if check.get("before_candidate_pool_path")
            else None
        )
        after_pool_path = (
            resolve_path(root, check["after_candidate_pool_path"])
            if check.get("after_candidate_pool_path")
            else None
        )
        failures: list[str] = []
        if not before_path.is_file():
            failures.append(f"missing before match sheet={before_path}")
        if not after_path.is_file():
            failures.append(f"missing after match sheet={after_path}")
        if failures:
            return False, f"failures={failures}", {"failures": failures}
        for label, candidate in (
            ("before_candidate_pool_path", before_pool_path),
            ("after_candidate_pool_path", after_pool_path),
        ):
            if candidate is not None and not candidate.is_file():
                failures.append(f"missing {label}={candidate}")
        if failures:
            return False, f"failures={failures}", {"failures": failures}
        _, before_rows = read_tsv(before_path)
        _, after_rows = read_tsv(after_path)
        before_by_id = {
            identity: row
            for index, row in enumerate(before_rows, start=1)
            if (identity := cue_id(row, index)) is not None
        }
        after_by_id = {
            identity: row
            for index, row in enumerate(after_rows, start=1)
            if (identity := cue_id(row, index)) is not None
        }
        if set(before_by_id) != set(after_by_id):
            failures.append("repair may not add, remove, or renumber match rows")
        protected_fields = {
            "line_id",
            "text",
            "caption_start",
            "caption_end",
            "start",
            "end",
            "duration",
        }
        actual_changed: list[int] = []
        protected_changes: list[str] = []
        for identity in sorted(set(before_by_id) & set(after_by_id)):
            before_row = before_by_id[identity]
            after_row = after_by_id[identity]
            if tsv_rows_differ(before_row, after_row):
                actual_changed.append(identity)
            for field in protected_fields:
                if field in before_row or field in after_row:
                    if before_row.get(field, "") != after_row.get(field, ""):
                        protected_changes.append(f"{identity}:{field}")
        if protected_changes:
            failures.append(f"repair changed protected caption fields={protected_changes}")
        declared_changed: list[int] = []
        for item in manifest.get("changed_cue_ids", []):
            try:
                declared_changed.append(int(item))
            except (TypeError, ValueError):
                failures.append(f"invalid changed cue ID={item!r}")
        declared_changed = sorted(set(declared_changed))
        if actual_changed != declared_changed:
            failures.append(
                f"hidden or missing repair rows: actual={actual_changed}, declared={declared_changed}"
            )
        repairs = manifest.get("repairs", [])
        repair_by_id = {
            int(item.get("cue_id")): item
            for item in repairs
            if isinstance(item, dict)
            and str(item.get("cue_id", "")).isdigit()
        }
        if sorted(repair_by_id) != declared_changed:
            failures.append(
                "repair entries must exactly match changed_cue_ids"
            )
        for identity in declared_changed:
            repair = repair_by_id.get(identity, {})
            if not str(repair.get("reason", "")).strip():
                failures.append(f"cue {identity}: repair reason missing")
            raw_evidence = repair.get("evidence") or repair.get("evidence_path")
            if check.get("require_repair_evidence", True) and resolved_existing_file(
                root, raw_evidence
            ) is None:
                failures.append(f"cue {identity}: repair evidence missing")
            expected_identities = split_identity_values(
                after_by_id.get(identity, {}).get("named_entities_expected", "")
            )
            if expected_identities:
                identity_check = repair.get("identity_check")
                if not isinstance(identity_check, dict):
                    failures.append(
                        f"cue {identity}: named-entity repair lacks identity_check"
                    )
                else:
                    visible = split_identity_values(identity_check.get("visible", []))
                    if not set(expected_identities).issubset(visible):
                        failures.append(
                            f"cue {identity}: repaired identity was not visibly verified"
                        )
                    if str(identity_check.get("status", "")).upper() != "PASS":
                        failures.append(f"cue {identity}: repair identity check failed")

        before_sha = file_sha256(before_path)
        after_sha = file_sha256(after_path)
        if manifest_hash_value(
            manifest, "before_match_sheet_sha256", "input_match_sheet_sha256"
        ) != before_sha:
            failures.append("repair manifest has stale before_match_sheet_sha256")
        if manifest_hash_value(
            manifest, "after_match_sheet_sha256", "output_match_sheet_sha256"
        ) != after_sha:
            failures.append("repair manifest has stale after_match_sheet_sha256")
        before_pool_sha = ""
        after_pool_sha = ""
        semantic_repair_mode = (
            check.get("candidate_pool_granularity")
            == SEMANTIC_VISUAL_UNIT_GRANULARITY
        )
        actual_pool_changed: list[int | str] = []
        added_candidate_ids: list[str] = []
        pool_binding_metrics: dict[str, Any] = {}
        repair_source_binding_metrics: dict[str, Any] = {}
        if before_pool_path is not None and after_pool_path is not None:
            before_pool_sha = file_sha256(before_pool_path)
            after_pool_sha = file_sha256(after_pool_path)
            if manifest_hash_value(
                manifest,
                "before_candidate_pool_sha256",
                "candidate_pool_input_sha256",
            ) != before_pool_sha:
                failures.append(
                    "repair manifest has stale before_candidate_pool_sha256"
                )
            if manifest_hash_value(
                manifest,
                "after_candidate_pool_sha256",
                "candidate_pool_output_sha256",
            ) != after_pool_sha:
                failures.append(
                    "repair manifest has stale after_candidate_pool_sha256"
                )
            before_pool_rows = read_jsonl(before_pool_path)
            after_pool_rows = read_jsonl(after_pool_path)

            def pool_map(
                values: list[dict[str, Any]],
            ) -> dict[int | str, dict[str, Any]]:
                result: dict[int | str, dict[str, Any]] = {}
                for value in values:
                    identity = (
                        str(value.get("visual_unit_id", "")).strip()
                        if semantic_repair_mode
                        else int(value.get("cue_id") or value.get("line_id"))
                    )
                    if identity in (None, ""):
                        raise ValueError("candidate pool row lacks identity")
                    if identity in result:
                        raise ValueError(
                            f"candidate pool duplicates identity {identity}"
                        )
                    result[identity] = value
                return result

            try:
                before_pool = pool_map(before_pool_rows)
                after_pool = pool_map(after_pool_rows)
            except (TypeError, ValueError) as exc:
                failures.append(f"candidate pool diff is invalid: {exc}")
                before_pool = {}
                after_pool = {}
            if semantic_repair_mode:
                binding_failures, pool_binding_metrics = semantic_candidate_pool_failures(
                    root,
                    after_rows,
                    after_pool_rows,
                    normal_min_candidates=int(check.get("min_pool_candidates", 8)),
                    normal_max_candidates=int(
                        check.get("normal_pool_max_candidates", 12)
                    ),
                    risk_max_candidates=int(check.get("risk_pool_max_candidates", 32)),
                    require_evidence=bool(
                        check.get("require_candidate_pool_evidence", False)
                    ),
                )
            else:
                binding_failures, pool_binding_metrics = candidate_pool_quality_failures(
                    root,
                    after_rows,
                    after_pool_rows,
                    min_candidates=int(check.get("min_pool_candidates", 3)),
                    preferred_candidates=int(
                        check.get(
                            "preferred_pool_candidates",
                            check.get("min_pool_candidates", 3),
                        )
                    ),
                    require_evidence=bool(
                        check.get("require_candidate_pool_evidence", False)
                    ),
                    require_shortfall_evidence=bool(
                        check.get("require_candidate_shortfall_evidence", False)
                    ),
                    normal_max_candidates=(
                        int(check["normal_pool_max_candidates"])
                        if check.get("normal_pool_max_candidates") is not None
                        else None
                    ),
                    risk_max_candidates=(
                        int(check["risk_pool_max_candidates"])
                        if check.get("risk_pool_max_candidates") is not None
                        else None
                    ),
                )
            failures.extend(
                f"repaired candidate pool: {failure}"
                for failure in binding_failures
            )
            if check.get("require_source_manifest_binding", False):
                source_manifest_path = (
                    resolve_path(root, check["source_manifest_path"])
                    if check.get("source_manifest_path")
                    else None
                )
                if (
                    source_manifest_path is None
                    or not source_manifest_path.is_file()
                ):
                    failures.append(
                        "repair source binding requires source_manifest_path"
                    )
                else:
                    (
                        source_failures,
                        repair_source_binding_metrics,
                    ) = candidate_source_manifest_failures(
                        root,
                        after_pool_rows,
                        source_manifest_path,
                    )
                    failures.extend(
                        f"repaired candidate pool: {failure}"
                        for failure in source_failures
                    )
                    source_manifest_sha = file_sha256(
                        source_manifest_path
                    )
                    if manifest_hash_value(
                        manifest,
                        "source_manifest_sha256",
                        "source_identity_manifest_sha256",
                    ) != source_manifest_sha:
                        failures.append(
                            "repair manifest has stale source_manifest_sha256"
                        )
            if set(before_pool) != set(after_pool):
                failures.append(
                    "repair may not add, remove, or renumber candidate-pool rows"
                )
            actual_pool_changed = sorted(
                identity
                for identity in set(before_pool) & set(after_pool)
                if before_pool[identity] != after_pool[identity]
            )
            if semantic_repair_mode:
                declared_changed_units = sorted(
                    {
                        str(value).strip()
                        for value in manifest.get("changed_visual_unit_ids", [])
                        if str(value).strip()
                    }
                )
                if actual_pool_changed != declared_changed_units:
                    failures.append(
                        "semantic candidate-pool changed units mismatch: "
                        f"actual={actual_pool_changed}, "
                        f"declared={declared_changed_units}"
                    )
                unit_cues = {
                    str(entry.get("visual_unit_id", "")).strip(): {
                        int(value) for value in entry.get("cue_ids", [])
                    }
                    for entry in after_pool_rows
                    if isinstance(entry, dict)
                }
                changed_pool_cues = set().union(
                    *(unit_cues.get(str(unit_id), set()) for unit_id in actual_pool_changed)
                ) if actual_pool_changed else set()
                if changed_pool_cues and not (
                    changed_pool_cues & set(declared_changed)
                ):
                    failures.append(
                        "semantic pool changed without any declared cue in that unit"
                    )
            elif not set(actual_pool_changed).issubset(set(declared_changed)):
                failures.append(
                    "candidate pool changed outside declared cues="
                    f"{sorted(set(actual_pool_changed) - set(declared_changed))}"
                )
            for identity in set(before_pool) & set(after_pool):
                before_ids = {
                    str(item.get("candidate_id"))
                    for item in before_pool[identity].get("candidates", [])
                    if isinstance(item, dict) and item.get("candidate_id")
                }
                after_ids = {
                    str(item.get("candidate_id"))
                    for item in after_pool[identity].get("candidates", [])
                    if isinstance(item, dict) and item.get("candidate_id")
                }
                added_candidate_ids.extend(sorted(after_ids - before_ids))
            declared_added_ids = sorted(
                str(item) for item in manifest.get("added_candidate_ids", [])
            )
            if sorted(added_candidate_ids) != declared_added_ids:
                failures.append(
                    "repair added-candidate set mismatch: actual="
                    f"{sorted(added_candidate_ids)}, declared={declared_added_ids}"
                )
        if str(manifest.get("status", "")).upper() != "PASS":
            failures.append("repair manifest status must be PASS")
        if check.get("require_repair_sequence_gates", False):
            for section_name in ("opening_review", "ending_review"):
                section = manifest.get(section_name)
                if (
                    not isinstance(section, dict)
                    or str(section.get("status", "")).upper() != "PASS"
                ):
                    failures.append(
                        f"repair manifest lacks PASS {section_name}"
                    )
        unresolved_after_raw = manifest.get("unresolved_after", [])
        unresolved_after: list[int] = []
        for item in (
            unresolved_after_raw
            if isinstance(unresolved_after_raw, list)
            else []
        ):
            try:
                unresolved_after.append(int(item))
            except (TypeError, ValueError):
                failures.append(f"invalid unresolved_after cue={item!r}")
        unresolved_after = sorted(set(unresolved_after))
        if unresolved_after:
            failures.append(f"repair leaves unresolved cues={unresolved_after}")
        review_unresolved: list[int] = []
        if check.get("review_manifest_path"):
            review_path = resolve_path(root, check["review_manifest_path"])
            if not review_path.is_file():
                failures.append(f"missing input review manifest={review_path}")
            else:
                if manifest_hash_value(
                    manifest,
                    "review_manifest_sha256",
                    "input_review_sha256",
                ) != file_sha256(review_path):
                    failures.append("repair manifest has stale review hash")
                review = json.loads(review_path.read_text(encoding="utf-8"))
                review_status = str(review.get("status", "")).upper()
                if review_status not in {"PASS", "NEEDS_REPAIR"}:
                    failures.append(
                        "input review status must be PASS or NEEDS_REPAIR"
                    )
                review_match_sha = manifest_hash_value(
                    review,
                    "match_sheet_sha256",
                    "final_match_sheet_sha256",
                )
                if review_match_sha != before_sha:
                    failures.append(
                        "input review is not bound to before match sheet"
                    )
                if manifest_hash_value(
                    review,
                    "candidate_pool_sha256",
                    "candidate_pool.sha256",
                ) != before_pool_sha:
                    failures.append(
                        "input review is not bound to before candidate pool"
                    )
                if check.get(
                    "require_source_manifest_binding", False
                ):
                    bound_source_manifest = resolve_path(
                        root, check["source_manifest_path"]
                    )
                    if manifest_hash_value(
                        review,
                        "source_manifest_sha256",
                        "source_identity_manifest_sha256",
                    ) != file_sha256(bound_source_manifest):
                        failures.append(
                            "input review is not bound to source manifest"
                        )
                review_unresolved_raw = review.get("unresolved_cue_ids")
                if review_unresolved_raw is None:
                    review_unresolved_raw = review.get("unresolved_ids", [])
                for item in (
                    review_unresolved_raw
                    if isinstance(review_unresolved_raw, list)
                    else []
                ):
                    raw_id = (
                        item.get("cue_id")
                        if isinstance(item, dict)
                        else item
                    )
                    try:
                        review_unresolved.append(int(raw_id))
                    except (TypeError, ValueError):
                        failures.append(
                            f"input review has invalid unresolved cue={raw_id!r}"
                        )
                review_unresolved = sorted(set(review_unresolved))
                omitted_repairs = sorted(
                    set(review_unresolved) - set(declared_changed)
                )
                if omitted_repairs:
                    failures.append(
                        "repair did not cover input-review unresolved cues="
                        f"{omitted_repairs}"
                    )
                newly_unresolved: list[int] = []
                for item in manifest.get("newly_unresolved", []):
                    try:
                        newly_unresolved.append(int(item))
                    except (TypeError, ValueError):
                        failures.append(
                            f"invalid newly_unresolved cue={item!r}"
                        )
                derived_unresolved_after = sorted(
                    (
                        set(review_unresolved) - set(declared_changed)
                    )
                    | set(newly_unresolved)
                )
                if unresolved_after != derived_unresolved_after:
                    failures.append(
                        "unresolved_after is not derived from the bound review: "
                        f"declared={unresolved_after}, "
                        f"derived={derived_unresolved_after}"
                    )

        plan_metrics: dict[str, Any] = {}
        if check.get("canonical_srt_path"):
            canonical_srt_path = resolve_path(root, check["canonical_srt_path"])
            if not canonical_srt_path.is_file():
                failures.append(f"missing canonical SRT={canonical_srt_path}")
            else:
                plan_failures, plan_metrics, _ = _match_plan_failures(
                    root,
                    after_path,
                    canonical_srt_path,
                    min_candidates=int(check.get("min_candidates", 3)),
                    max_reuse=(
                        int(check["max_reuse"])
                        if check.get("max_reuse") is not None
                        else None
                    ),
                    timing_tolerance_ms=float(
                        check.get("timing_tolerance_ms", 2)
                    ),
                    require_candidate_evidence=bool(
                        check.get("require_candidate_evidence", False)
                    ),
                    required_qa_status=None,
                    require_candidate_ids=bool(
                        check.get("require_candidate_ids", False)
                    ),
                    require_semantic_visual_units=bool(
                        check.get("require_semantic_visual_units", False)
                    ),
                    min_semantic_unit_duration_seconds=float(
                        check.get("min_semantic_unit_duration_seconds", 4)
                    ),
                    max_semantic_unit_duration_seconds=float(
                        check.get("max_semantic_unit_duration_seconds", 8)
                    ),
                )
                failures.extend(
                    f"repaired match plan: {failure}"
                    for failure in plan_failures
                )
        metrics = {
            "status": str(manifest.get("status", "")).upper(),
            "actual_changed_cue_ids": actual_changed,
            "declared_changed_cue_ids": declared_changed,
            "before_match_sheet_sha256": before_sha,
            "after_match_sheet_sha256": after_sha,
            "before_candidate_pool_sha256": before_pool_sha,
            "after_candidate_pool_sha256": after_pool_sha,
            "actual_pool_changed_cue_ids": actual_pool_changed,
            "added_candidate_ids": sorted(added_candidate_ids),
            "candidate_pool_binding": pool_binding_metrics,
            "source_binding": repair_source_binding_metrics,
            "unresolved_after": unresolved_after,
            "input_review_unresolved": review_unresolved,
            "workflow_ready": not unresolved_after and not failures,
            "match_plan": plan_metrics,
            "repair_manifest_sha256": file_sha256(path),
            "failures": failures,
        }
        return (
            not failures,
            f"changed={actual_changed}, unresolved={unresolved_after}, failures={failures}",
            metrics,
        )

    if check_type == "picture_master_integrity":
        required_config = [
            field
            for field in (
                "manifest_path",
                "match_sheet_path",
                "approval_path",
                "timing_contract_path",
            )
            if field not in check
        ]
        if check.get("render_unit_mode") == SEMANTIC_VISUAL_UNIT_GRANULARITY:
            required_config.extend(
                field
                for field in (
                    "aesthetic_proxy_approval_path",
                    "composition_path",
                    "render_plan_path",
                )
                if not check.get(field)
            )
        if required_config:
            return False, f"check config missing {required_config}", {
                "config_missing": required_config
            }
        manifest_path = resolve_path(root, check["manifest_path"])
        match_sheet_path = resolve_path(root, check["match_sheet_path"])
        approval_path = resolve_path(root, check["approval_path"])
        timing_contract_path = resolve_path(root, check["timing_contract_path"])
        composition_path = (
            resolve_path(root, check["composition_path"])
            if check.get("composition_path")
            else None
        )
        render_plan_path = (
            resolve_path(root, check["render_plan_path"])
            if check.get("render_plan_path")
            else None
        )
        failures: list[str] = []
        for label, candidate in (
            ("manifest_path", manifest_path),
            ("match_sheet_path", match_sheet_path),
            ("approval_path", approval_path),
            ("timing_contract_path", timing_contract_path),
        ):
            if not candidate.is_file():
                failures.append(f"{label} is missing: {candidate}")
        for label, candidate in (
            ("composition_path", composition_path),
            ("render_plan_path", render_plan_path),
        ):
            if candidate is not None and not candidate.is_file():
                failures.append(f"{label} is missing: {candidate}")
        if failures:
            return False, f"failures={failures}", {"failures": failures}
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
        media_failures, media_metrics = _media_contract(
            path,
            timing_contract_path,
            frame_tolerance=int(check.get("frame_tolerance", 0)),
            fps_tolerance=float(check.get("fps_tolerance", 0.02)),
        )
        failures.extend(media_failures)
        picture_sha = media_metrics["sha256"]
        match_sha = file_sha256(match_sheet_path)
        approval_sha = file_sha256(approval_path)
        timing_sha = file_sha256(timing_contract_path)
        composition_sha = (
            file_sha256(composition_path)
            if composition_path is not None and composition_path.is_file()
            else ""
        )
        render_plan_sha = (
            file_sha256(render_plan_path)
            if render_plan_path is not None and render_plan_path.is_file()
            else ""
        )
        aesthetic_approval_path = (
            resolve_path(root, check["aesthetic_proxy_approval_path"])
            if check.get("aesthetic_proxy_approval_path")
            else None
        )
        aesthetic_approval_sha = ""
        if aesthetic_approval_path is not None:
            if not aesthetic_approval_path.is_file():
                failures.append(
                    f"aesthetic_proxy_approval_path is missing: {aesthetic_approval_path}"
                )
            else:
                aesthetic_approval = json.loads(
                    aesthetic_approval_path.read_text(encoding="utf-8")
                )
                aesthetic_approval_sha = file_sha256(aesthetic_approval_path)
                if str(aesthetic_approval.get("status", "")).upper() != "PASS":
                    failures.append("aesthetic proxy approval status must be PASS")
                if manifest_hash_value(
                    aesthetic_approval, "match_sheet_sha256", "match_sheet.sha256"
                ) != match_sha:
                    failures.append(
                        "aesthetic proxy approval is not bound to the current match sheet"
                    )
                if manifest_hash_value(
                    manifest,
                    "aesthetic_proxy_approval_sha256",
                    "aesthetic_proxy_approval.sha256",
                ) != aesthetic_approval_sha:
                    failures.append(
                        "picture render manifest has stale aesthetic approval SHA"
                    )
                for label, actual_hash, fields in (
                    (
                        "composition",
                        composition_sha,
                        ("composition_sha256", "composition.sha256"),
                    ),
                    (
                        "render plan",
                        render_plan_sha,
                        ("render_plan_sha256", "render_plan.sha256"),
                    ),
                ):
                    if not actual_hash or manifest_hash_value(
                        aesthetic_approval, *fields
                    ) != actual_hash:
                        failures.append(
                            f"aesthetic approval has stale HyperFrames {label} SHA"
                        )
                    if not actual_hash or manifest_hash_value(
                        manifest, *fields
                    ) != actual_hash:
                        failures.append(
                            f"picture render manifest has stale HyperFrames {label} SHA"
                        )
        if str(manifest.get("status", "")).upper() != "PASS":
            failures.append("picture render manifest status must be PASS")
        if manifest_hash_value(
            manifest,
            "picture_master_sha256",
            "output.sha256",
            "picture_master.sha256",
        ) != picture_sha:
            failures.append("picture render manifest has stale output SHA")
        if manifest_hash_value(
            manifest, "match_sheet_sha256", "match_sheet.sha256"
        ) != match_sha:
            failures.append("picture render manifest has stale match sheet SHA")
        if manifest_hash_value(
            manifest,
            "approval_sha256",
            "review_manifest_sha256",
            "repair_manifest_sha256",
        ) != approval_sha:
            failures.append("picture render manifest has stale approval SHA")
        if manifest_hash_value(
            manifest, "timing_contract_sha256", "timing_contract.sha256"
        ) != timing_sha:
            failures.append("picture render manifest has stale timing contract SHA")
        _, match_rows = read_tsv(match_sheet_path)
        manifest_cues = manifest.get("cue_count", manifest.get("row_count", -1))
        if int(manifest_cues) != len(match_rows):
            failures.append("picture render manifest cue count mismatch")
        if manifest.get("all_match_rows_rendered") is not True:
            failures.append("picture render manifest must prove all rows rendered")
        segment_manifest_path = (
            resolve_path(root, check["segment_manifest_path"])
            if check.get("segment_manifest_path")
            else None
        )
        segment_manifest_sha = ""
        segment_rows_count = 0
        segment_boundary_frames: list[int] = []
        if segment_manifest_path is not None:
            if not segment_manifest_path.is_file():
                failures.append(
                    f"picture segment manifest is missing={segment_manifest_path}"
                )
            else:
                segment_manifest_sha = file_sha256(segment_manifest_path)
                if manifest_hash_value(
                    manifest,
                    "segment_manifest_sha256",
                    "render_manifest_sha256",
                ) != segment_manifest_sha:
                    failures.append(
                        "picture render manifest has stale segment_manifest_sha256"
                    )
                segment_fields, segment_rows = read_tsv(segment_manifest_path)
                segment_rows_count = len(segment_rows)
                semantic_unit_mode = (
                    check.get("render_unit_mode") == "semantic_visual_units_v2"
                )
                required_segment_fields = {
                    "visual_unit_id" if semantic_unit_mode else "line_id",
                    "output_start_frame",
                    "output_end_frame",
                    "source_file",
                    "source_in",
                    "source_out",
                }
                missing_segment_fields = sorted(
                    required_segment_fields - set(segment_fields)
                )
                if missing_segment_fields:
                    failures.append(
                        f"segment manifest missing columns={missing_segment_fields}"
                    )
                if semantic_unit_mode:
                    match_by_id: dict[str | int, dict[str, str]] = {}
                    for row in match_rows:
                        identity = row.get("visual_unit_id", "").strip()
                        if not identity:
                            failures.append("match sheet row has empty visual_unit_id")
                            continue
                        match_by_id.setdefault(identity, row)
                else:
                    match_by_id = {
                        identity: row
                        for index, row in enumerate(match_rows, start=1)
                        if (identity := cue_id(row, index)) is not None
                    }
                segment_by_id: dict[str | int, dict[str, str]] = {}
                spans: list[tuple[int, int, str | int]] = []
                timing_contract = json.loads(
                    timing_contract_path.read_text(encoding="utf-8")
                )
                target_frames = int(timing_contract["target_frame_count"])
                target_fps = float(timing_contract["fps"])
                ordered_match_ids = list(match_by_id)
                expected_output_spans: dict[str | int, tuple[int, int]] = {}
                for position, identity in enumerate(ordered_match_ids):
                    row = match_by_id[identity]
                    explicit_start = (
                        row.get("visual_start_frame")
                        or row.get("output_start_frame")
                    )
                    explicit_end = (
                        row.get("visual_end_frame")
                        or row.get("output_end_frame")
                    )
                    if explicit_start not in (None, "") and explicit_end not in (
                        None,
                        "",
                    ):
                        expected_output_spans[identity] = (
                            int(explicit_start),
                            int(explicit_end),
                        )
                        continue
                    start_frame = (
                        0
                        if position == 0
                        else 0
                    )
                    if position > 0:
                        current_range = caption_range(row)
                        if current_range is None:
                            failures.append(
                                f"cue {identity}: caption range is invalid"
                            )
                        else:
                            start_frame = round(current_range[0] * target_fps)
                    if position + 1 < len(ordered_match_ids):
                        next_row = match_by_id[ordered_match_ids[position + 1]]
                        next_range = caption_range(next_row)
                        if next_range is None:
                            failures.append(
                                f"cue {identity}: next cue caption range is invalid"
                            )
                            end_frame = start_frame
                        else:
                            end_frame = round(next_range[0] * target_fps)
                    else:
                        end_frame = target_frames
                    expected_output_spans[identity] = (
                        start_frame,
                        end_frame,
                    )
                for index, segment in enumerate(segment_rows, start=1):
                    identity = (
                        segment.get("visual_unit_id", "").strip()
                        if semantic_unit_mode
                        else cue_id(segment, index)
                    )
                    if identity in (None, ""):
                        failures.append(
                            f"segment row {index}: invalid "
                            f"{'visual_unit_id' if semantic_unit_mode else 'line_id'}"
                        )
                        continue
                    if identity in segment_by_id:
                        failures.append(
                            f"segment manifest duplicates cue {identity}"
                        )
                    segment_by_id[identity] = segment
                    try:
                        start_frame = int(segment["output_start_frame"])
                        end_frame = int(segment["output_end_frame"])
                        if start_frame < 0 or end_frame <= start_frame:
                            raise ValueError
                        spans.append((start_frame, end_frame, identity))
                        expected_span = expected_output_spans.get(identity)
                        if expected_span and (
                            start_frame,
                            end_frame,
                        ) != expected_span:
                            failures.append(
                                f"cue {identity}: segment output span "
                                f"{start_frame}-{end_frame} differs from "
                                f"expected {expected_span[0]}-{expected_span[1]}"
                            )
                    except (KeyError, ValueError):
                        failures.append(
                            f"cue {identity}: invalid output frame span"
                        )
                    selected = match_by_id.get(identity)
                    if selected is not None:
                        if (
                            Path(segment.get("source_file", "")).expanduser().resolve()
                            != Path(selected.get("source_file", "")).expanduser().resolve()
                        ):
                            failures.append(
                                f"cue {identity}: segment source differs from match sheet"
                            )
                        try:
                            if (
                                abs(
                                    float(segment.get("source_in", ""))
                                    - float(selected.get("source_in", ""))
                                )
                                > 0.002
                                or abs(
                                    float(segment.get("source_out", ""))
                                    - float(selected.get("source_out", ""))
                                )
                                > 0.022
                            ):
                                failures.append(
                                    f"cue {identity}: segment source range differs "
                                    "from match sheet"
                                )
                        except ValueError:
                            failures.append(
                                f"cue {identity}: invalid segment source range"
                            )
                if set(segment_by_id) != set(match_by_id):
                    failures.append(
                        "segment coverage missing="
                        f"{sorted(set(match_by_id) - set(segment_by_id))}, "
                        f"extra={sorted(set(segment_by_id) - set(match_by_id))}"
                    )
                if semantic_unit_mode:
                    manifest_unit_count = int(manifest.get("visual_unit_count", -1))
                    if manifest_unit_count != len(match_by_id):
                        failures.append(
                            "picture render manifest visual_unit_count mismatch"
                        )
                spans.sort()
                segment_boundary_frames = [start for start, _, _ in spans[1:]]
                expected_frame = 0
                for start_frame, end_frame, identity in spans:
                    if start_frame != expected_frame:
                        failures.append(
                            f"cue {identity}: segment frame coverage jumps "
                            f"from {expected_frame} to {start_frame}"
                        )
                    expected_frame = end_frame
                if expected_frame != target_frames:
                    failures.append(
                        f"segment frame coverage ends at {expected_frame}, "
                        f"expected {target_frames}"
                    )
        elif check.get("require_segment_manifest", False):
            failures.append("picture master requires segment_manifest_path")
        approval_status = str(approval.get("status", "")).upper()
        unresolved = (
            approval.get("unresolved_after")
            if "unresolved_after" in approval
            else approval.get("unresolved_cue_ids", [])
        )
        if approval_status != "PASS" or unresolved:
            failures.append(
                f"picture render approval is not workflow-ready: status={approval_status}, unresolved={unresolved}"
            )
        approval_match_sha = manifest_hash_value(
            approval,
            "match_sheet_sha256",
            "final_match_sheet_sha256",
            "after_match_sheet_sha256",
            "output_match_sheet_sha256",
        )
        if approval_match_sha != match_sha:
            failures.append(
                "picture render approval is not bound to the current match sheet"
            )
        if check.get("require_approval_sequence_gates", False):
            for section_name in ("opening_review", "ending_review"):
                section = approval.get(section_name)
                if (
                    not isinstance(section, dict)
                    or str(section.get("status", "")).upper() != "PASS"
                ):
                    failures.append(
                        f"picture render approval lacks PASS {section_name}"
                    )
        black_events: list[str] = []
        if check.get("check_black_frames", True):
            try:
                black_events = _black_events(
                    path,
                    duration=float(check.get("black_duration", 0.05)),
                    pixel_threshold=float(check.get("black_pixel_threshold", 0.02)),
                )
            except RuntimeError as exc:
                failures.append(str(exc))
            if black_events:
                failures.append(f"black frame events={black_events[:20]}")
        full_decode_pass = None
        if check.get("check_full_decode", False):
            full_decode_pass, decode_detail = full_decode_once(path)
            if not full_decode_pass:
                failures.append(f"picture full decode failed: {decode_detail}")
        seam_black: list[int] = []
        seam_observed = 0
        if check.get("check_transition_seams", False):
            try:
                seam_black, seam_observed = seam_black_frames(
                    path,
                    segment_boundary_frames,
                    total_frames=int(media_metrics["frames"]),
                    amount=float(check.get("seam_black_amount", 99)),
                    threshold=int(check.get("seam_black_threshold", 16)),
                )
            except (RuntimeError, ValueError) as exc:
                failures.append(str(exc))
            if seam_black:
                failures.append(f"black seam frames={seam_black[:20]}")
        metrics = {
            **media_metrics,
            "cue_count": len(match_rows),
            "match_sheet_sha256": match_sha,
            "approval_sha256": approval_sha,
            "render_manifest_sha256": file_sha256(manifest_path),
            "segment_manifest_sha256": segment_manifest_sha,
            "segment_rows": segment_rows_count,
            "black_events": black_events,
            "full_decode_pass": full_decode_pass,
            "seam_black_frames": seam_black,
            "seam_frames_observed": seam_observed,
            "aesthetic_proxy_approval_sha256": aesthetic_approval_sha,
            "composition_sha256": composition_sha,
            "render_plan_sha256": render_plan_sha,
            "failures": failures,
        }
        return (
            not failures,
            (
                f"frames={media_metrics['frames']}, cues={len(match_rows)}, "
                f"black_events={len(black_events)}, failures={failures}"
            ),
            metrics,
        )

    if check_type == "picture_patch_integrity":
        required_config = [
            field
            for field in (
                "before_match_sheet_path",
                "after_match_sheet_path",
                "timing_contract_path",
                "repair_approval_path",
                "base_approval_path",
            )
            if field not in check
        ]
        if required_config:
            return False, f"check config missing {required_config}", {
                "config_missing": required_config
            }
        manifest = json.loads(path.read_text(encoding="utf-8"))
        before_path = resolve_path(root, check["before_match_sheet_path"])
        after_path = resolve_path(root, check["after_match_sheet_path"])
        timing_contract_path = resolve_path(root, check["timing_contract_path"])
        repair_approval_path = resolve_path(
            root, check["repair_approval_path"]
        )
        base_approval_path = resolve_path(root, check["base_approval_path"])
        base_path = resolved_existing_file(
            root,
            check.get("base_picture_path")
            or manifest.get("base_picture", {}).get("path", ""),
        )
        output_path = resolved_existing_file(
            root,
            check.get("output_picture_path")
            or manifest.get("output_picture", {}).get("path", ""),
        )
        failures: list[str] = []
        for label, candidate in (
            ("before_match_sheet_path", before_path),
            ("after_match_sheet_path", after_path),
            ("timing_contract_path", timing_contract_path),
            ("repair_approval_path", repair_approval_path),
            ("base_approval_path", base_approval_path),
        ):
            if not candidate.is_file():
                failures.append(f"{label} is missing: {candidate}")
        if base_path is None:
            failures.append("base picture is missing")
        if output_path is None:
            failures.append("output picture is missing")
        if failures:
            return False, f"failures={failures}", {"failures": failures}
        assert base_path is not None and output_path is not None
        _, before_rows = read_tsv(before_path)
        _, after_rows = read_tsv(after_path)
        before_by_id = {
            identity: row
            for index, row in enumerate(before_rows, start=1)
            if (identity := cue_id(row, index)) is not None
        }
        after_by_id = {
            identity: row
            for index, row in enumerate(after_rows, start=1)
            if (identity := cue_id(row, index)) is not None
        }
        if set(before_by_id) != set(after_by_id):
            failures.append("picture patch may not add, remove, or renumber rows")
        protected_fields = {
            "line_id",
            "text",
            "caption_start",
            "caption_end",
            "start",
            "end",
            "duration",
        }
        protected_changes: list[str] = []
        for identity in sorted(set(before_by_id) & set(after_by_id)):
            for field in protected_fields:
                if before_by_id[identity].get(field, "") != after_by_id[
                    identity
                ].get(field, ""):
                    protected_changes.append(f"{identity}:{field}")
        if protected_changes:
            failures.append(
                "picture patch changed protected caption fields="
                f"{protected_changes[:20]}"
            )
        actual_changed = sorted(
            identity
            for identity in set(before_by_id) & set(after_by_id)
            if tsv_rows_differ(
                before_by_id[identity], after_by_id[identity]
            )
        )
        declared_changed: list[int] = []
        for item in manifest.get("changed_cue_ids", []):
            try:
                declared_changed.append(int(item))
            except (TypeError, ValueError):
                failures.append(f"invalid changed cue ID={item!r}")
        declared_changed = sorted(set(declared_changed))
        if actual_changed != declared_changed:
            failures.append(
                f"hidden picture patch rows: actual={actual_changed}, declared={declared_changed}"
            )
        corrections = manifest.get("corrections", [])
        correction_ids = sorted(
            {
                int(item.get("cue_id"))
                for item in corrections
                if isinstance(item, dict)
                and str(item.get("cue_id", "")).isdigit()
            }
        )
        if correction_ids != declared_changed:
            failures.append("patch corrections must exactly match changed_cue_ids")
        for item in corrections:
            if not isinstance(item, dict):
                continue
            identity = item.get("cue_id")
            if not str(item.get("reason", "")).strip():
                failures.append(f"cue {identity}: patch reason missing")
            if check.get("require_patch_evidence", True) and resolved_existing_file(
                root, item.get("evidence") or item.get("evidence_path")
            ) is None:
                failures.append(f"cue {identity}: patch evidence missing")

        base_sha = file_sha256(base_path)
        output_sha = file_sha256(output_path)
        before_sha = file_sha256(before_path)
        after_sha = file_sha256(after_path)
        expected_base_sha = manifest_hash_value(
            manifest, "base_picture.sha256", "base_picture_sha256"
        )
        expected_output_sha = manifest_hash_value(
            manifest, "output_picture.sha256", "output_picture_sha256"
        )
        if expected_base_sha != base_sha:
            failures.append("patch manifest has stale base picture SHA")
        if expected_output_sha != output_sha:
            failures.append("patch manifest has stale output picture SHA")
        if manifest_hash_value(
            manifest, "before_match_sheet_sha256", "pre_match_sheet_sha256"
        ) != before_sha:
            failures.append("patch manifest has stale before match sheet SHA")
        if manifest_hash_value(
            manifest, "after_match_sheet_sha256", "post_match_sheet_sha256"
        ) != after_sha:
            failures.append("patch manifest has stale after match sheet SHA")
        if base_sha == output_sha:
            failures.append("picture patch output is identical to base picture")
        if str(manifest.get("status", "")).upper() != "PASS":
            failures.append("picture patch manifest status must be PASS")

        repair_approval = json.loads(
            repair_approval_path.read_text(encoding="utf-8")
        )
        base_approval = json.loads(
            base_approval_path.read_text(encoding="utf-8")
        )
        repair_approval_sha = file_sha256(repair_approval_path)
        base_approval_sha = file_sha256(base_approval_path)
        if manifest_hash_value(
            manifest,
            "repair_approval_sha256",
            "repair_manifest_sha256",
        ) != repair_approval_sha:
            failures.append("patch manifest has stale repair approval SHA")
        if manifest_hash_value(
            manifest,
            "base_approval_sha256",
            "base_render_manifest_sha256",
            "base_patch_manifest_sha256",
        ) != base_approval_sha:
            failures.append("patch manifest has stale base approval SHA")
        if (
            str(repair_approval.get("status", "")).upper() != "PASS"
            or repair_approval.get("unresolved_after", [])
        ):
            failures.append("patch repair approval is not workflow-ready")
        for section_name in ("opening_review", "ending_review"):
            section = repair_approval.get(section_name)
            if (
                not isinstance(section, dict)
                or str(section.get("status", "")).upper() != "PASS"
            ):
                failures.append(
                    f"patch repair approval lacks PASS {section_name}"
                )
        if manifest_hash_value(
            repair_approval,
            "before_match_sheet_sha256",
            "input_match_sheet_sha256",
        ) != before_sha:
            failures.append(
                "patch repair approval is not bound to before match sheet"
            )
        if manifest_hash_value(
            repair_approval,
            "after_match_sheet_sha256",
            "output_match_sheet_sha256",
        ) != after_sha:
            failures.append(
                "patch repair approval is not bound to after match sheet"
            )
        if str(base_approval.get("status", "")).upper() != "PASS":
            failures.append("patch base approval status must be PASS")
        base_approved_picture_sha = manifest_hash_value(
            base_approval,
            "picture_master_sha256",
            "output.sha256",
            "picture_master.sha256",
            "output_picture.sha256",
            "output_picture_sha256",
        )
        if base_approved_picture_sha != base_sha:
            failures.append(
                "patch base picture is not the approved prior output"
            )
        base_approved_match_sha = manifest_hash_value(
            base_approval,
            "match_sheet_sha256",
            "match_sheet.sha256",
            "after_match_sheet_sha256",
            "output_match_sheet_sha256",
        )
        if base_approved_match_sha != before_sha:
            failures.append(
                "patch base approval is not bound to before match sheet"
            )

        chunk_scoped_mode = (
            check.get("patch_verification_mode") == "chunk_scoped_v2"
        )
        base_segments_path = None if chunk_scoped_mode else (
            resolve_path(root, check["base_segment_manifest_path"])
            if check.get("base_segment_manifest_path")
            else resolved_existing_file(
                root,
                manifest.get("base_segment_manifest", {}).get("path", ""),
            )
        )
        output_segments_path = None if chunk_scoped_mode else (
            resolve_path(root, check["output_segment_manifest_path"])
            if check.get("output_segment_manifest_path")
            else resolved_existing_file(
                root,
                manifest.get("output_segment_manifest", {}).get("path", ""),
            )
        )
        segment_metrics: dict[str, Any] = {}
        if check.get("require_segment_manifests", True):
            if not isinstance(base_segments_path, Path) or not base_segments_path.is_file():
                failures.append("base segment manifest is required")
            if not isinstance(output_segments_path, Path) or not output_segments_path.is_file():
                failures.append("output segment manifest is required")
        if (
            isinstance(base_segments_path, Path)
            and base_segments_path.is_file()
            and isinstance(output_segments_path, Path)
            and output_segments_path.is_file()
        ):
            _, base_segments = read_tsv(base_segments_path)
            _, output_segments = read_tsv(output_segments_path)
            base_segment_manifest_sha = file_sha256(base_segments_path)
            output_segment_manifest_sha = file_sha256(output_segments_path)
            if manifest_hash_value(
                manifest,
                "base_segment_manifest_sha256",
                "base_segment_manifest.sha256",
            ) != base_segment_manifest_sha:
                failures.append(
                    "patch manifest has stale base segment-manifest SHA"
                )
            if manifest_hash_value(
                manifest,
                "output_segment_manifest_sha256",
                "output_segment_manifest.sha256",
            ) != output_segment_manifest_sha:
                failures.append(
                    "patch manifest has stale output segment-manifest SHA"
                )
            verify_decoded_segments = bool(
                check.get("verify_decoded_segment_hashes", False)
            )

            def segment_map(
                rows: list[dict[str, str]], label: str
            ) -> dict[int, dict[str, Any]]:
                result: dict[int, dict[str, Any]] = {}
                for index, row in enumerate(rows, start=1):
                    identity = cue_id(row, index)
                    digest = (
                        row.get("sha256", "")
                        or row.get("segment_sha256", "")
                    ).strip().lower()
                    if identity is not None:
                        if identity in result:
                            failures.append(
                                f"{label} segment manifest duplicates cue {identity}"
                            )
                        if not re.fullmatch(r"[0-9a-f]{64}", digest):
                            failures.append(
                                f"{label} segment manifest cue {identity} has "
                                "invalid SHA-256"
                            )
                        start_frame = None
                        end_frame = None
                        if verify_decoded_segments:
                            try:
                                start_frame = int(row["output_start_frame"])
                                end_frame = int(row["output_end_frame"])
                                if start_frame < 0 or end_frame <= start_frame:
                                    raise ValueError
                            except (KeyError, ValueError):
                                failures.append(
                                    f"{label} segment manifest cue {identity} "
                                    "has invalid output frame span"
                                )
                        result[identity] = {
                            "sha256": digest,
                            "output_start_frame": start_frame,
                            "output_end_frame": end_frame,
                        }
                return result

            base_segments_by_id = segment_map(base_segments, "base")
            output_segments_by_id = segment_map(output_segments, "output")
            if set(base_segments_by_id) != set(output_segments_by_id):
                failures.append("segment manifest cue coverage changed")
            secretly_changed_segments = sorted(
                identity
                for identity in set(base_segments_by_id)
                & set(output_segments_by_id)
                if identity not in declared_changed
                and base_segments_by_id[identity]["sha256"]
                != output_segments_by_id[identity]["sha256"]
            )
            unchanged_declared_segments = sorted(
                identity
                for identity in declared_changed
                if base_segments_by_id.get(identity, {}).get("sha256")
                == output_segments_by_id.get(identity, {}).get("sha256")
            )
            if secretly_changed_segments:
                failures.append(
                    f"unlisted segment changes={secretly_changed_segments}"
                )
            if unchanged_declared_segments:
                failures.append(
                    f"declared patched segments did not change={unchanged_declared_segments}"
                )
            decoded_secret_changes: list[int] = []
            decoded_unchanged_declared: list[int] = []
            if verify_decoded_segments:
                try:
                    base_frame_hashes = decoded_frame_hashes(base_path)
                    output_frame_hashes = decoded_frame_hashes(output_path)
                except RuntimeError as exc:
                    failures.append(str(exc))
                    base_frame_hashes = []
                    output_frame_hashes = []
                if base_frame_hashes and output_frame_hashes:
                    for identity in sorted(
                        set(base_segments_by_id) & set(output_segments_by_id)
                    ):
                        base_segment = base_segments_by_id[identity]
                        output_segment = output_segments_by_id[identity]
                        base_span = (
                            base_segment["output_start_frame"],
                            base_segment["output_end_frame"],
                        )
                        output_span = (
                            output_segment["output_start_frame"],
                            output_segment["output_end_frame"],
                        )
                        if base_span != output_span:
                            failures.append(
                                f"cue {identity}: patch changed output frame span "
                                f"{base_span}->{output_span}"
                            )
                            continue
                        try:
                            actual_base_digest = frame_slice_sha256(
                                base_frame_hashes, *base_span
                            )
                            actual_output_digest = frame_slice_sha256(
                                output_frame_hashes, *output_span
                            )
                        except (TypeError, ValueError) as exc:
                            failures.append(f"cue {identity}: {exc}")
                            continue
                        if base_segment["sha256"] != actual_base_digest:
                            failures.append(
                                f"cue {identity}: base segment SHA is not derived "
                                "from the base picture"
                            )
                        if output_segment["sha256"] != actual_output_digest:
                            failures.append(
                                f"cue {identity}: output segment SHA is not derived "
                                "from the output picture"
                            )
                        if identity not in declared_changed and (
                            actual_base_digest != actual_output_digest
                        ):
                            decoded_secret_changes.append(identity)
                        if identity in declared_changed and (
                            actual_base_digest == actual_output_digest
                        ):
                            decoded_unchanged_declared.append(identity)
                if decoded_secret_changes:
                    failures.append(
                        f"decoded unlisted segment changes={decoded_secret_changes}"
                    )
                if decoded_unchanged_declared:
                    failures.append(
                        "decoded declared segments did not change="
                        f"{decoded_unchanged_declared}"
                    )
            segment_metrics = {
                "base_segment_manifest_sha256": base_segment_manifest_sha,
                "output_segment_manifest_sha256": output_segment_manifest_sha,
                "secretly_changed_segments": secretly_changed_segments,
                "decoded_secret_changes": decoded_secret_changes
                if verify_decoded_segments
                else [],
            }

        chunk_metrics: dict[str, Any] = {}
        chunk_boundary_frames: list[int] = []
        if chunk_scoped_mode:
            chunk_manifest_path = (
                resolve_path(root, check["chunk_verification_manifest_path"])
                if check.get("chunk_verification_manifest_path")
                else None
            )
            if chunk_manifest_path is None or not chunk_manifest_path.is_file():
                failures.append("chunk_scoped_v2 requires chunk_verification_manifest_path")
            else:
                chunk_manifest = json.loads(
                    chunk_manifest_path.read_text(encoding="utf-8")
                )
                chunk_manifest_sha = file_sha256(chunk_manifest_path)
                if manifest_hash_value(
                    manifest,
                    "chunk_verification_manifest_sha256",
                    "chunk_verification_manifest.sha256",
                ) != chunk_manifest_sha:
                    failures.append(
                        "patch manifest has stale chunk-verification manifest SHA"
                    )
                if manifest_hash_value(
                    chunk_manifest, "base_picture_sha256", "base_picture.sha256"
                ) != base_sha:
                    failures.append("chunk verification has stale base picture SHA")
                if manifest_hash_value(
                    chunk_manifest, "output_picture_sha256", "output_picture.sha256"
                ) != output_sha:
                    failures.append("chunk verification has stale output picture SHA")
                if str(chunk_manifest.get("status", "")).upper() != "PASS":
                    failures.append("chunk verification manifest status must be PASS")
                chunks = chunk_manifest.get("chunks", [])
                if not isinstance(chunks, list) or not chunks:
                    failures.append("chunk verification manifest requires nonempty chunks")
                    chunks = []
                declared_changed_chunk_ids = {
                    str(value).strip()
                    for value in chunk_manifest.get("changed_chunk_ids", [])
                    if str(value).strip()
                }
                actual_changed_chunk_ids: set[str] = set()
                changed_chunk_cue_ids: set[int] = set()
                seen_chunk_ids: set[str] = set()
                spans: list[tuple[int, int, str]] = []
                unchanged_sha_count = 0
                changed_decoded_count = 0
                for index, entry in enumerate(chunks, start=1):
                    if not isinstance(entry, dict):
                        failures.append(f"chunk row {index} is not an object")
                        continue
                    chunk_id = str(entry.get("chunk_id", "")).strip()
                    state = str(entry.get("state", "")).strip().lower()
                    if not chunk_id or chunk_id in seen_chunk_ids:
                        failures.append(
                            f"chunk row {index} has missing/duplicate chunk_id"
                        )
                    seen_chunk_ids.add(chunk_id)
                    if state not in {"changed", "unchanged"}:
                        failures.append(f"chunk {chunk_id}: invalid state={state!r}")
                    if state == "changed":
                        actual_changed_chunk_ids.add(chunk_id)
                    try:
                        start_frame = int(entry["output_start_frame"])
                        end_frame = int(entry["output_end_frame"])
                        if start_frame < 0 or end_frame <= start_frame:
                            raise ValueError
                        spans.append((start_frame, end_frame, chunk_id))
                    except (KeyError, TypeError, ValueError):
                        failures.append(f"chunk {chunk_id}: invalid output frame span")
                        continue
                    base_chunk = resolved_existing_file(root, entry.get("base_chunk_path"))
                    output_chunk = resolved_existing_file(root, entry.get("output_chunk_path"))
                    if base_chunk is None or output_chunk is None:
                        failures.append(f"chunk {chunk_id}: base/output chunk file is missing")
                        continue
                    base_chunk_sha = file_sha256(base_chunk)
                    output_chunk_sha = file_sha256(output_chunk)
                    if str(entry.get("base_sha256", "")).lower() != base_chunk_sha:
                        failures.append(f"chunk {chunk_id}: stale base chunk SHA")
                    if str(entry.get("output_sha256", "")).lower() != output_chunk_sha:
                        failures.append(f"chunk {chunk_id}: stale output chunk SHA")
                    if state == "unchanged":
                        if check.get("verify_unchanged_chunk_sha256", True) and (
                            base_chunk_sha != output_chunk_sha
                        ):
                            failures.append(
                                f"chunk {chunk_id}: unchanged chunk SHA differs"
                            )
                        else:
                            unchanged_sha_count += 1
                    elif check.get("verify_changed_chunk_decoded_frames", True):
                        try:
                            base_decoded_sha, base_frames = decoded_frame_sequence_sha256(
                                base_chunk
                            )
                            output_decoded_sha, output_frames = decoded_frame_sequence_sha256(
                                output_chunk
                            )
                        except RuntimeError as exc:
                            failures.append(f"chunk {chunk_id}: {exc}")
                            continue
                        expected_frames = end_frame - start_frame
                        if base_frames != expected_frames or output_frames != expected_frames:
                            failures.append(
                                f"chunk {chunk_id}: decoded frames "
                                f"{base_frames}/{output_frames}, expected={expected_frames}"
                            )
                        if base_decoded_sha == output_decoded_sha:
                            failures.append(
                                f"chunk {chunk_id}: changed chunk decoded pixels are identical"
                            )
                        else:
                            changed_decoded_count += 1
                        if str(entry.get("base_decoded_sha256", "")).lower() != base_decoded_sha:
                            failures.append(
                                f"chunk {chunk_id}: stale base decoded-frame SHA"
                            )
                        if str(entry.get("output_decoded_sha256", "")).lower() != output_decoded_sha:
                            failures.append(
                                f"chunk {chunk_id}: stale output decoded-frame SHA"
                            )
                        for cue_value in entry.get("changed_cue_ids", []):
                            try:
                                changed_chunk_cue_ids.add(int(cue_value))
                            except (TypeError, ValueError):
                                failures.append(
                                    f"chunk {chunk_id}: invalid changed cue {cue_value!r}"
                                )
                if actual_changed_chunk_ids != declared_changed_chunk_ids:
                    failures.append(
                        "changed chunk IDs differ from manifest declaration: "
                        f"actual={sorted(actual_changed_chunk_ids)}, "
                        f"declared={sorted(declared_changed_chunk_ids)}"
                    )
                if changed_chunk_cue_ids != set(declared_changed):
                    failures.append(
                        "changed chunk cue coverage differs from patch changed_cue_ids: "
                        f"chunks={sorted(changed_chunk_cue_ids)}, "
                        f"patch={declared_changed}"
                    )
                timing_contract = json.loads(
                    timing_contract_path.read_text(encoding="utf-8")
                )
                target_frames = int(timing_contract["target_frame_count"])
                spans.sort()
                expected_frame = 0
                for start_frame, end_frame, chunk_id in spans:
                    if start_frame != expected_frame:
                        failures.append(
                            f"chunk {chunk_id}: coverage jumps from "
                            f"{expected_frame} to {start_frame}"
                        )
                    expected_frame = end_frame
                if expected_frame != target_frames:
                    failures.append(
                        f"chunk coverage ends at {expected_frame}, expected={target_frames}"
                    )
                chunk_boundary_frames = [start for start, _, _ in spans[1:]]
                chunk_metrics = {
                    "chunk_verification_manifest_sha256": chunk_manifest_sha,
                    "chunk_count": len(chunks),
                    "changed_chunk_ids": sorted(actual_changed_chunk_ids),
                    "unchanged_chunk_sha_verified": unchanged_sha_count,
                    "changed_chunk_decoded_verified": changed_decoded_count,
                }

        media_failures, media_metrics = _media_contract(
            output_path,
            timing_contract_path,
            frame_tolerance=int(check.get("frame_tolerance", 0)),
            fps_tolerance=float(check.get("fps_tolerance", 0.02)),
        )
        failures.extend(media_failures)
        black_events: list[str] = []
        if check.get("check_black_frames", True):
            try:
                black_events = _black_events(
                    output_path,
                    duration=float(check.get("black_duration", 0.05)),
                    pixel_threshold=float(check.get("black_pixel_threshold", 0.02)),
                )
            except RuntimeError as exc:
                failures.append(str(exc))
            if black_events:
                failures.append(f"black frame events={black_events[:20]}")
        final_decode_pass = None
        if chunk_scoped_mode and check.get("check_final_decode", True):
            final_decode_pass, decode_detail = full_decode_once(output_path)
            if not final_decode_pass:
                failures.append(f"final patched master decode failed: {decode_detail}")
        seam_black: list[int] = []
        seam_observed = 0
        if chunk_scoped_mode and check.get("check_transition_seams", True):
            try:
                seam_black, seam_observed = seam_black_frames(
                    output_path,
                    chunk_boundary_frames,
                    total_frames=int(media_metrics["frames"]),
                    amount=float(check.get("seam_black_amount", 99)),
                    threshold=int(check.get("seam_black_threshold", 16)),
                )
            except (RuntimeError, ValueError) as exc:
                failures.append(str(exc))
            if seam_black:
                failures.append(f"patched master black seam frames={seam_black[:20]}")
        metrics = {
            **media_metrics,
            **segment_metrics,
            **chunk_metrics,
            "base_picture_sha256": base_sha,
            "output_picture_sha256": output_sha,
            "actual_changed_cue_ids": actual_changed,
            "declared_changed_cue_ids": declared_changed,
            "black_events": black_events,
            "final_decode_pass": final_decode_pass,
            "seam_black_frames": seam_black,
            "seam_frames_observed": seam_observed,
            "patch_verification_mode": check.get("patch_verification_mode", "legacy_v1"),
            "patch_manifest_sha256": file_sha256(path),
            "repair_approval_sha256": repair_approval_sha,
            "base_approval_sha256": base_approval_sha,
            "failures": failures,
        }
        return (
            not failures,
            f"changed={actual_changed}, frames={media_metrics['frames']}, failures={failures}",
            metrics,
        )

    if check_type == "json_fields":
        data = json.loads(path.read_text(encoding="utf-8"))
        missing = []
        for field in check.get("fields", []):
            try:
                value = dotted_value(data, field)
                if value in (None, "", [], {}):
                    missing.append(field)
            except KeyError:
                missing.append(field)
        return not missing, f"missing_or_empty={missing}", {"missing_or_empty": missing}

    if check_type in {"json_assert", "live_state_assert"}:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return False, "JSON root must be an object", {}
        missing = []
        for field in check.get("required_fields", []):
            try:
                dotted_value(data, field)
            except KeyError:
                missing.append(field)
        failures = [f"{field}: missing" for field in missing]
        failures.extend(assert_json_values(data, check.get("assertions", [])))
        if check_type == "live_state_assert":
            required_live = (
                "draft_name",
                "timeline_name",
                "timeline_count",
                "project_timecode",
                "caption_count",
                "narration_clip_count",
                "picture_clip_count",
                "bgm_clip_count",
            )
            failures.extend(f"{field}: missing" for field in required_live if field not in data)
        return not failures, f"failures={failures}", {"failures": failures}

    if check_type == "text_contains":
        text = path.read_text(encoding="utf-8")
        missing = [value for value in check.get("values", []) if value not in text]
        return not missing, f"missing={missing}", {"missing": missing}

    if check_type == "tsv_status":
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        field = check.get("field", "status")
        accepted = tuple(value.lower() for value in check.get("accepted_prefixes", ["pass", "done", "waived"]))
        filter_field = check.get("filter_field")
        filter_values = set(check.get("filter_values", []))
        selected = [row for row in rows if not filter_field or row.get(filter_field) in filter_values]
        bad = [index for index, row in enumerate(selected, start=2) if not row.get(field, "").lower().startswith(accepted)]
        return not bad, f"rows={len(selected)}, failing_rows={bad}", {"rows": len(selected), "failing_rows": bad}

    if check_type == "tsv_row_count_match":
        other_path = resolve_path(root, check["other_path"])
        if not other_path.exists():
            return False, f"missing other path: {other_path}", {"path": str(path), "other_path": str(other_path)}
        with path.open(encoding="utf-8", newline="") as handle:
            left_rows = list(csv.DictReader(handle, delimiter="\t"))
        with other_path.open(encoding="utf-8", newline="") as handle:
            right_rows = list(csv.DictReader(handle, delimiter="\t"))
        left_count = len(left_rows)
        right_count = len(right_rows)
        passed = left_count == right_count
        metrics = {
            "path": str(path),
            "other_path": str(other_path),
            "left_rows": left_count,
            "right_rows": right_count,
        }
        return passed, f"left_rows={left_count}, right_rows={right_count}", metrics

    if check_type == "mission_flow_coverage":
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        if not rows:
            return False, "mission flow has no rows", {"rows": 0}

        start_field = check.get("start_field", "start_s")
        end_field = check.get("end_field", "end_s")
        evidence_field = check.get("evidence_field", "evidence_frames")
        required_nonempty = check.get(
            "required_nonempty_fields",
            ["step_id", "phase_type", evidence_field, "fact_or_inference", "confidence"],
        )
        duration = float(check["duration_s"])
        max_gap = float(check.get("max_gap_s", 2.0))
        start_tolerance = float(check.get("start_tolerance_s", max_gap))
        end_tolerance = float(check.get("end_tolerance_s", max_gap))
        allow_overlap = bool(check.get("allow_overlap", False))

        parsed = []
        errors = []
        missing_fields = []
        for line_number, row in enumerate(rows, start=2):
            try:
                start = float(row.get(start_field, ""))
                end = float(row.get(end_field, ""))
            except ValueError:
                errors.append(f"row {line_number}: invalid start/end")
                continue
            if start < 0 or end < start:
                errors.append(f"row {line_number}: range {start}..{end}")
            empty = [field for field in required_nonempty if not row.get(field, "").strip()]
            if empty:
                missing_fields.append({"row": line_number, "fields": empty})
            parsed.append((start, end, line_number))

        parsed.sort()
        gaps = []
        overlaps = []
        if parsed:
            if parsed[0][0] > start_tolerance:
                gaps.append({"from": 0.0, "to": parsed[0][0], "seconds": parsed[0][0]})
            covered_end = parsed[0][1]
            for start, end, line_number in parsed[1:]:
                if start > covered_end + max_gap:
                    gaps.append({"from": covered_end, "to": start, "seconds": start - covered_end})
                if start < covered_end and not allow_overlap:
                    overlaps.append({"row": line_number, "seconds": covered_end - start})
                covered_end = max(covered_end, end)
            if covered_end < duration - end_tolerance:
                gaps.append({"from": covered_end, "to": duration, "seconds": duration - covered_end})
        else:
            covered_end = 0.0

        passed = not errors and not missing_fields and not gaps and not overlaps
        metrics = {
            "rows": len(rows),
            "duration_s": duration,
            "covered_end_s": covered_end,
            "max_gap_s": max_gap,
            "gaps": gaps,
            "overlaps": overlaps,
            "range_errors": errors,
            "missing_fields": missing_fields,
        }
        detail = (
            f"rows={len(rows)}, covered_end={covered_end:.3f}, gaps={len(gaps)}, "
            f"overlaps={len(overlaps)}, invalid={len(errors)}, incomplete={len(missing_fields)}"
        )
        return passed, detail, metrics

    if check_type == "srt_no_adjacent_duplicates":
        texts = parse_srt_texts(path)
        duplicates = [index + 1 for index in range(1, len(texts)) if texts[index] == texts[index - 1]]
        return not duplicates, f"entries={len(texts)}, duplicate_entries={duplicates}", {"entries": len(texts), "duplicate_entries": duplicates}

    if check_type == "srt_integrity":
        entries = parse_srt_entries(path)
        required_config = [
            field
            for field in (
                "expected_count",
                "reference_text_path",
                "expected_end_seconds",
                "forbidden_terminal_punctuation",
                "terminal_closing_marks",
            )
            if field not in check
        ]
        if required_config:
            return False, f"check config missing {required_config}", {"config_missing": required_config}
        failures = []
        expected_forbidden = list(CAPTION_FORBIDDEN_TERMINAL_PUNCTUATION)
        expected_closing_marks = list(CAPTION_TRAILING_CLOSING_MARKS)
        if check["forbidden_terminal_punctuation"] != expected_forbidden:
            failures.append(
                "forbidden_terminal_punctuation must equal "
                f"{expected_forbidden!r}"
            )
        if check["terminal_closing_marks"] != expected_closing_marks:
            failures.append(f"terminal_closing_marks must equal {expected_closing_marks!r}")
        expected_count = int(check["expected_count"])
        if len(entries) != expected_count:
            failures.append(f"count={len(entries)}, expected={expected_count}")
        expected_indices = list(range(1, len(entries) + 1))
        actual_indices = [entry["index"] for entry in entries]
        if actual_indices != expected_indices:
            failures.append("indices are not continuous from 1")
        bad_ranges = [entry["index"] for entry in entries if entry["start"] < 0 or entry["end"] <= entry["start"]]
        if bad_ranges:
            failures.append(f"invalid_ranges={bad_ranges}")
        overlaps = [entries[index]["index"] for index in range(1, len(entries)) if entries[index]["start"] < entries[index - 1]["end"]]
        if overlaps and not check.get("allow_overlaps", False):
            failures.append(f"overlaps={overlaps}")
        duplicates = [entries[index]["index"] for index in range(1, len(entries)) if entries[index]["text"] == entries[index - 1]["text"]]
        if duplicates:
            failures.append(f"adjacent_duplicates={duplicates}")
        forbidden_terminal_entries = [
            {
                "entry": entry["index"],
                "punctuation": punctuation,
                "text": entry["text"],
            }
            for entry in entries
            if (punctuation := find_forbidden_terminal_punctuation(entry["text"]))
        ]
        if forbidden_terminal_entries:
            failures.append(
                "forbidden_terminal_punctuation_entries="
                f"{[entry['entry'] for entry in forbidden_terminal_entries]}"
            )
        ordered_text = "\n".join(entry["text"] for entry in entries)
        ordered_sha = hashlib.sha256(ordered_text.encode("utf-8")).hexdigest()
        expected_sha = check.get("expected_text_sha256")
        if expected_sha and ordered_sha != expected_sha:
            failures.append(f"ordered_text_sha256={ordered_sha}, expected={expected_sha}")
        reference_path = resolve_path(root, check["reference_text_path"])
        if not reference_path.is_file():
            failures.append(f"missing reference_text_path={reference_path}")
            reference_sha = ""
        else:
            reference_text = lexical_text(reference_path.read_text(encoding="utf-8-sig"))
            actual_text = lexical_text("".join(entry["text"] for entry in entries))
            reference_sha = hashlib.sha256(reference_text.encode("utf-8")).hexdigest()
            if actual_text != reference_text:
                failures.append("lexical coverage differs from reference_text_path")
        final_end = entries[-1]["end"] if entries else 0.0
        if "end_tolerance_ms" in check:
            tolerance = float(check["end_tolerance_ms"]) / 1000
        elif "final_end_tolerance_seconds" in check:
            # Backward-compatible support for early production plans that
            # expressed the same tolerance directly in seconds.
            tolerance = float(check["final_end_tolerance_seconds"])
        else:
            tolerance = 0.05
        if abs(final_end - float(check["expected_end_seconds"])) > tolerance:
            failures.append(f"final_end={final_end:.3f}, expected={float(check['expected_end_seconds']):.3f}±{tolerance:.3f}")
        metrics = {
            "entries": len(entries),
            "final_end": final_end,
            "ordered_text_sha256": ordered_sha,
            "reference_lexical_sha256": reference_sha,
            "overlaps": overlaps,
            "adjacent_duplicates": duplicates,
            "forbidden_terminal_punctuation_entries": forbidden_terminal_entries,
            "terminal_punctuation_policy": {
                "forbidden": expected_forbidden,
                "trailing_closing_marks": expected_closing_marks,
                "preserved": ["？", "！", "?", "!"],
            },
            "failures": failures,
        }
        return not failures, f"entries={len(entries)}, final_end={final_end:.3f}, failures={failures}", metrics

    if check_type == "bgm_sources_within_root":
        data = json.loads(path.read_text(encoding="utf-8"))
        sections_field = check.get("sections_field", "sections")
        source_field = check.get("source_field", "source")
        sections = dotted_value(data, sections_field)
        source_root_value = check.get("source_root")
        source_root = (
            Path(source_root_value).expanduser()
            if source_root_value
            else Path.home() / "Music"
        ).resolve()
        if not source_root.is_dir():
            return False, f"source root is not a directory: {source_root}", {"source_root": str(source_root)}
        if not isinstance(sections, list) or not sections:
            return False, f"{sections_field} must be a nonempty list", {"source_root": str(source_root), "sections": 0}

        failures = []
        accepted_sources = []
        for index, section in enumerate(sections, start=1):
            raw_source = section.get(source_field) if isinstance(section, dict) else None
            if not isinstance(raw_source, str) or not raw_source.strip():
                failures.append(f"section {index}: missing {source_field}")
                continue
            candidate = Path(raw_source).expanduser()
            if not candidate.is_absolute():
                failures.append(f"section {index}: source must be absolute: {raw_source}")
                continue
            resolved = candidate.resolve()
            if not resolved.is_file():
                failures.append(f"section {index}: source is not a file: {resolved}")
                continue
            try:
                resolved.relative_to(source_root)
            except ValueError:
                failures.append(f"section {index}: source outside {source_root}: {resolved}")
                continue
            accepted_sources.append(str(resolved))

        metrics = {
            "source_root": str(source_root),
            "sections": len(sections),
            "accepted_source_count": len(accepted_sources),
            "accepted_sources": accepted_sources,
            "failures": failures,
        }
        return not failures, f"sections={len(sections)}, failures={failures}", metrics

    if check_type == "generated_bgm_manifest_integrity":
        data = json.loads(path.read_text(encoding="utf-8"))
        failures = []
        if data.get("source_mode") != "generated_score":
            failures.append("bgm manifest source_mode must be generated_score")
        generation_value = data.get("generation_manifest") or check.get("generation_manifest_path")
        if not isinstance(generation_value, str) or not generation_value.strip():
            failures.append("missing generation_manifest path")
            generation_path = None
            generation_data = {}
        else:
            generation_path = resolve_path(root, generation_value)
            if not generation_path.is_file():
                failures.append(f"generation manifest missing: {generation_path}")
                generation_data = {}
            else:
                generation_data = json.loads(generation_path.read_text(encoding="utf-8"))
        if generation_data.get("status") != "pass":
            failures.append("generation manifest status must be pass")
        generations = generation_data.get("generations")
        if not isinstance(generations, list) or not generations:
            failures.append("generation manifest generations must be a nonempty list")
            generations = []

        generated_sources: dict[str, dict[str, Any]] = {}
        for index, record in enumerate(generations, start=1):
            if not isinstance(record, dict):
                failures.append(f"generation {index}: record must be an object")
                continue
            for field in ("service", "model", "source", "sha256"):
                if not str(record.get(field, "")).strip():
                    failures.append(f"generation {index}: missing {field}")
            if not str(record.get("prompt", "")).strip() and not str(record.get("prompt_sha256", "")).strip():
                failures.append(f"generation {index}: missing prompt or prompt_sha256")
            try:
                if float(record.get("duration", 0)) <= 0:
                    failures.append(f"generation {index}: duration must be positive")
            except (TypeError, ValueError):
                failures.append(f"generation {index}: invalid duration")
            source_value = record.get("source")
            if not isinstance(source_value, str) or not source_value.strip():
                continue
            source_path = Path(source_value).expanduser()
            if not source_path.is_absolute():
                failures.append(f"generation {index}: source must be absolute")
                continue
            resolved = source_path.resolve()
            if not resolved.is_file():
                failures.append(f"generation {index}: source is not a file: {resolved}")
                continue
            digest = file_sha256(resolved)
            if digest != record.get("sha256"):
                failures.append(f"generation {index}: sha256 mismatch: {resolved}")
                continue
            generated_sources[str(resolved)] = record

        sections = data.get("sections")
        if not isinstance(sections, list) or not sections:
            failures.append("bgm manifest sections must be a nonempty list")
            sections = []
        accepted_sources = []
        for index, section in enumerate(sections, start=1):
            raw_source = section.get("source") if isinstance(section, dict) else None
            if not isinstance(raw_source, str) or not raw_source.strip():
                failures.append(f"section {index}: missing source")
                continue
            resolved = str(Path(raw_source).expanduser().resolve())
            if resolved not in generated_sources:
                failures.append(f"section {index}: source is not bound to generation manifest: {resolved}")
                continue
            accepted_sources.append(resolved)

        metrics = {
            "source_mode": data.get("source_mode"),
            "generation_manifest": str(generation_path) if generation_path else None,
            "generation_count": len(generations),
            "sections": len(sections),
            "accepted_source_count": len(accepted_sources),
            "accepted_sources": accepted_sources,
            "failures": failures,
        }
        return not failures, f"generations={len(generations)}, sections={len(sections)}, failures={failures}", metrics

    if check_type == "image_evidence_set":
        matches = sorted(path.glob(check.get("pattern", "*.png")))
        minimum = int(check.get("min_count", 3))
        failures = []
        if len(matches) < minimum:
            failures.append(f"count={len(matches)}, expected>={minimum}")
        digests = [file_sha256(candidate) for candidate in matches]
        if len(digests) != len(set(digests)):
            failures.append("evidence images are not distinct")
        black = []
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            failures.append("ffmpeg not found for non-black evidence check")
        else:
            for candidate in matches:
                completed = subprocess.run(
                    [ffmpeg, "-hide_banner", "-loglevel", "info", "-i", str(candidate), "-vf", "signalstats,metadata=print", "-frames:v", "1", "-f", "null", "-"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                values = re.findall(r"lavfi\.signalstats\.YAVG=([0-9.]+)", completed.stderr + completed.stdout)
                if not values or float(values[-1]) <= float(check.get("min_yavg", 4.0)):
                    black.append(candidate.name)
                if check.get("require_companion_json", True):
                    companion = candidate.with_suffix(".json")
                    if not companion.is_file():
                        failures.append(f"missing companion live-state JSON: {companion.name}")
                    else:
                        live = json.loads(companion.read_text(encoding="utf-8"))
                        for field in ("timecode", "draft_name", "timeline_name"):
                            if not live.get(field):
                                failures.append(f"{companion.name} missing {field}")
        if black:
            failures.append(f"black_or_unreadable={black}")
        return not failures, f"images={len(matches)}, failures={failures}", {"images": [str(item) for item in matches], "failures": failures}

    if check_type == "media_frame_contract":
        contract_path = resolve_path(root, check["timing_contract_path"])
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        probe = ffprobe_json(path, count_frames=True)
        streams = probe.get("streams", [])
        video = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
        audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})
        stream = video or audio
        duration = float(probe.get("format", {}).get("duration", 0.0) or 0.0)
        fps = float(Fraction(video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1")) if video else float(contract["fps"])
        frames = int(stream.get("nb_read_frames") or stream.get("nb_frames") or round(duration * fps))
        expected_frames = int(contract["target_frame_count"])
        tolerance_frames = int(check.get("frame_tolerance", 0))
        failures = []
        if abs(frames - expected_frames) > tolerance_frames:
            failures.append(f"frames={frames}, expected={expected_frames}±{tolerance_frames}")
        if video and abs(fps - float(contract["fps"])) > float(check.get("fps_tolerance", 0.02)):
            failures.append(f"fps={fps}, expected={contract['fps']}")
        if "audio_streams" in check:
            audio_count = sum(item.get("codec_type") == "audio" for item in streams)
            if audio_count != int(check["audio_streams"]):
                failures.append(f"audio_streams={audio_count}, expected={check['audio_streams']}")
        return not failures, "; ".join(failures) if failures else "frame contract matched", {"frames": frames, "fps": fps, "duration": duration, "failures": failures}

    try:
        probe = ffprobe_json(path)
    except RuntimeError as exc:
        return False, str(exc), {}
    streams = probe.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio_count = sum(stream.get("codec_type") == "audio" for stream in streams)
    duration = float(probe.get("format", {}).get("duration", 0.0) or 0.0)
    fps_text = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
    fps = float(Fraction(fps_text)) if fps_text != "0/0" else 0.0
    metrics = {
        "duration": duration,
        "width": int(video.get("width", 0) or 0),
        "height": int(video.get("height", 0) or 0),
        "fps": fps,
        "video_streams": sum(stream.get("codec_type") == "video" for stream in streams),
        "audio_streams": audio_count,
    }
    expect = check.get("expect", {})
    failures = []
    for key in ("width", "height", "video_streams", "audio_streams"):
        if key in expect and metrics[key] != int(expect[key]):
            failures.append(f"{key}={metrics[key]} expected={expect[key]}")
    if "fps" in expect and abs(metrics["fps"] - float(expect["fps"])) > float(expect.get("fps_tolerance", 0.02)):
        failures.append(f"fps={metrics['fps']} expected={expect['fps']}")
    if "duration_min" in expect and duration < float(expect["duration_min"]):
        failures.append(f"duration={duration} below={expect['duration_min']}")
    if "duration_max" in expect and duration > float(expect["duration_max"]):
        failures.append(f"duration={duration} above={expect['duration_max']}")
    return not failures, "; ".join(failures) if failures else "metadata matched", metrics


def run_plan(root: Path, selected_ids: set[str] | None = None) -> dict[str, Any]:
    plan_path = root / "verification_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    checks = plan.get("checks", [])
    by_id = {check.get("id"): check for check in checks}
    ids = list(selected_ids) if selected_ids else [check.get("id") for check in checks]
    results = []
    for check_id in ids:
        check = by_id.get(check_id)
        if not check:
            results.append({"id": check_id, "required": True, "pass": False, "detail": "check id not found", "metrics": {}})
            continue
        try:
            passed, detail, metrics = run_check(root, check)
        except Exception as exc:
            passed, detail, metrics = False, f"{type(exc).__name__}: {exc}", {}
        results.append(
            {
                "id": check_id,
                "type": check.get("type"),
                "required": bool(check.get("required", True)),
                "pass": bool(passed),
                "detail": detail,
                "metrics": metrics,
            }
        )
    report = {"run_dir": str(root), "checked_at": datetime.now(timezone.utc).isoformat(), "results": results}
    output = root / "qa/verification_results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--check-id", action="append", help="Run only the named check; repeat as needed")
    args = parser.parse_args()
    root = Path(args.run_dir).expanduser().resolve()
    report = run_plan(root, set(args.check_id) if args.check_id else None)
    failed = [row for row in report["results"] if row["required"] and not row["pass"]]
    for row in report["results"]:
        print(f"{'PASS' if row['pass'] else 'FAIL'} {row['id']}: {row['detail']}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
