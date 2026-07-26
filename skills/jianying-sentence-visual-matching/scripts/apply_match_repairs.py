#!/usr/bin/env python3
"""Apply hash-bound A/B/C choices or explicit override candidates safely."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STILL_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def split_identity_values(value: object) -> set[str]:
    if isinstance(value, list):
        raw_values = [str(item) for item in value]
    else:
        raw_values = re.split(r"[,，、;/；|]+", str(value or ""))
    return {item.strip() for item in raw_values if item.strip()}


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def atomic_json(path: Path, value: object) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def read_match_sheet(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader.fieldnames or []), list(reader)


def write_match_sheet(
    path: Path, fields: list[str], rows: list[dict[str, str]]
) -> None:
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8", newline="") as buffer:
        writer = csv.DictWriter(
            buffer,
            fieldnames=fields,
            delimiter="\t",
            lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)
        buffer.seek(0)
        atomic_text(path, buffer.read())


def source_paths_from_manifest(path: Path | None) -> dict[str, Path]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, Path] = {}
    for key in ("primary_sources", "auxiliary_assets", "sources", "assets"):
        for item in data.get(key, []):
            source_id = str(
                item.get("source_id")
                or item.get("asset_id")
                or item.get("id")
                or ""
            )
            source_path = (
                item.get("real_path")
                or item.get("path")
                or item.get("local_path")
                or item.get("source_file")
            )
            if source_id and source_path:
                result[source_id] = Path(str(source_path)).expanduser().resolve()
    return result


def parse_candidate(value: str) -> dict[str, Any]:
    parts = value.split("|")
    if len(parts) < 5:
        raise ValueError(f"unrecognized candidate descriptor: {value!r}")
    source_id, filename, span, step_id, kind = parts[:5]
    matches = re.findall(r"(-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)", span)
    if len(matches) != 1:
        raise ValueError(
            "A/B/C repair requires one continuous candidate range; "
            "use an explicit override for a composite candidate"
        )
    source_in, source_out = (float(item) for item in matches[0])
    if source_out <= source_in:
        raise ValueError("candidate source_out must be after source_in")
    return {
        "source_id": source_id,
        "filename": filename,
        "source_in": source_in,
        "source_out": source_out,
        "step_id": step_id,
        "kind": kind,
        "descriptor": value,
    }


def resolve_source(
    candidate: dict[str, Any],
    row: dict[str, str],
    repair: dict[str, Any],
    source_paths: dict[str, Path],
) -> Path:
    explicit = repair.get("source_file")
    if explicit:
        path = Path(str(explicit)).expanduser().resolve()
        if path.name != Path(str(candidate["filename"])).name:
            raise ValueError("repair source_file does not match selected candidate")
        return path
    source_id = str(candidate["source_id"])
    if source_id in source_paths:
        return source_paths[source_id]
    filename = Path(str(candidate["filename"])).expanduser()
    if filename.is_absolute():
        return filename.resolve()
    current = Path(row.get("source_file", "")).expanduser()
    if current.is_absolute() and current.name == filename.name:
        return current.resolve()
    raise ValueError(
        f"cannot resolve {source_id!r}/{filename!r}; "
        "provide --source-manifest or repair.source_file"
    )


def load_candidate_pool(path: Path | None) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    if path is None or not path.is_file():
        return [], {}
    entries = []
    by_cue = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        cue_id = int(entry.get("cue_id") or entry.get("line_id"))
        entries.append(entry)
        by_cue[cue_id] = entry
    return entries, by_cue


def write_candidate_pool(path: Path, entries: list[dict[str, Any]]) -> None:
    atomic_text(
        path,
        "".join(
            json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n"
            for entry in sorted(
                entries, key=lambda item: int(item.get("cue_id") or item.get("line_id"))
            )
        ),
    )


def add_pool_candidate(
    entries: list[dict[str, Any]],
    by_cue: dict[int, dict[str, Any]],
    cue_id: int,
    candidate: dict[str, Any],
) -> None:
    entry = by_cue.get(cue_id)
    if entry is None:
        entry = {"cue_id": cue_id, "candidates": []}
        entries.append(entry)
        by_cue[cue_id] = entry
    candidates = entry.setdefault("candidates", [])
    candidate_id = candidate["candidate_id"]
    for index, existing in enumerate(candidates):
        if existing.get("candidate_id") == candidate_id:
            candidates[index] = candidate
            return
    candidates.append(candidate)


def pool_candidate_matches(
    item: object,
    *,
    descriptor: str,
    source_id: str,
    source: Path,
    source_in: float,
    source_out: float,
) -> bool:
    if not isinstance(item, dict):
        return False
    if str(item.get("descriptor") or "") == descriptor:
        return True
    try:
        return (
            str(item.get("source_id") or "") == source_id
            and Path(str(item.get("source_file") or "")).name == source.name
            and abs(float(item["source_in"]) - source_in) <= 0.002
            and abs(float(item["source_out"]) - source_out) <= 0.022
        )
    except (KeyError, TypeError, ValueError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("match_sheet", nargs="?", type=Path)
    parser.add_argument("repair_manifest", nargs="?", type=Path)
    parser.add_argument("--match-sheet", dest="match_sheet_flag", type=Path)
    parser.add_argument("--repairs", dest="repair_manifest_flag", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--candidate-pool", type=Path)
    parser.add_argument("--snapshot-dir", type=Path)
    parser.add_argument("--history", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--review-manifest", type=Path)
    args = parser.parse_args()

    match_sheet = args.match_sheet_flag or args.match_sheet
    manifest_path = args.repair_manifest_flag or args.repair_manifest
    if match_sheet is None or manifest_path is None:
        parser.error("provide MATCH_SHEET and REPAIR_MANIFEST")
    match_sheet = match_sheet.expanduser().resolve()
    manifest_path = manifest_path.expanduser().resolve()
    output = (
        args.output.expanduser().resolve()
        if args.output
        else match_sheet
    )
    source_manifest = (
        args.source_manifest.expanduser().resolve()
        if args.source_manifest
        else None
    )
    candidate_pool = (
        args.candidate_pool.expanduser().resolve()
        if args.candidate_pool
        else (
            match_sheet.parent / "candidate_pool.jsonl"
            if (match_sheet.parent / "candidate_pool.jsonl").exists()
            else None
        )
    )
    snapshot_dir = (
        args.snapshot_dir.expanduser().resolve()
        if args.snapshot_dir
        else match_sheet.parent / "snapshots"
    )
    history_path = (
        args.history.expanduser().resolve()
        if args.history
        else match_sheet.parent / "repair_history.jsonl"
    )
    review_manifest = (
        args.review_manifest.expanduser().resolve()
        if args.review_manifest
        else None
    )

    input_sha = sha256_file(match_sheet)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_sha = str(
        manifest.get("base_match_sheet_sha256")
        or manifest.get("match_sheet_sha256")
        or ""
    )
    if not expected_sha:
        raise SystemExit("repair manifest missing base_match_sheet_sha256")
    if expected_sha != input_sha:
        raise SystemExit(
            f"base hash mismatch: manifest={expected_sha} current={input_sha}"
        )
    review_manifest_sha = ""
    if review_manifest is None or not review_manifest.is_file():
        raise SystemExit("--review-manifest is required and must exist")
    review_manifest_sha = sha256_file(review_manifest)
    review_data = json.loads(review_manifest.read_text(encoding="utf-8"))
    expected_review_sha = str(
        manifest.get("review_manifest_sha256")
        or manifest.get("input_review_sha256")
        or ""
    )
    if not expected_review_sha:
        raise SystemExit(
            "repair manifest missing review_manifest_sha256"
        )
    if expected_review_sha != review_manifest_sha:
        raise SystemExit(
            "review manifest hash mismatch: "
            f"manifest={expected_review_sha} current={review_manifest_sha}"
        )
    review_match_sha = str(
        review_data.get("match_sheet_sha256")
        or review_data.get("final_match_sheet_sha256")
        or ""
    )
    if review_match_sha != input_sha:
        raise SystemExit(
            "review manifest is not bound to the base match sheet"
        )
    repairs = manifest.get("repairs")
    if not isinstance(repairs, list) or not repairs:
        raise SystemExit("repair manifest repairs must be a non-empty list")

    fields, rows = read_match_sheet(match_sheet)
    row_by_id = {int(row["line_id"]): row for row in rows}
    if len(row_by_id) != len(rows):
        raise SystemExit("duplicate line_id values in match sheet")
    repair_ids = [int(item["line_id"]) for item in repairs]
    if len(repair_ids) != len(set(repair_ids)):
        raise SystemExit("repair manifest contains duplicate line_id values")
    unknown = sorted(set(repair_ids) - set(row_by_id))
    if unknown:
        raise SystemExit(f"repair manifest references unknown rows: {unknown}")
    review_unresolved_raw = review_data.get("unresolved_cue_ids")
    if review_unresolved_raw is None:
        review_unresolved_raw = review_data.get("unresolved_ids", [])
    review_unresolved = {
        int(item.get("cue_id") if isinstance(item, dict) else item)
        for item in (
            review_unresolved_raw
            if isinstance(review_unresolved_raw, list)
            else []
        )
    }
    omitted_unresolved = sorted(review_unresolved - set(repair_ids))
    if omitted_unresolved:
        raise SystemExit(
            "repairs do not cover review unresolved cues: "
            f"{omitted_unresolved}"
        )

    added_fields = [
        "selected_candidate_id",
        "selection_origin",
        "repair_id",
        "repair_manifest_sha256",
        "repair_base_match_sheet_sha256",
        "review_status",
        "identity_review",
        "override_candidate_json",
        "visual_review",
        "selected_source_id",
        "selected_step_id",
    ]
    for field in added_fields:
        if field not in fields:
            fields.append(field)
            for row in rows:
                row[field] = ""

    if source_manifest is None or not source_manifest.is_file():
        raise SystemExit(
            "--source-manifest is required and must name the current "
            "indexed source manifest"
        )
    source_manifest_sha = sha256_file(source_manifest)
    if str(manifest.get("source_manifest_sha256") or "") != source_manifest_sha:
        raise SystemExit(
            "repair manifest is not bound to the current source manifest"
        )
    source_paths = source_paths_from_manifest(source_manifest)
    pool_entries, pool_by_cue = load_candidate_pool(candidate_pool)
    if candidate_pool is None or not candidate_pool.is_file():
        raise SystemExit(
            "--candidate-pool is required and must name the current pool"
        )
    pool_input_sha = (
        sha256_file(candidate_pool) if candidate_pool and candidate_pool.is_file() else ""
    )
    expected_pool_sha = str(
        manifest.get("before_candidate_pool_sha256")
        or manifest.get("base_candidate_pool_sha256")
        or ""
    )
    if not expected_pool_sha:
        raise SystemExit(
            "repair manifest missing before_candidate_pool_sha256"
        )
    if expected_pool_sha != pool_input_sha:
        raise SystemExit(
            "candidate pool hash mismatch: "
            f"manifest={expected_pool_sha} current={pool_input_sha}"
        )
    review_pool_value = review_data.get("candidate_pool")
    review_pool_sha = str(
        review_data.get("candidate_pool_sha256")
        or (
            review_pool_value.get("sha256")
            if isinstance(review_pool_value, dict)
            else ""
        )
        or ""
    )
    if review_pool_sha != pool_input_sha:
        raise SystemExit(
            "review manifest is not bound to the base candidate pool"
        )
    pool_ids_before = {
        str(candidate.get("candidate_id"))
        for entry in pool_entries
        for candidate in entry.get("candidates", [])
        if isinstance(candidate, dict) and candidate.get("candidate_id")
    }
    manifest_sha = sha256_file(manifest_path)
    repair_set_id = str(manifest.get("repair_id") or manifest_sha[:16])
    applied = []
    audit_repairs = []

    for repair in repairs:
        line_id = int(repair["line_id"])
        row = row_by_id[line_id]
        duration = float(row["duration"])
        review_status = str(repair.get("review_status") or "approved")
        if review_status.casefold() not in {"approved", "pass", "verified"}:
            raise SystemExit(f"line {line_id}: repair is not approved")
        choice = str(repair.get("selected_choice") or "").upper()
        override = repair.get("override")
        if bool(choice) == bool(override):
            raise SystemExit(
                f"line {line_id}: provide exactly one of selected_choice or override"
            )

        if choice:
            if choice not in {"A", "B", "C"}:
                raise SystemExit(f"line {line_id}: invalid selected_choice={choice}")
            descriptor = row[f"candidate_{choice.lower()}"].strip()
            candidate = parse_candidate(descriptor)
            source = resolve_source(candidate, row, repair, source_paths)
            source_in = float(candidate["source_in"])
            source_out = float(candidate["source_out"])
            kind = str(candidate["kind"])
            candidate_record = {
                "candidate_id": stable_id({"line_id": line_id, "descriptor": descriptor}),
                "origin": f"candidate_{choice}",
                "descriptor": descriptor,
                "source_id": candidate["source_id"],
                "source_file": str(source),
                "source_in": source_in,
                "source_out": source_out,
                "kind": kind,
                "step_id": candidate["step_id"],
            }
            if candidate_pool is not None:
                pool_entry = pool_by_cue.get(line_id)
                pool_candidates = (
                    pool_entry.get("candidates", [])
                    if isinstance(pool_entry, dict)
                    else []
                )
                matching_pool_candidate = next(
                    (
                        item
                        for item in pool_candidates
                        if pool_candidate_matches(
                            item,
                            descriptor=descriptor,
                            source_id=str(candidate["source_id"]),
                            source=source,
                            source_in=source_in,
                            source_out=source_out,
                        )
                    ),
                    None,
                )
                if matching_pool_candidate is None:
                    raise SystemExit(
                        f"line {line_id}: selected A/B/C candidate is not "
                        "present in candidate pool"
                    )
                candidate_record = {
                    **matching_pool_candidate,
                    **candidate_record,
                    "candidate_id": str(
                        matching_pool_candidate["candidate_id"]
                    ),
                }
            selection_origin = f"candidate_{choice}"
            visual_review = f"approved_choice_{choice}"
            override_json = ""
        else:
            if not isinstance(override, dict):
                raise SystemExit(f"line {line_id}: override must be an object")
            required = {"source_id", "source_file"}
            missing = sorted(required - set(override))
            if missing:
                raise SystemExit(
                    f"line {line_id}: override missing {', '.join(missing)}"
                )
            source = Path(str(override["source_file"])).expanduser().resolve()
            override_source_id = str(override["source_id"])
            indexed_source = source_paths.get(override_source_id)
            if (
                indexed_source is None
                or indexed_source.resolve() != source
            ):
                raise SystemExit(
                    f"line {line_id}: manual expansion source is not bound "
                    "to the current source manifest"
                )
            kind = str(
                override.get(
                    "kind",
                    "still"
                    if source.suffix.casefold() in STILL_SUFFIXES
                    else "video",
                )
            )
            if kind == "still":
                source_in, source_out = 0.0, duration
            else:
                if "source_in" not in override or "source_out" not in override:
                    raise SystemExit(
                        f"line {line_id}: video override needs source_in/source_out"
                    )
                source_in = float(override["source_in"])
                source_out = float(override["source_out"])
            candidate_record = {
                "origin": "manual_expansion",
                "source_id": override_source_id,
                "source_file": str(source),
                "source_in": source_in,
                "source_out": source_out,
                "kind": kind,
                "step_id": str(override.get("step_id") or "manual_override"),
                "evidence": override.get("evidence", {}),
                "identity_label": str(
                    override.get("identity_label")
                    or repair.get("identity_label")
                    or ""
                ),
                "reason": str(
                    override.get("reason")
                    or repair.get("match_reason")
                    or manifest.get("reason")
                    or "explicit reviewed override"
                ),
            }
            candidate_record["candidate_id"] = stable_id(
                {"line_id": line_id, **candidate_record}
            )
            override_evidence = candidate_record["evidence"]
            if not isinstance(override_evidence, dict):
                raise SystemExit(
                    f"line {line_id}: override evidence must be a "
                    "head/mid/tail object"
                )
            for sample in ("head", "mid", "tail"):
                raw_sample = override_evidence.get(sample)
                if isinstance(raw_sample, dict):
                    raw_sample = raw_sample.get("path")
                if not raw_sample:
                    raise SystemExit(
                        f"line {line_id}: override evidence missing {sample}"
                    )
                sample_path = Path(str(raw_sample)).expanduser()
                if not sample_path.is_absolute():
                    sample_path = manifest_path.parent / sample_path
                if not sample_path.resolve().is_file():
                    raise SystemExit(
                        f"line {line_id}: override {sample} evidence is missing"
                    )
            selection_origin = "manual_expansion"
            visual_review = "approved_override"
            override_json = json.dumps(
                candidate_record, ensure_ascii=False, sort_keys=True
            )
            if candidate_pool is not None:
                add_pool_candidate(
                    pool_entries, pool_by_cue, line_id, candidate_record
                )

        if not source.is_file():
            raise SystemExit(f"line {line_id}: selected source missing: {source}")
        if source_out <= source_in:
            raise SystemExit(f"line {line_id}: source_out must be after source_in")
        if kind != "still" and source_out - source_in + 0.04 < duration:
            raise SystemExit(
                f"line {line_id}: selected source shorter than visual duration"
            )
        identity = str(
            repair.get("identity_label")
            or (
                override.get("identity_label", "")
                if isinstance(override, dict)
                else ""
            )
        )
        reason = str(
            repair.get("match_reason")
            or (
                override.get("reason", "")
                if isinstance(override, dict)
                else ""
            )
            or manifest.get("reason")
            or "reviewed repair"
        ).strip()
        if not reason:
            raise SystemExit(f"line {line_id}: match_reason is required")
        evidence_value = (
            repair.get("evidence")
            or repair.get("evidence_path")
            or (
                row.get(f"candidate_{choice.lower()}_evidence", "")
                if choice
                else ""
            )
        )
        if not isinstance(evidence_value, str) or not evidence_value.strip():
            raise SystemExit(f"line {line_id}: repair evidence path is required")
        evidence_path = Path(evidence_value).expanduser()
        if not evidence_path.is_absolute():
            evidence_path = manifest_path.parent / evidence_path
        evidence_path = evidence_path.resolve()
        if not evidence_path.is_file():
            raise SystemExit(
                f"line {line_id}: repair evidence is missing: {evidence_path}"
            )
        expected_identities = split_identity_values(
            row.get("named_entities_expected", "")
        )
        identity_check = repair.get("identity_check")
        if expected_identities:
            if not isinstance(identity_check, dict):
                raise SystemExit(
                    f"line {line_id}: identity_check is required for "
                    f"{sorted(expected_identities)}"
                )
            visible = split_identity_values(identity_check.get("visible", []))
            if not expected_identities.issubset(visible):
                raise SystemExit(
                    f"line {line_id}: identity_check does not visibly verify "
                    f"{sorted(expected_identities)}"
                )
            if str(identity_check.get("status", "")).upper() != "PASS":
                raise SystemExit(
                    f"line {line_id}: identity_check status must be PASS"
                )

        row.update(
            {
                "source_file": str(source),
                "source_in": f"{source_in:.6f}",
                "source_out": f"{source_out:.6f}",
                "source_id": str(candidate_record["source_id"]),
                "selected_source_id": str(candidate_record["source_id"]),
                "selected_step_id": str(candidate_record.get("step_id") or ""),
                "selected_candidate_id": str(candidate_record["candidate_id"]),
                "selection_origin": selection_origin,
                "repair_id": repair_set_id,
                "repair_manifest_sha256": manifest_sha,
                "repair_base_match_sheet_sha256": input_sha,
                "review_status": "approved",
                "identity_review": (
                    f"verified:{identity}" if identity else row.get("identity_review", "")
                ),
                "override_candidate_json": override_json,
                "visual_review": visual_review,
                "match_reason": reason,
                "qa_status": (
                    "card"
                    if kind == "still"
                    else "reviewed"
                ),
            }
        )
        if "treatment" in repair:
            row["treatment"] = str(repair["treatment"])
        elif isinstance(override, dict) and override.get("treatment"):
            row["treatment"] = str(override["treatment"])
        applied.append(
            {
                "line_id": line_id,
                "candidate_id": candidate_record["candidate_id"],
                "selection_origin": selection_origin,
                "source_file": str(source),
                "source_in": source_in,
                "source_out": source_out,
            }
        )
        audit_repair = {
            "cue_id": line_id,
            "reason": reason,
            "evidence": str(evidence_path),
            "selected_candidate_id": candidate_record["candidate_id"],
            "selection_origin": selection_origin,
        }
        if isinstance(identity_check, dict):
            audit_repair["identity_check"] = identity_check
        audit_repairs.append(audit_repair)

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot = snapshot_dir / f"{match_sheet.stem}.pre_repair.{input_sha[:16]}.tsv"
    if not snapshot.exists():
        shutil.copy2(match_sheet, snapshot)
        os.chmod(snapshot, 0o444)
    pool_snapshot: Path | None = None
    if candidate_pool is not None and candidate_pool.is_file():
        pool_snapshot = (
            snapshot_dir
            / (
                f"{candidate_pool.stem}.pre_repair."
                f"{pool_input_sha[:16]}{candidate_pool.suffix}"
            )
        )
        if not pool_snapshot.exists():
            shutil.copy2(candidate_pool, pool_snapshot)
            os.chmod(pool_snapshot, 0o444)

    write_match_sheet(output, fields, rows)
    output_sha = sha256_file(output)
    pool_output_sha = pool_input_sha
    if candidate_pool is not None and any(
        item["selection_origin"] == "manual_expansion" for item in applied
    ):
        write_candidate_pool(candidate_pool, pool_entries)
        pool_output_sha = sha256_file(candidate_pool)
    pool_ids_after = {
        str(candidate.get("candidate_id"))
        for entry in pool_entries
        for candidate in entry.get("candidates", [])
        if isinstance(candidate, dict) and candidate.get("candidate_id")
    }
    added_candidate_ids = sorted(pool_ids_after - pool_ids_before)

    history_record = {
        "schema_version": 1,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "repair_id": repair_set_id,
        "manifest": str(manifest_path),
        "manifest_sha256": manifest_sha,
        "base_match_sheet_sha256": input_sha,
        "output_match_sheet": str(output),
        "output_match_sheet_sha256": output_sha,
        "snapshot": str(snapshot),
        "candidate_pool": str(candidate_pool) if candidate_pool else "",
        "candidate_pool_input_sha256": pool_input_sha,
        "candidate_pool_output_sha256": pool_output_sha,
        "candidate_pool_snapshot": str(pool_snapshot) if pool_snapshot else "",
        "added_candidate_ids": added_candidate_ids,
        "changed_line_ids": sorted(repair_ids),
        "repairs": applied,
    }
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(history_record, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())

    opening_review = (
        manifest.get("opening_review")
        or review_data.get("opening_review")
        or {"status": "PENDING"}
    )
    ending_review = (
        manifest.get("ending_review")
        or review_data.get("ending_review")
        or {"status": "PENDING"}
    )
    sequence_ready = all(
        isinstance(section, dict)
        and str(section.get("status", "")).upper() == "PASS"
        for section in (opening_review, ending_review)
    )
    result = {
        "schema_version": 2,
        "status": "PASS",
        "repair_id": repair_set_id,
        "repair_manifest_path": str(manifest_path),
        "repair_manifest_sha256": manifest_sha,
        "before_match_sheet_path": str(snapshot),
        "before_match_sheet_sha256": input_sha,
        "after_match_sheet_path": str(output),
        "after_match_sheet_sha256": output_sha,
        "before_candidate_pool_path": str(pool_snapshot) if pool_snapshot else "",
        "before_candidate_pool_sha256": pool_input_sha,
        "after_candidate_pool_path": str(candidate_pool) if candidate_pool else "",
        "after_candidate_pool_sha256": pool_output_sha,
        "review_manifest_path": str(review_manifest) if review_manifest else "",
        "review_manifest_sha256": review_manifest_sha,
        "source_manifest_path": str(source_manifest),
        "source_manifest_sha256": source_manifest_sha,
        "changed_cue_ids": sorted(repair_ids),
        "added_candidate_ids": added_candidate_ids,
        "repairs": audit_repairs,
        "unresolved_after": [],
        "workflow_ready": sequence_ready,
        "opening_review": opening_review,
        "ending_review": ending_review,
        "history_path": str(history_path),
    }
    if args.output_json:
        atomic_json(args.output_json.expanduser().resolve(), result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
