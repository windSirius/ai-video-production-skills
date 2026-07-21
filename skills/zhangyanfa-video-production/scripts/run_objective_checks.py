#!/usr/bin/env python3
"""Run a whitelist of objective file, caption, TSV, JSON, and media checks."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any


SUPPORTED_TYPES = {
    "file_exists",
    "file_nonempty",
    "glob_count",
    "json_fields",
    "text_contains",
    "tsv_status",
    "tsv_row_count_match",
    "mission_flow_coverage",
    "srt_no_adjacent_duplicates",
    "bgm_sources_within_root",
    "media_probe",
}
DEFAULT_MUSIC_SOURCE_ROOT = str(
    Path(os.environ.get("AI_VIDEO_MUSIC_ROOT", Path.home() / "Music")).expanduser().resolve()
)


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


def run_check(root: Path, check: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    check_type = check.get("type")
    if check_type not in SUPPORTED_TYPES:
        return False, f"unsupported check type: {check_type}", {}

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

    if check_type == "bgm_sources_within_root":
        data = json.loads(path.read_text(encoding="utf-8"))
        sections_field = check.get("sections_field", "sections")
        source_field = check.get("source_field", "source")
        sections = dotted_value(data, sections_field)
        source_root = Path(check.get("source_root", DEFAULT_MUSIC_SOURCE_ROOT)).expanduser().resolve()
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

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return False, "ffprobe not found", {}
    completed = subprocess.run(
        [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return False, completed.stderr.strip() or "ffprobe failed", {}
    probe = json.loads(completed.stdout)
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
