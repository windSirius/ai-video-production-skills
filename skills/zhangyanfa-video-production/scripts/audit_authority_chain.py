#!/usr/bin/env python3
"""Fail closed when one episode has split or stale production authorities."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


FINAL_STATES = {"accepted", "frozen"}
TIME_BOUND_KINDS = {
    "a_track",
    "b_track",
    "c_track",
    "picture_master",
    "auxiliary_track",
    "bgm_master",
    "final_export",
}
FULL_FRAME_KINDS = {"a_track", "picture_master", "final_export"}
SRT_TIMING_RE = re.compile(
    r"(?m)^(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s+-->\s+"
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_status(value: object) -> str:
    return str(value or "").strip().lower()


def resolve_inside(root: Path, value: object, label: str, errors: list[str]) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}.path is missing")
        return None
    candidate = Path(value).expanduser()
    candidate = (candidate if candidate.is_absolute() else root / candidate).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        errors.append(f"{label}.path must be a stable file inside the run directory: {candidate}")
        return None
    if not candidate.is_file():
        errors.append(f"{label}.path is not an existing file: {candidate}")
        return None
    return candidate


def positive_int(value: object, label: str, errors: list[str]) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        errors.append(f"{label} must be a positive integer")
        return None
    return value


def srt_summary(path: Path, fps: int) -> dict[str, int]:
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    matches = list(SRT_TIMING_RE.finditer(text))
    if not matches:
        raise ValueError("subtitle has no valid SRT timing rows")
    end = matches[-1]
    hours, minutes, seconds, milliseconds = (int(value) for value in end.groups()[4:])
    end_ms = ((hours * 60 + minutes) * 60 + seconds) * 1000 + milliseconds
    return {
        "cue_count": len(matches),
        "final_end_ms": end_ms,
        "final_end_frame": math.ceil(end_ms * fps / 1000),
    }


def audio_summary(path: Path, fps: int) -> dict[str, float | int]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe is required to bind the actual narration duration")
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffprobe failed for narration")
    try:
        duration_seconds = float(json.loads(completed.stdout)["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("ffprobe did not return a valid narration duration") from exc
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise RuntimeError("narration duration must be positive and finite")
    return {
        "duration_seconds": duration_seconds,
        "duration_frame_count": math.ceil(duration_seconds * fps - 1e-6),
    }


def verify_frozen_file(
    root: Path,
    label: str,
    entry: object,
    errors: list[str],
    *,
    allow_provisional: bool,
) -> tuple[Path | None, str]:
    if not isinstance(entry, dict):
        errors.append(f"authorities.{label} must be an object")
        return None, ""
    state = normalized_status(entry.get("status"))
    allowed_states = {"frozen"} | ({"provisional"} if allow_provisional else set())
    if state not in allowed_states:
        errors.append(
            f"authorities.{label}.status={state or '<missing>'}; expected frozen"
            + (" or provisional" if allow_provisional else "")
        )
    path = resolve_inside(root, entry.get("path"), f"authorities.{label}", errors)
    expected_sha = str(entry.get("sha256") or "").strip().lower()
    if not expected_sha:
        errors.append(f"authorities.{label}.sha256 is missing")
    actual_sha = sha256_file(path) if path else ""
    if expected_sha and actual_sha and expected_sha != actual_sha:
        errors.append(
            f"authorities.{label}.sha256 is stale: declared {expected_sha}, actual {actual_sha}"
        )
    return path, actual_sha


def audit_authority_bundle(
    root: Path,
    bundle_path: Path,
    *,
    require_descendants: set[str] | None = None,
    allow_provisional: bool = False,
) -> dict[str, Any]:
    root = root.expanduser().resolve()
    bundle_path = bundle_path.expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    require_descendants = require_descendants or set()

    if not bundle_path.is_file():
        return {
            "ok": False,
            "bundle": str(bundle_path),
            "errors": [f"authority bundle does not exist: {bundle_path}"],
            "warnings": [],
        }
    try:
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "bundle": str(bundle_path),
            "errors": [f"cannot read authority bundle: {exc}"],
            "warnings": [],
        }
    if not isinstance(bundle, dict):
        errors.append("authority bundle root must be an object")
        bundle = {}

    if bundle.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    bundle_state = normalized_status(bundle.get("status"))
    allowed_bundle_states = {"frozen"} | ({"provisional"} if allow_provisional else set())
    if bundle_state not in allowed_bundle_states:
        errors.append(
            f"status={bundle_state or '<missing>'}; expected frozen"
            + (" or provisional" if allow_provisional else "")
        )

    delivery = bundle.get("delivery_spec")
    if not isinstance(delivery, dict):
        errors.append("delivery_spec must be an object")
        delivery = {}
    width = positive_int(delivery.get("width"), "delivery_spec.width", errors)
    height = positive_int(delivery.get("height"), "delivery_spec.height", errors)
    fps = positive_int(delivery.get("fps"), "delivery_spec.fps", errors)
    target_frames = positive_int(
        delivery.get("target_frame_count"), "delivery_spec.target_frame_count", errors
    )

    authorities = bundle.get("authorities")
    if not isinstance(authorities, dict):
        errors.append("authorities must be an object")
        authorities = {}
    _script_path, script_sha = verify_frozen_file(
        root, "script", authorities.get("script"), errors, allow_provisional=allow_provisional
    )
    narration_path, narration_sha = verify_frozen_file(
        root,
        "narration",
        authorities.get("narration"),
        errors,
        allow_provisional=allow_provisional,
    )
    subtitle_path, subtitle_sha = verify_frozen_file(
        root,
        "subtitle",
        authorities.get("subtitle"),
        errors,
        allow_provisional=allow_provisional,
    )

    narration = authorities.get("narration") if isinstance(authorities.get("narration"), dict) else {}
    subtitle = authorities.get("subtitle") if isinstance(authorities.get("subtitle"), dict) else {}
    if not allow_provisional:
        if normalized_status(narration.get("lexical_status")) != "pass":
            errors.append("authorities.narration.lexical_status must be pass")
        if normalized_status(narration.get("human_audition_status")) != "pass":
            errors.append("authorities.narration.human_audition_status must be pass")
        if normalized_status(subtitle.get("human_approval_status")) != "pass":
            errors.append("authorities.subtitle.human_approval_status must be pass")

    narration_summary: dict[str, float | int] = {}
    if narration_path and fps:
        try:
            narration_summary = audio_summary(narration_path, fps)
        except RuntimeError as exc:
            errors.append(f"authorities.narration is invalid: {exc}")
        else:
            declared_duration_frames = narration.get("duration_frame_count")
            actual_duration_frames = narration_summary["duration_frame_count"]
            if declared_duration_frames != actual_duration_frames:
                errors.append(
                    "authorities.narration.duration_frame_count="
                    f"{declared_duration_frames!r}, actual {actual_duration_frames}"
                )
            if target_frames and target_frames != actual_duration_frames:
                errors.append(
                    "delivery_spec.target_frame_count must equal the actual narration "
                    f"duration frame count ({actual_duration_frames})"
                )

    subtitle_summary: dict[str, int] = {}
    if subtitle_path and fps:
        try:
            subtitle_summary = srt_summary(subtitle_path, fps)
        except ValueError as exc:
            errors.append(f"authorities.subtitle is invalid: {exc}")
        else:
            declared_cues = subtitle.get("cue_count")
            if declared_cues != subtitle_summary["cue_count"]:
                errors.append(
                    "authorities.subtitle.cue_count="
                    f"{declared_cues!r}, actual {subtitle_summary['cue_count']}"
                )
            declared_end = subtitle.get("final_end_frame")
            if declared_end != subtitle_summary["final_end_frame"]:
                errors.append(
                    "authorities.subtitle.final_end_frame="
                    f"{declared_end!r}, actual {subtitle_summary['final_end_frame']}"
                )
            if target_frames:
                if subtitle_summary["final_end_frame"] > target_frames:
                    errors.append("subtitle ends after delivery_spec.target_frame_count")
                tail = target_frames - subtitle_summary["final_end_frame"]
                if subtitle.get("caption_tail_hold_frames", 0) != tail:
                    errors.append(
                        "authorities.subtitle.caption_tail_hold_frames must equal "
                        f"target_frame_count - final_end_frame ({tail})"
                    )

    descendants = bundle.get("downstream")
    if descendants is None:
        descendants = []
    if not isinstance(descendants, list):
        errors.append("downstream must be an array")
        descendants = []
    seen_ids: set[str] = set()
    final_ids: set[str] = set()
    descendant_results: list[dict[str, Any]] = []
    for index, item in enumerate(descendants):
        label = f"downstream[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        item_id = str(item.get("id") or "").strip()
        kind = str(item.get("kind") or "").strip()
        state = normalized_status(item.get("state"))
        if not item_id:
            errors.append(f"{label}.id is missing")
        elif item_id in seen_ids:
            errors.append(f"duplicate downstream id: {item_id}")
        seen_ids.add(item_id)
        if not kind:
            errors.append(f"{label}.kind is missing")
        is_final = state in FINAL_STATES
        if is_final:
            final_ids.add(item_id)
            if normalized_status(item.get("objective_status")) != "pass":
                errors.append(f"{label}.objective_status must be pass for state={state}")
            if normalized_status(item.get("human_status")) != "pass":
                errors.append(f"{label}.human_status must be pass for state={state}")
        elif item_id in require_descendants:
            errors.append(f"required descendant {item_id} is not accepted/frozen (state={state})")

        path = resolve_inside(root, item.get("path"), label, errors)
        expected_sha = str(item.get("sha256") or "").strip().lower()
        actual_sha = sha256_file(path) if path else ""
        if not expected_sha:
            errors.append(f"{label}.sha256 is missing")
        elif actual_sha and expected_sha != actual_sha:
            errors.append(f"{label}.sha256 is stale")

        bindings = item.get("bindings")
        if not isinstance(bindings, dict):
            errors.append(f"{label}.bindings must be an object")
            bindings = {}
        if script_sha and bindings.get("script_sha256") != script_sha:
            errors.append(f"{label}.bindings.script_sha256 does not match the frozen script")
        if kind in TIME_BOUND_KINDS:
            expected = {
                "narration_sha256": narration_sha,
                "subtitle_sha256": subtitle_sha,
                "fps": fps,
                "target_frame_count": target_frames,
            }
            for field, value in expected.items():
                if value and bindings.get(field) != value:
                    errors.append(f"{label}.bindings.{field} does not match the authority bundle")
        if kind in FULL_FRAME_KINDS:
            if width and bindings.get("width") != width:
                errors.append(f"{label}.bindings.width does not match delivery_spec.width")
            if height and bindings.get("height") != height:
                errors.append(f"{label}.bindings.height does not match delivery_spec.height")
        descendant_results.append(
            {"id": item_id, "kind": kind, "state": state, "sha256": actual_sha}
        )

    missing_required = sorted(require_descendants - final_ids)
    for item_id in missing_required:
        if item_id not in seen_ids:
            errors.append(f"required descendant is missing: {item_id}")

    if allow_provisional:
        warnings.append(
            "provisional authority accepted for planning/proxy work only; do not use this result "
            "to authorize a target-resolution master"
        )
    return {
        "ok": not errors,
        "bundle": str(bundle_path),
        "bundle_sha256": sha256_file(bundle_path),
        "delivery_spec": {
            "width": width,
            "height": height,
            "fps": fps,
            "target_frame_count": target_frames,
        },
        "authority_sha256": {
            "script": script_sha,
            "narration": narration_sha,
            "subtitle": subtitle_sha,
        },
        "narration": narration_summary,
        "subtitle": subtitle_summary,
        "descendants": descendant_results,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", help="Episode run directory")
    parser.add_argument(
        "--bundle", default="authority_bundle.json", help="Bundle path relative to run_dir"
    )
    parser.add_argument(
        "--require-descendant",
        action="append",
        default=[],
        help="Require an accepted/frozen downstream artifact ID; repeat as needed",
    )
    parser.add_argument(
        "--allow-provisional",
        action="store_true",
        help="Permit planning/proxy work before human release; never authorizes a full master",
    )
    parser.add_argument("--output", help="Optional JSON result path")
    args = parser.parse_args()

    root = Path(args.run_dir).expanduser().resolve()
    bundle_path = Path(args.bundle).expanduser()
    if not bundle_path.is_absolute():
        bundle_path = root / bundle_path
    result = audit_authority_bundle(
        root,
        bundle_path,
        require_descendants=set(args.require_descendant),
        allow_provisional=args.allow_provisional,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = Path(args.output).expanduser()
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
