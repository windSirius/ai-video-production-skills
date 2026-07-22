#!/usr/bin/env python3
"""Fail-closed transaction harness for the 障眼法 production pipeline.

The harness never clicks Jianying.  It grants exactly one mutation token, records
the pre-state, and accepts the mutation only after fresh evidence proves the
expected delta while protected state remains unchanged.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from run_objective_checks import run_check, run_plan


SCHEMA_VERSION = 1
MUSIC_SOURCE_ROOT = Path(
    os.environ.get("AI_VIDEO_MUSIC_ROOT") or (Path.home() / "Music")
).expanduser().resolve()
LIFECYCLES = {"ready", "prepared", "in_action", "repair_required", "blocked", "closing", "complete"}
LIVE_OBSERVATION_KEYS = (
    "app_bundle_version",
    "window_signature",
    "ui_recipe_profile",
    "ui_recipe_calibrated",
    "draft_name",
    "timeline_name",
    "timeline_count",
    "project_timecode",
    "caption_track_count",
    "caption_count",
    "narration_track_count",
    "narration_clip_count",
    "picture_track_count",
    "picture_clip_count",
    "bgm_track_count",
    "bgm_clip_count",
    "protected_tracks_locked",
    "authoritative_timeline",
)
LEDGER_FIELDS = (
    "batch_id",
    "phase",
    "assumption",
    "scope",
    "mutation",
    "unit_limit_key",
    "unit_count",
    "check_id",
    "expected",
    "measured",
    "status",
    "evidence",
    "waiver_reason",
    "superseded_by",
    "opened_at",
    "closed_at",
)


SAME_CORE = {
    "app_bundle_version": "same",
    "window_signature": "same",
    "ui_recipe_profile": "same",
    "ui_recipe_calibrated": "true",
    "draft_name": "same",
    "timeline_name": "same",
    "timeline_count": "same",
    "authoritative_timeline": "true",
}
SAME_ALL = {
    **SAME_CORE,
    "project_timecode": "same",
    "caption_track_count": "same",
    "caption_count": "same",
    "narration_track_count": "same",
    "narration_clip_count": "same",
    "picture_track_count": "same",
    "picture_clip_count": "same",
    "bgm_track_count": "same",
    "bgm_clip_count": "same",
    "protected_tracks_locked": "same",
}


ACTION_REGISTRY: dict[str, dict[str, Any]] = {
    "offline_artifact": {
        "mutation": "offline.artifact",
        "live": False,
        "recipe_id": "offline.objective-check.v1",
        "verifier": "objective_plan_check",
        "fresh_objective_target_required": True,
    },
    "adopt_verified_artifact": {
        "mutation": "none.adopt",
        "live": False,
        "recipe_id": "offline.adopt-objective-check.v1",
        "verifier": "objective_plan_check",
    },
    "append_narration_clip": {
        "mutation": "live.narration.append",
        "live": True,
        "recipe_id": "jianying.media-identity-quick-add.v1",
        "verifier": "live_state_delta",
        "media_required": True,
        "stable_media_required": True,
        "expect": {
            **SAME_CORE,
            "caption_track_count": "same",
            "caption_count": "same",
            "picture_track_count": "same",
            "picture_clip_count": "same",
            "bgm_track_count": "same",
            "bgm_clip_count": "same",
            "narration_track_count": "same",
            "narration_clip_count": "+1",
            "protected_tracks_locked": "same",
        },
        "required_expect": ["project_timecode"],
        "promotes_recipe_loop": True,
    },
    "append_narration_loop": {
        "mutation": "live.narration.append_loop",
        "live": True,
        "recipe_id": "jianying.media-identity-quick-add-loop.v1",
        "verifier": "live_state_delta_and_loop_log",
        "loop_required": True,
        "expect": {
            **SAME_CORE,
            "caption_track_count": "same",
            "caption_count": "same",
            "picture_track_count": "same",
            "picture_clip_count": "same",
            "bgm_track_count": "same",
            "bgm_clip_count": "same",
            "narration_track_count": "same",
            "protected_tracks_locked": "same",
        },
        "required_expect": ["project_timecode"],
        "requires_recipe_streak": "jianying.media-identity-quick-add.v1",
        "required_unit_limit_key": "narration_loop_items_per_batch",
    },
    "rename_unicode": {
        "mutation": "live.rename_unicode",
        "live": True,
        "recipe_id": "jianying.ax-or-clipboard-unicode.v1",
        "verifier": "live_state_delta",
        "expect": {
            "timeline_count": "same",
            "project_timecode": "same",
            "caption_track_count": "same",
            "caption_count": "same",
            "narration_clip_count": "same",
            "picture_clip_count": "same",
            "bgm_clip_count": "same",
            "protected_tracks_locked": "same",
        },
        "required_any_expect": ["draft_name", "timeline_name"],
    },
    "caption_replace_atomic": {
        "mutation": "live.caption.replace_atomic",
        "live": True,
        "recipe_id": "jianying.caption-export-remove-import-export.v1",
        "verifier": "live_state_delta_and_caption_transaction",
        "media_required": True,
        "stable_media_required": True,
        "expect": {
            **SAME_CORE,
            "project_timecode": "same",
            "caption_track_count": "same",
            "narration_track_count": "same",
            "narration_clip_count": "same",
            "picture_track_count": "same",
            "picture_clip_count": "same",
            "bgm_track_count": "same",
            "bgm_clip_count": "same",
            "protected_tracks_locked": "same",
        },
        "required_expect": ["caption_count"],
        "caption_transaction_required": True,
        "objective_check_required": True,
        "allowed_objective_types": ["srt_integrity"],
    },
    "apply_picture_master": {
        "mutation": "live.picture.replace",
        "live": True,
        "recipe_id": "jianying.equal-duration-replace-clip.v1",
        "verifier": "live_state_delta",
        "media_required": True,
        "stable_media_required": True,
        "timing_contract_required": True,
        "expect": {
            **SAME_CORE,
            "project_timecode": "same",
            "caption_track_count": "same",
            "caption_count": "same",
            "narration_track_count": "same",
            "narration_clip_count": "same",
            "picture_track_count": "same",
            "picture_clip_count": "same",
            "bgm_track_count": "same",
            "bgm_clip_count": "same",
            "protected_tracks_locked": "same",
        },
        "required_expect": ["visible_picture_filename"],
    },
    "apply_bgm_master": {
        "mutation": "live.bgm.apply",
        "live": True,
        "recipe_id": "jianying.music-provenance-quick-add.v1",
        "verifier": "live_state_delta",
        "media_required": True,
        "stable_media_required": True,
        "timing_contract_required": True,
        "bgm_manifest_required": True,
        "expect": {
            **SAME_CORE,
            "project_timecode": "same",
            "caption_track_count": "same",
            "caption_count": "same",
            "narration_track_count": "same",
            "narration_clip_count": "same",
            "picture_track_count": "same",
            "picture_clip_count": "same",
            "bgm_track_count": "same",
            "bgm_clip_count": "+1",
            "protected_tracks_locked": "same",
        },
    },
    "align_fullspan_tail": {
        "mutation": "live.fullspan.align_tail",
        "live": True,
        "recipe_id": "jianying.single-split-delete-tail.v1",
        "verifier": "live_state_delta",
        "timing_contract_required": True,
        "expect": {
            **SAME_CORE,
            "caption_track_count": "same",
            "caption_count": "same",
            "narration_track_count": "same",
            "narration_clip_count": "same",
            "picture_track_count": "same",
            "picture_clip_count": "same",
            "bgm_track_count": "same",
            "bgm_clip_count": "same",
            "protected_tracks_locked": "same",
        },
        "required_expect": ["project_timecode"],
        "max_successes_per_run": 1,
    },
    "cleanup_extra_timelines": {
        "mutation": "live.timeline.cleanup",
        "live": True,
        "recipe_id": "jianying.delete-nonauthoritative-timeline.v1",
        "verifier": "live_state_delta",
        "expect": {
            "draft_name": "same",
            "timeline_name": "same",
            "project_timecode": "same",
            "caption_track_count": "same",
            "caption_count": "same",
            "narration_clip_count": "same",
            "picture_clip_count": "same",
            "bgm_clip_count": "same",
            "protected_tracks_locked": "same",
            "timeline_count": "1",
        },
    },
    "caption_canonical_export": {
        "mutation": "live.caption.export_only",
        "live": True,
        "recipe_id": "jianying.caption-only-export.v1",
        "verifier": "live_state_delta",
        "expect": SAME_ALL,
        "objective_check_required": True,
        "allowed_objective_types": ["srt_integrity"],
    },
    "live_qa_capture": {
        "mutation": "live.qa.capture",
        "live": True,
        "recipe_id": "jianying.open-middle-final-evidence.v1",
        "verifier": "live_state_delta",
        "expect": SAME_ALL,
        "minimum_evidence": 3,
        "objective_check_required": True,
        "allowed_objective_types": ["image_evidence_set"],
    },
    "save_reopen_verify": {
        "mutation": "live.persistence.reopen",
        "live": True,
        "recipe_id": "jianying.save-home-reopen-verify.v1",
        "verifier": "live_state_delta",
        "expect": {**SAME_ALL, "reopened": "true"},
    },
}

FINAL_ACTION_ORDER = (
    "cleanup_extra_timelines",
    "caption_canonical_export",
    "live_qa_capture",
    "save_reopen_verify",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


@contextmanager
def run_lock(root: Path) -> Iterator[None]:
    lock_path = root / "harness/lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def append_event(root: Path, state: dict[str, Any], kind: str, **payload: Any) -> None:
    state["event_seq"] = int(state.get("event_seq", 0)) + 1
    event = {"seq": state["event_seq"], "at": utc_now(), "kind": kind, **payload}
    path = root / "harness/events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"invalid {label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return value


def fingerprint(path: Path, strong: bool = True) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    stat = resolved.stat()
    result = {"path": str(resolved), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    if strong and resolved.is_file():
        result["sha256"] = sha256_file(resolved)
    return result


def initial_state(root: Path, phase: str) -> dict[str, Any]:
    contract = root / "request_contract.json"
    plan = root / "verification_plan.json"
    manifest = root / "run_manifest.json"
    created = utc_now()
    run_id = hashlib.sha256(f"{root}|{created}".encode("utf-8")).hexdigest()[:20]
    return {
        "schema_version": SCHEMA_VERSION,
        "state_revision": 1,
        "run_id": run_id,
        "run_dir": str(root),
        "lifecycle": "ready",
        "phase": phase,
        "contract_fingerprint": fingerprint(contract),
        "verification_plan_fingerprint": fingerprint(plan),
        "manifest_path": str(manifest),
        "next_action": None,
        "open_action": None,
        "last_good_checkpoint": None,
        "budgets": {
            "limits": {"same_failure": 2, "phase_failures": 3, "run_failures": 6},
            "phase_failures": {},
            "run_failures": 0,
            "fingerprints": {},
        },
        "recipe_success_streak": {},
        "action_success_count": {},
        "completed_actions": [],
        "sealed_phases": {},
        "blocked": None,
        "event_seq": 0,
        "created_at": created,
        "updated_at": created,
    }


def validate_state(root: Path, state: dict[str, Any]) -> None:
    if state.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported harness schema: {state.get('schema_version')}")
    if state.get("run_dir") != str(root):
        raise ValueError("harness run_dir does not match the requested run")
    if state.get("lifecycle") not in LIFECYCLES:
        raise ValueError(f"invalid lifecycle: {state.get('lifecycle')}")
    if state.get("lifecycle") == "in_action" and not state.get("open_action"):
        raise ValueError("in_action state requires open_action")
    if state.get("open_action") and state.get("lifecycle") not in {"prepared", "in_action", "repair_required", "blocked"}:
        raise ValueError("open_action is inconsistent with lifecycle")


def load_state(root: Path) -> dict[str, Any]:
    path = root / "harness/state.json"
    if not path.exists():
        raise ValueError(f"missing harness state; run: {Path(__file__).name} init {root}")
    state = read_json(path, "harness state")
    validate_state(root, state)
    return state


def save_state(root: Path, state: dict[str, Any]) -> None:
    state["state_revision"] = int(state.get("state_revision", 0)) + 1
    state["updated_at"] = utc_now()
    atomic_json(root / "harness/state.json", state)


def pending_action_path(root: Path) -> Path:
    return root / "harness/pending_action.json"


def fingerprint_matches(saved: dict[str, Any]) -> bool:
    path = Path(saved.get("path", ""))
    if not path.is_file():
        return False
    current = fingerprint(path, strong=False)
    if current["size"] != saved.get("size") or current["mtime_ns"] != saved.get("mtime_ns"):
        return sha256_file(path) == saved.get("sha256")
    return True


def drift_reasons(state: dict[str, Any]) -> list[str]:
    reasons = []
    if not fingerprint_matches(state.get("contract_fingerprint", {})):
        reasons.append("request_contract drift")
    if not fingerprint_matches(state.get("verification_plan_fingerprint", {})):
        reasons.append("verification_plan drift")
    for phase, seal in state.get("sealed_phases", {}).items():
        for item in seal.get("artifacts", []):
            if not fingerprint_matches(item):
                reasons.append(f"sealed artifact drift: {phase}: {item.get('path')}")
    return reasons


def ensure_no_drift(state: dict[str, Any]) -> None:
    reasons = drift_reasons(state)
    if reasons:
        raise ValueError("; ".join(reasons))


def read_ledger(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_ledger(path: Path, rows: list[dict[str, str]]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS, delimiter="\t", extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in LEDGER_FIELDS})
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def update_ledger(root: Path, batch_id: str, **updates: str) -> None:
    path = root / "batch_ledger.tsv"
    rows = read_ledger(path)
    found = False
    for row in rows:
        if row.get("batch_id") == batch_id:
            row.update(updates)
            found = True
            break
    if not found:
        raise ValueError(f"batch not found in ledger: {batch_id}")
    write_ledger(path, rows)


def append_ledger(root: Path, row: dict[str, str]) -> None:
    path = root / "batch_ledger.tsv"
    rows = read_ledger(path)
    if any(existing.get("batch_id") == row.get("batch_id") for existing in rows):
        raise ValueError(f"duplicate batch id: {row.get('batch_id')}")
    rows.append(row)
    write_ledger(path, rows)


def next_batch_id(root: Path) -> str:
    numbers = []
    for row in read_ledger(root / "batch_ledger.tsv"):
        batch_id = row.get("batch_id", "")
        if batch_id.startswith("H") and batch_id[1:].isdigit():
            numbers.append(int(batch_id[1:]))
    return f"H{max(numbers, default=0) + 1:04d}"


def parse_expectations(values: list[str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError(f"expectation must use FIELD=SPEC: {value}")
        field, spec = value.split("=", 1)
        field, spec = field.strip(), spec.strip()
        if not field or not spec:
            raise ValueError(f"invalid expectation: {value}")
        result[field] = spec
    return result


def load_observation(path: Path) -> dict[str, Any]:
    value = read_json(path, "live observation")
    missing = [field for field in LIVE_OBSERVATION_KEYS if field not in value]
    if missing:
        raise ValueError(f"live observation missing keys: {missing}")
    for field in LIVE_OBSERVATION_KEYS:
        if field.endswith("_count") and (not isinstance(value[field], int) or value[field] < 0):
            raise ValueError(f"live observation {field} must be a nonnegative integer")
    if not value["draft_name"] or not value["timeline_name"] or not value["project_timecode"]:
        raise ValueError("live observation requires draft_name, timeline_name, and project_timecode")
    for field in ("app_bundle_version", "window_signature", "ui_recipe_profile"):
        if not isinstance(value[field], str) or not value[field].strip():
            raise ValueError(f"live observation requires nonempty {field}")
    if value["ui_recipe_calibrated"] is not True:
        raise ValueError("live observation requires ui_recipe_calibrated=true")
    if value["authoritative_timeline"] is not True:
        raise ValueError("live observation requires authoritative_timeline=true")
    return value


def save_checkpoint(root: Path, batch_id: str, label: str, observation: dict[str, Any], evidence: list[Path]) -> dict[str, Any]:
    directory = root / f"harness/checkpoints/{batch_id}"
    directory.mkdir(parents=True, exist_ok=True)
    observation_path = directory / f"{label}.json"
    atomic_json(observation_path, observation)
    evidence_fingerprints = [fingerprint(path) for path in evidence]
    checkpoint = {
        "label": label,
        "observation": str(observation_path),
        "observation_sha256": sha256_file(observation_path),
        "evidence": evidence_fingerprints,
        "captured_at": utc_now(),
    }
    atomic_json(directory / f"{label}_checkpoint.json", checkpoint)
    return checkpoint


def parse_spec(spec: str) -> Any:
    lowered = spec.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return json.loads(spec)
    except json.JSONDecodeError:
        return spec


def compare_observations(before: dict[str, Any], after: dict[str, Any], expectations: dict[str, str]) -> list[str]:
    failures = []
    for field, spec in expectations.items():
        if field not in before and spec in {"same", "+1", "-1"}:
            failures.append(f"before observation missing {field}")
            continue
        if field not in after:
            failures.append(f"after observation missing {field}")
            continue
        actual = after[field]
        if spec == "same":
            expected = before[field]
        elif spec.startswith("+") and spec[1:].isdigit():
            expected = before[field] + int(spec[1:])
        elif spec.startswith("-") and spec[1:].isdigit():
            expected = before[field] - int(spec[1:])
        else:
            expected = parse_spec(spec)
        if actual != expected:
            failures.append(f"{field}={actual!r}, expected {expected!r} ({spec})")
    return failures


def find_plan_check(root: Path, check_id: str) -> dict[str, Any] | None:
    plan = read_json(root / "verification_plan.json", "verification plan")
    return next((check for check in plan.get("checks", []) if check.get("id") == check_id), None)


def validate_objective_binding(check: dict[str, Any], mutation: str) -> None:
    observed = check.get("observes_mutations", [])
    if mutation not in observed:
        raise ValueError(f"check {check.get('id')} does not declare observes_mutations={mutation}")
    targets = check.get("observed_targets", [])
    if not isinstance(targets, list) or not targets:
        raise ValueError(f"check {check.get('id')} requires nonempty observed_targets")
    forbidden = {"batch_ledger.tsv", "run_manifest.json", "harness/state.json", "harness/events.jsonl"}
    if any(str(target) in forbidden for target in targets):
        raise ValueError(f"check {check.get('id')} is self-referential and cannot prove a production action")


def media_identity(path: Path) -> dict[str, Any]:
    if not path.expanduser().is_absolute():
        raise ValueError(f"media identity requires an absolute path: {path}")
    expanded = path.expanduser()
    resolved = expanded.resolve()
    if not resolved.is_file():
        raise ValueError(f"media is not a regular file: {resolved}")
    result = fingerprint(resolved)
    result["requested_path"] = str(expanded)
    result["was_symlink"] = expanded.is_symlink()
    result["basename"] = resolved.name
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        completed = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(resolved)],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            try:
                result["duration"] = float(json.loads(completed.stdout)["format"]["duration"])
            except Exception:
                pass
    if resolved.suffix.lower() not in {".srt", ".ass", ".txt"} and not result.get("duration", 0) > 0:
        raise ValueError(f"media identity requires a positive probed duration: {resolved}")
    return result


def validate_stable_media(identity: dict[str, Any]) -> None:
    resolved_media = Path(identity["path"])
    temporary_roots = (Path("/tmp"), Path("/private/tmp"), Path("/var/folders"))
    if identity.get("was_symlink") or any(
        resolved_media == temporary_root or temporary_root in resolved_media.parents
        for temporary_root in temporary_roots
    ):
        raise ValueError("live media must be a stable non-symlink regular file outside temporary directories")


def validate_timing_contract(path: Path) -> dict[str, Any]:
    value = read_json(path, "timing contract")
    for field in ("fps", "target_frame_count", "target_timecode", "target_seconds"):
        if field not in value:
            raise ValueError(f"timing contract missing {field}")
    fps = float(value["fps"])
    frames = int(value["target_frame_count"])
    seconds = float(value["target_seconds"])
    if fps <= 0 or frames <= 0 or abs(frames / fps - seconds) > 1 / fps:
        raise ValueError("timing contract frame/seconds values disagree by more than one frame")
    return value


def validate_bgm_manifest(root: Path) -> dict[str, Any]:
    path = root / "audio/bgm_manifest.json"
    check = {
        "id": "harness_bgm_sources_within_music",
        "type": "bgm_sources_within_root",
        "path": str(path),
        "source_root": str(MUSIC_SOURCE_ROOT),
    }
    passed, detail, metrics = run_check(root, check)
    if not passed:
        raise ValueError(f"BGM provenance failed: {detail}")
    return metrics


def validate_caption_transaction(path: Path, expected_count: Any) -> dict[str, Any]:
    value = read_json(path, "caption transaction")
    required_events = ["raw_backup_exported", "raw_track_removed", "semantic_imported", "canonical_exported"]
    if value.get("events") != required_events:
        raise ValueError(f"caption transaction events must equal {required_events}")
    if value.get("caption_track_counts") != [1, 0, 1]:
        raise ValueError("caption transaction must prove track counts 1 -> 0 -> 1")
    if int(value.get("exact_overlap_count", -1)) != 0:
        raise ValueError("caption transaction exact_overlap_count must be zero")
    if int(value.get("final_caption_count", -1)) != int(expected_count):
        raise ValueError("caption transaction final count does not match expected caption_count")
    for field in ("raw_backup", "canonical_export"):
        candidate = Path(value.get(field, "")).expanduser()
        if not candidate.is_absolute():
            candidate = path.parent / candidate
        if not candidate.is_file() or candidate.stat().st_size == 0:
            raise ValueError(f"caption transaction missing nonempty {field}: {candidate}")
    return value


def validate_loop_manifest(path: Path, unit_count: int) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or len(value) != unit_count:
        raise ValueError(f"loop manifest must contain exactly {unit_count} items")
    for index, row in enumerate(value, start=1):
        if not isinstance(row, dict) or not row.get("source") or not row.get("expected_end"):
            raise ValueError(f"loop manifest row {index} requires source and expected_end")
        identity = media_identity(Path(row["source"]))
        validate_stable_media(identity)
    return value


def validate_loop_results(path: Path, manifest: list[dict[str, Any]]) -> dict[str, Any]:
    value = read_json(path, "loop results")
    rows = value.get("items", [])
    if not isinstance(rows, list) or len(rows) != len(manifest):
        raise ValueError("loop results count does not match loop manifest")
    for index, (expected, actual) in enumerate(zip(manifest, rows), start=1):
        if actual.get("source_basename") != Path(expected["source"]).name:
            raise ValueError(f"loop row {index} selected the wrong media")
        if actual.get("actual_end") != expected["expected_end"] or actual.get("pass") is not True:
            raise ValueError(f"loop row {index} failed cumulative-end verification")
    return value


def evidence_paths(values: list[str] | None, minimum: int = 1) -> list[Path]:
    paths = [Path(value).expanduser().resolve() for value in values or []]
    if len(paths) < minimum:
        raise ValueError(f"at least {minimum} fresh evidence file(s) required")
    for path in paths:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"evidence is missing or empty: {path}")
    return paths


def fresh_evidence(paths: list[Path], started_at: str) -> None:
    started = datetime.fromisoformat(started_at).timestamp()
    stale = [str(path) for path in paths if path.stat().st_mtime + 1 < started]
    if stale:
        raise ValueError(f"evidence predates ACTION_BEGUN: {stale}")


def make_token(state: dict[str, Any], action_key: str, attempt: int, checkpoint_digest: str) -> str:
    payload = f"{state['run_id']}|{state['state_revision']}|{action_key}|{attempt}|{checkpoint_digest}"
    return f"{action_key}-a{attempt}-{hashlib.sha256(payload.encode()).hexdigest()[:10]}"


def status_payload(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    pending_path = pending_action_path(root)
    if pending_path.exists():
        pending = read_json(pending_path, "pending action journal")
        open_action = state.get("open_action")
        if not open_action:
            return {
                "lifecycle": "blocked",
                "phase": state["phase"],
                "next_action": {
                    "kind": "recover_pending_transaction",
                    "instruction": "Run harness.py recover; do not perform a production mutation.",
                },
            }
        if pending.get("batch_id") != open_action.get("batch_id") or pending.get("token") != open_action.get("token"):
            return {
                "lifecycle": "blocked",
                "phase": state["phase"],
                "next_action": {"kind": "recover_journal_mismatch", "instruction": "Pending journal and state disagree; run recover."},
            }
        ledger_row = next(
            (row for row in read_ledger(root / "batch_ledger.tsv") if row.get("batch_id") == pending.get("batch_id")),
            None,
        )
        expected_lifecycle = {
            "prepared": "prepared",
            "in_action": "in_action",
            "open_repair": "repair_required",
            "blocked": "blocked",
        }.get(ledger_row.get("status") if ledger_row else None)
        if ledger_row and ledger_row.get("status") in {"pass", "waived"}:
            return {
                "lifecycle": "blocked",
                "phase": state["phase"],
                "next_action": {"kind": "recover_closed_ledger_action", "instruction": "Ledger closed before state commit; run recover."},
            }
        if expected_lifecycle and expected_lifecycle != state.get("lifecycle"):
            return {
                "lifecycle": "blocked",
                "phase": state["phase"],
                "next_action": {"kind": "recover_state_ledger_mismatch", "instruction": "Ledger and state disagree; run recover."},
            }
    elif state.get("open_action"):
        return {
            "lifecycle": "blocked",
            "phase": state["phase"],
            "next_action": {"kind": "recover_missing_journal", "instruction": "Open action lacks its journal; run recover."},
        }
    drift = drift_reasons(state)
    if drift:
        return {
            "lifecycle": "blocked",
            "phase": state["phase"],
            "next_action": {"kind": "repair_contract_drift", "instruction": "; ".join(drift)},
        }
    lifecycle = state["lifecycle"]
    action = state.get("open_action")
    if lifecycle == "complete":
        next_action = {"kind": "none", "instruction": "Run is complete; do not mutate it."}
    elif lifecycle == "blocked":
        next_action = {"kind": "request_user_decision", "instruction": state.get("blocked", {}).get("reason", "blocked")}
    elif lifecycle == "prepared":
        next_action = {
            "kind": "begin",
            "token": action["token"],
            "instruction": f"Begin only {action['action_key']} using recipe {action['recipe_id']}.",
            "command": f"python3 {shlex.quote(str(Path(__file__)))} begin {shlex.quote(str(root))} --token {action['token']}",
        }
    elif lifecycle == "in_action":
        next_action = {
            "kind": "inspect_pending_action",
            "token": action["token"],
            "instruction": "Do not repeat the mutation. Inspect current state, then verify or fail this token.",
        }
    elif lifecycle == "repair_required":
        next_action = {
            "kind": "retry_once",
            "token": action["token"],
            "instruction": f"Retry the same registered recipe once; do not invent a coordinate or drag variant: {action['recipe_id']}",
            "command": f"python3 {shlex.quote(str(Path(__file__)))} begin {shlex.quote(str(root))} --token {action['token']}",
        }
    else:
        next_action = {
            "kind": "prepare",
            "instruction": f"Prepare exactly one registered action in phase {state['phase']}; no production mutation is authorized yet.",
            "allowed_action_keys": sorted(ACTION_REGISTRY),
        }
    return {"lifecycle": lifecycle, "phase": state["phase"], "state_revision": state["state_revision"], "next_action": next_action}


def command_init(args: argparse.Namespace) -> int:
    root = Path(args.run_dir).expanduser().resolve()
    for required in ("request_contract.json", "verification_plan.json", "run_manifest.json", "batch_ledger.tsv"):
        if not (root / required).exists():
            raise ValueError(f"cannot initialize harness; missing {required}")
    state_path = root / "harness/state.json"
    with run_lock(root):
        if state_path.exists():
            state = load_state(root)
            print(json.dumps(status_payload(root, state), ensure_ascii=False, indent=2))
            return 0
        manifest = read_json(root / "run_manifest.json", "run manifest")
        artifacts = manifest.setdefault("artifacts", {})
        artifacts.setdefault("harness_state", str(state_path))
        artifacts.setdefault("harness_events", str(root / "harness/events.jsonl"))
        artifacts.setdefault("harness_close_result", str(root / "harness/close_result.json"))
        atomic_json(root / "run_manifest.json", manifest)
        phase = args.phase or str(manifest.get("current_phase") or "intake")
        state = initial_state(root, phase)
        append_event(root, state, "HARNESS_INITIALIZED", phase=phase)
        atomic_json(state_path, state)
    print(state_path)
    return 0


def command_status(args: argparse.Namespace) -> int:
    root = Path(args.run_dir).expanduser().resolve()
    state = load_state(root)
    print(json.dumps(status_payload(root, state), ensure_ascii=False, indent=2))
    return 1 if drift_reasons(state) or state["lifecycle"] == "blocked" else 0


def command_prepare(args: argparse.Namespace) -> int:
    root = Path(args.run_dir).expanduser().resolve()
    with run_lock(root):
        state = load_state(root)
        if state["lifecycle"] != "ready" or state.get("open_action"):
            raise ValueError(f"prepare requires ready state with no open action; current={state['lifecycle']}")
        if pending_action_path(root).exists():
            raise ValueError("pending action journal exists; run recover before preparing another action")
        ensure_no_drift(state)
        if args.action_key not in ACTION_REGISTRY:
            raise ValueError(f"unregistered action key: {args.action_key}")
        spec = ACTION_REGISTRY[args.action_key]
        if args.recipe_id != spec["recipe_id"]:
            raise ValueError(f"recipe mismatch; required {spec['recipe_id']}")
        contract = read_json(root / "request_contract.json", "request contract")
        limits = contract.get("unit_limits", {})
        if args.unit_limit_key not in limits:
            raise ValueError(f"unknown unit limit: {args.unit_limit_key}")
        required_limit_key = spec.get("required_unit_limit_key")
        if required_limit_key and args.unit_limit_key != required_limit_key:
            raise ValueError(f"{args.action_key} requires unit limit key {required_limit_key}")
        if args.unit_count <= 0 or args.unit_count > int(limits[args.unit_limit_key]):
            raise ValueError(f"unit_count={args.unit_count} exceeds {args.unit_limit_key}={limits[args.unit_limit_key]}")
        successes = int(state.get("action_success_count", {}).get(args.action_key, 0))
        if spec.get("max_successes_per_run") is not None and successes >= int(spec["max_successes_per_run"]):
            raise ValueError(f"{args.action_key} may succeed at most once per run")

        expectations = dict(spec.get("expect", {}))
        if spec["live"]:
            for field, expectation in {
                "app_bundle_version": "same",
                "window_signature": "same",
                "ui_recipe_profile": "same",
                "ui_recipe_calibrated": "true",
                "authoritative_timeline": "true",
            }.items():
                expectations.setdefault(field, expectation)
        expectations.update(parse_expectations(args.expect))
        for field in spec.get("required_expect", []):
            if field not in expectations:
                raise ValueError(f"{args.action_key} requires --expect {field}=VALUE")
        required_any = spec.get("required_any_expect", [])
        if required_any and not any(field in parse_expectations(args.expect) for field in required_any):
            raise ValueError(f"{args.action_key} requires an explicit expectation for one of {required_any}")

        check_id = args.check_id
        objective_check = None
        if spec["live"]:
            if check_id != "harness_live_state_delta":
                raise ValueError("live mutation check_id must be harness_live_state_delta; unrelated file checks cannot prove UI state")
        else:
            objective_check = find_plan_check(root, check_id)
            if not objective_check:
                raise ValueError(f"offline action requires a check_id in verification_plan.json: {check_id}")
            validate_objective_binding(objective_check, spec["mutation"])
        supplemental_objective_check = None
        if spec.get("objective_check_required"):
            if not args.objective_check_id:
                raise ValueError(f"{args.action_key} requires --objective-check-id")
            supplemental_objective_check = find_plan_check(root, args.objective_check_id)
            if not supplemental_objective_check:
                raise ValueError(f"objective check not found: {args.objective_check_id}")
            if supplemental_objective_check.get("type") not in spec.get("allowed_objective_types", []):
                raise ValueError(
                    f"{args.action_key} objective check must use one of {spec.get('allowed_objective_types', [])}"
                )
            validate_objective_binding(supplemental_objective_check, spec["mutation"])
        if args.optional:
            criterion_checks = {
                criterion.get("check_id")
                for criterion in contract.get("success_criteria", [])
                if isinstance(criterion, dict)
            }
            if check_id in criterion_checks or args.objective_check_id in criterion_checks:
                raise ValueError("an action bound to a required success criterion cannot be optional")

        batch_id = next_batch_id(root)
        pre_checkpoint = None
        media = None
        timing_contract = None
        bgm_provenance = None
        loop_manifest = None
        if spec["live"]:
            observation_path = Path(args.observation or "").expanduser().resolve()
            if not args.observation:
                raise ValueError("live mutation requires --observation PRE_STATE.json")
            observation = load_observation(observation_path)
            pre_evidence = evidence_paths(args.evidence, minimum=1)
            pre_checkpoint = save_checkpoint(root, batch_id, "before", observation, pre_evidence)
        if spec.get("media_required"):
            if not args.media:
                raise ValueError(f"{args.action_key} requires --media PATH")
            media = media_identity(Path(args.media))
            if spec.get("stable_media_required"):
                validate_stable_media(media)
        if spec.get("timing_contract_required"):
            if not args.timing_contract:
                raise ValueError(f"{args.action_key} requires --timing-contract PATH")
            timing_contract = validate_timing_contract(Path(args.timing_contract).expanduser().resolve())
        if spec.get("bgm_manifest_required"):
            bgm_provenance = validate_bgm_manifest(root)
        if spec.get("loop_required"):
            required_recipe = spec["requires_recipe_streak"]
            if int(state.get("recipe_success_streak", {}).get(required_recipe, 0)) < 2:
                raise ValueError("loop promotion requires two consecutive successful single-item recipe executions")
            if not args.loop_manifest:
                raise ValueError("loop action requires --loop-manifest PATH")
            loop_manifest = validate_loop_manifest(Path(args.loop_manifest).expanduser().resolve(), args.unit_count)
            expectations["narration_clip_count"] = f"+{args.unit_count}"

        checkpoint_digest = pre_checkpoint["observation_sha256"] if pre_checkpoint else canonical_digest(objective_check)
        token = make_token(state, args.action_key, 1, checkpoint_digest)
        ledger_check_id = check_id if not args.objective_check_id else f"{check_id}+{args.objective_check_id}"
        action = {
            "batch_id": batch_id,
            "token": token,
            "attempt": 1,
            "phase": state["phase"],
            "action_key": args.action_key,
            "mutation": spec["mutation"],
            "recipe_id": spec["recipe_id"],
            "verifier": spec["verifier"],
            "check_id": check_id,
            "ledger_check_id": ledger_check_id,
            "objective_check_id": args.objective_check_id,
            "assumption": args.assumption,
            "scope": args.scope,
            "unit_limit_key": args.unit_limit_key,
            "unit_count": args.unit_count,
            "optional": bool(args.optional),
            "expectations": expectations,
            "pre_checkpoint": pre_checkpoint,
            "media": media,
            "timing_contract": timing_contract,
            "bgm_provenance": bgm_provenance,
            "loop_manifest": loop_manifest,
            "prepared_at": utc_now(),
            "started_at": None,
        }
        atomic_json(pending_action_path(root), action)
        append_ledger(
            root,
            {
                "batch_id": batch_id,
                "phase": state["phase"],
                "assumption": args.assumption,
                "scope": args.scope,
                "mutation": spec["mutation"],
                "unit_limit_key": args.unit_limit_key,
                "unit_count": str(args.unit_count),
                "check_id": ledger_check_id,
                "expected": json.dumps(expectations, ensure_ascii=False, sort_keys=True),
                "measured": "",
                "status": "prepared",
                "evidence": "",
                "waiver_reason": "",
                "superseded_by": "",
                "opened_at": utc_now(),
                "closed_at": "",
            },
        )
        state["open_action"] = action
        state["next_action"] = {"kind": "begin", "token": token}
        state["lifecycle"] = "prepared"
        append_event(root, state, "ACTION_PREPARED", batch_id=batch_id, token=token, action_key=args.action_key)
        save_state(root, state)
    print(json.dumps(status_payload(root, state), ensure_ascii=False, indent=2))
    return 0


def command_begin(args: argparse.Namespace) -> int:
    root = Path(args.run_dir).expanduser().resolve()
    with run_lock(root):
        state = load_state(root)
        if state["lifecycle"] == "in_action":
            raise ValueError("action is already in progress; inspect it instead of repeating the mutation")
        if state["lifecycle"] not in {"prepared", "repair_required"}:
            raise ValueError(f"begin not allowed in lifecycle={state['lifecycle']}")
        ensure_no_drift(state)
        action = state.get("open_action") or {}
        if args.token != action.get("token"):
            raise ValueError("stale or foreign action token")
        action["started_at"] = utc_now()
        atomic_json(pending_action_path(root), action)
        state["lifecycle"] = "in_action"
        state["next_action"] = {"kind": "inspect_pending_action", "token": args.token}
        update_ledger(root, action["batch_id"], status="in_action")
        append_event(root, state, "ACTION_BEGUN", batch_id=action["batch_id"], token=args.token, attempt=action["attempt"])
        save_state(root, state)
    print(json.dumps(status_payload(root, state), ensure_ascii=False, indent=2))
    return 0


def command_skip(args: argparse.Namespace) -> int:
    root = Path(args.run_dir).expanduser().resolve()
    with run_lock(root):
        state = load_state(root)
        if state["lifecycle"] != "prepared":
            raise ValueError("skip is allowed only before an optional action begins")
        action = state.get("open_action") or {}
        if args.token != action.get("token"):
            raise ValueError("stale or foreign action token")
        if action.get("optional") is not True:
            raise ValueError("required actions cannot be waived")
        if args.authorized_by != "user":
            raise ValueError("skip requires explicit user authority")
        authorization = f"user-authorized:{utc_now()}"
        update_ledger(
            root,
            action["batch_id"],
            measured="not executed",
            status="waived",
            waiver_reason=args.reason,
            superseded_by=authorization,
            closed_at=utc_now(),
        )
        append_event(root, state, "OPTIONAL_ACTION_WAIVED", batch_id=action["batch_id"], reason=args.reason, authorization=authorization)
        state["open_action"] = None
        state["next_action"] = None
        state["lifecycle"] = "ready"
        save_state(root, state)
        pending_action_path(root).unlink(missing_ok=True)
    print(json.dumps(status_payload(root, state), ensure_ascii=False, indent=2))
    return 0


def close_action_as_failure(
    root: Path,
    state: dict[str, Any],
    reason_code: str,
    detail: str,
    evidence: list[Path],
    rolled_back: bool,
) -> None:
    action = state["open_action"]
    phase = action["phase"]
    pre_observation = read_json(Path(action["pre_checkpoint"]["observation"]), "pre observation") if action.get("pre_checkpoint") else {}
    fingerprint_key = "|".join(
        (
            action["action_key"],
            action["recipe_id"],
            str(pre_observation.get("app_bundle_version", "offline")),
            str(pre_observation.get("window_signature", "offline")),
            str(action.get("pre_checkpoint", {}).get("observation_sha256", "offline")),
            reason_code,
        )
    )
    budgets = state["budgets"]
    budgets["run_failures"] = int(budgets.get("run_failures", 0)) + 1
    phase_failures = budgets.setdefault("phase_failures", {})
    phase_failures[phase] = int(phase_failures.get(phase, 0)) + 1
    fingerprints = budgets.setdefault("fingerprints", {})
    fingerprints[fingerprint_key] = int(fingerprints.get(fingerprint_key, 0)) + 1
    state.setdefault("recipe_success_streak", {})[action["recipe_id"]] = 0

    fatal_codes = {"protected_state_changed", "mutation_inconclusive", "contract_drift", "bgm_provenance", "unrecoverable"}
    limits = budgets["limits"]
    exhausted = (
        fingerprints[fingerprint_key] >= int(limits["same_failure"])
        or phase_failures[phase] >= int(limits["phase_failures"])
        or budgets["run_failures"] >= int(limits["run_failures"])
    )
    if reason_code in fatal_codes or not rolled_back or exhausted:
        state["lifecycle"] = "blocked"
        state["blocked"] = {
            "reason": detail,
            "reason_code": reason_code,
            "batch_id": action["batch_id"],
            "failure_fingerprint": fingerprint_key,
            "rolled_back": rolled_back,
            "at": utc_now(),
        }
        update_ledger(
            root,
            action["batch_id"],
            measured=detail,
            status="blocked",
            evidence=";".join(str(path) for path in evidence),
        )
        append_event(root, state, "ACTION_BLOCKED", batch_id=action["batch_id"], reason_code=reason_code, detail=detail)
        return

    action["attempt"] = int(action["attempt"]) + 1
    checkpoint_digest = action.get("pre_checkpoint", {}).get("observation_sha256", canonical_digest(action))
    action["token"] = make_token(state, action["action_key"], action["attempt"], checkpoint_digest)
    action["started_at"] = None
    state["lifecycle"] = "repair_required"
    state["next_action"] = {"kind": "retry_once", "token": action["token"]}
    update_ledger(
        root,
        action["batch_id"],
        measured=detail,
        status="open_repair",
        evidence=";".join(str(path) for path in evidence),
    )
    append_event(
        root,
        state,
        "ACTION_FAILED_RECOVERED",
        batch_id=action["batch_id"],
        reason_code=reason_code,
        detail=detail,
        retry_token=action["token"],
    )


def command_verify(args: argparse.Namespace) -> int:
    root = Path(args.run_dir).expanduser().resolve()
    with run_lock(root):
        state = load_state(root)
        if state["lifecycle"] != "in_action":
            raise ValueError("verify requires one in-progress action")
        action = state["open_action"]
        if args.token != action["token"]:
            raise ValueError("stale or foreign action token")
        ensure_no_drift(state)
        spec = ACTION_REGISTRY[action["action_key"]]
        evidence = evidence_paths(args.evidence, minimum=int(spec.get("minimum_evidence", 1)))
        fresh_evidence(evidence, action["started_at"])
        failures: list[str] = []
        metrics: dict[str, Any] = {}
        post_checkpoint = None

        if spec["live"]:
            if not args.observation:
                raise ValueError("live verification requires --observation POST_STATE.json")
            after = load_observation(Path(args.observation).expanduser().resolve())
            before_path = Path(action["pre_checkpoint"]["observation"])
            before = read_json(before_path, "pre observation")
            failures.extend(compare_observations(before, after, action["expectations"]))
            post_checkpoint = save_checkpoint(root, action["batch_id"], f"after_attempt_{action['attempt']}", after, evidence)
            metrics["before_sha256"] = action["pre_checkpoint"]["observation_sha256"]
            metrics["after_sha256"] = post_checkpoint["observation_sha256"]
        else:
            check = find_plan_check(root, action["check_id"])
            if not check:
                failures.append(f"objective check disappeared: {action['check_id']}")
            else:
                if spec.get("fresh_objective_target_required") and check.get("path"):
                    target_path = Path(check["path"]).expanduser()
                    if not target_path.is_absolute():
                        target_path = root / target_path
                    try:
                        fresh_evidence([target_path.resolve()], action["started_at"])
                    except Exception as exc:
                        failures.append(f"objective target freshness: {exc}")
                passed, detail, check_metrics = run_check(root, check)
                metrics["objective_check"] = {"pass": passed, "detail": detail, "metrics": check_metrics}
                if not passed:
                    failures.append(detail)

        if spec.get("caption_transaction_required"):
            if not args.transaction_log:
                failures.append("missing caption transaction log")
            else:
                try:
                    metrics["caption_transaction"] = validate_caption_transaction(
                        Path(args.transaction_log).expanduser().resolve(), action["expectations"]["caption_count"]
                    )
                except Exception as exc:
                    failures.append(str(exc))
        if spec.get("loop_required"):
            if not args.loop_results:
                failures.append("missing loop results")
            else:
                try:
                    metrics["loop_results"] = validate_loop_results(
                        Path(args.loop_results).expanduser().resolve(), action["loop_manifest"]
                    )
                except Exception as exc:
                    failures.append(str(exc))
        if action.get("objective_check_id"):
            check = find_plan_check(root, action["objective_check_id"])
            if not check:
                failures.append(f"objective check disappeared: {action['objective_check_id']}")
            else:
                target = check.get("path")
                if target:
                    target_path = Path(target).expanduser()
                    if not target_path.is_absolute():
                        target_path = root / target_path
                    try:
                        fresh_evidence([target_path.resolve()], action["started_at"])
                    except Exception as exc:
                        failures.append(f"objective target freshness: {exc}")
                passed, detail, check_metrics = run_check(root, check)
                metrics["supplemental_objective_check"] = {
                    "id": action["objective_check_id"],
                    "pass": passed,
                    "detail": detail,
                    "metrics": check_metrics,
                }
                if not passed:
                    failures.append(f"{action['objective_check_id']}: {detail}")

        result = {
            "batch_id": action["batch_id"],
            "action_key": action["action_key"],
            "mutation": action["mutation"],
            "check_id": action["check_id"],
            "ledger_check_id": action.get("ledger_check_id", action["check_id"]),
            "objective_check_id": action.get("objective_check_id"),
            "attempt": action["attempt"],
            "checked_at": utc_now(),
            "pass": not failures,
            "failures": failures,
            "metrics": metrics,
            "evidence": [fingerprint(path) for path in evidence],
        }
        result_path = root / f"harness/checks/{action['batch_id']}/attempt_{action['attempt']}.json"
        atomic_json(result_path, result)

        if failures:
            rolled_back = bool(args.rolled_back)
            if rolled_back:
                if not args.rollback_observation:
                    failures.append("--rolled-back requires --rollback-observation")
                    rolled_back = False
                else:
                    rollback = load_observation(Path(args.rollback_observation).expanduser().resolve())
                    before = read_json(Path(action["pre_checkpoint"]["observation"]), "pre observation")
                    rollback_failures = compare_observations(before, rollback, {field: "same" for field in LIVE_OBSERVATION_KEYS})
                    if rollback_failures:
                        failures.extend(f"rollback: {failure}" for failure in rollback_failures)
                        rolled_back = False
                    else:
                        save_checkpoint(root, action["batch_id"], f"rollback_attempt_{action['attempt']}", rollback, evidence)
            protected_failure = any(
                failure.split("=", 1)[0] in {field for field, expectation in action["expectations"].items() if expectation == "same"}
                for failure in failures
            )
            close_action_as_failure(
                root,
                state,
                "protected_state_changed" if protected_failure else "check_failed",
                "; ".join(failures),
                evidence + [result_path],
                rolled_back,
            )
            atomic_json(pending_action_path(root), state["open_action"])
            save_state(root, state)
            print(json.dumps(status_payload(root, state), ensure_ascii=False, indent=2))
            return 1

        update_ledger(
            root,
            action["batch_id"],
            measured=args.measured,
            status="pass",
            evidence=";".join([str(result_path), *[str(path) for path in evidence]]),
            closed_at=utc_now(),
        )
        recipe = action["recipe_id"]
        streaks = state.setdefault("recipe_success_streak", {})
        streaks[recipe] = int(streaks.get(recipe, 0)) + 1
        counts = state.setdefault("action_success_count", {})
        counts[action["action_key"]] = int(counts.get(action["action_key"], 0)) + 1
        state.setdefault("completed_actions", []).append(
            {"action_key": action["action_key"], "batch_id": action["batch_id"], "closed_at": utc_now(), "result": str(result_path)}
        )
        state["last_good_checkpoint"] = post_checkpoint or str(result_path)
        append_event(root, state, "ACTION_PASSED", batch_id=action["batch_id"], result=str(result_path))
        state["open_action"] = None
        state["next_action"] = None
        state["lifecycle"] = "ready"
        save_state(root, state)
        pending_action_path(root).unlink(missing_ok=True)
    print(json.dumps(status_payload(root, state), ensure_ascii=False, indent=2))
    return 0


def command_fail(args: argparse.Namespace) -> int:
    root = Path(args.run_dir).expanduser().resolve()
    with run_lock(root):
        state = load_state(root)
        if state["lifecycle"] != "in_action":
            raise ValueError("fail requires one in-progress action")
        action = state["open_action"]
        if args.token != action["token"]:
            raise ValueError("stale or foreign action token")
        evidence = evidence_paths(args.evidence, minimum=1)
        fresh_evidence(evidence, action["started_at"])
        rolled_back = bool(args.rolled_back)
        if args.observation:
            observation = load_observation(Path(args.observation).expanduser().resolve())
            save_checkpoint(root, action["batch_id"], f"failed_attempt_{action['attempt']}", observation, evidence)
            if rolled_back:
                before = read_json(Path(action["pre_checkpoint"]["observation"]), "pre observation")
                rollback_failures = compare_observations(before, observation, {field: "same" for field in LIVE_OBSERVATION_KEYS})
                if rollback_failures:
                    rolled_back = False
                    args.detail += "; rollback not proven: " + "; ".join(rollback_failures)
        elif rolled_back:
            rolled_back = False
            args.detail += "; --rolled-back requires --observation proving the restored state"
        close_action_as_failure(root, state, args.reason_code, args.detail, evidence, rolled_back)
        atomic_json(pending_action_path(root), state["open_action"])
        save_state(root, state)
    print(json.dumps(status_payload(root, state), ensure_ascii=False, indent=2))
    return 1


def command_recover(args: argparse.Namespace) -> int:
    root = Path(args.run_dir).expanduser().resolve()
    with run_lock(root):
        state = load_state(root)
        journal_path = pending_action_path(root)
        if not journal_path.exists():
            if state.get("open_action"):
                atomic_json(journal_path, state["open_action"])
                append_event(root, state, "PENDING_JOURNAL_REBUILT", batch_id=state["open_action"]["batch_id"])
                save_state(root, state)
            print(json.dumps(status_payload(root, state), ensure_ascii=False, indent=2))
            return 0

        pending = read_json(journal_path, "pending action journal")
        rows = read_ledger(root / "batch_ledger.tsv")
        row = next((item for item in rows if item.get("batch_id") == pending.get("batch_id")), None)
        if row is None:
            if state.get("open_action"):
                raise ValueError("pending action has state but no ledger row; manual user decision required")
            journal_path.unlink(missing_ok=True)
            append_event(root, state, "ORPHAN_PREPARE_DISCARDED", batch_id=pending.get("batch_id"))
            save_state(root, state)
            print(json.dumps(status_payload(root, state), ensure_ascii=False, indent=2))
            return 0

        status = row.get("status", "")
        if status in {"pass", "waived"}:
            if status == "pass" and not any(
                item.get("batch_id") == pending.get("batch_id") for item in state.get("completed_actions", [])
            ):
                result_path = row.get("evidence", "").split(";", 1)[0]
                state.setdefault("completed_actions", []).append(
                    {
                        "action_key": pending["action_key"],
                        "batch_id": pending["batch_id"],
                        "closed_at": row.get("closed_at") or utc_now(),
                        "result": result_path,
                    }
                )
                recipe = pending["recipe_id"]
                streaks = state.setdefault("recipe_success_streak", {})
                streaks[recipe] = int(streaks.get(recipe, 0)) + 1
                counts = state.setdefault("action_success_count", {})
                counts[pending["action_key"]] = int(counts.get(pending["action_key"], 0)) + 1
            state["open_action"] = None
            state["next_action"] = None
            state["lifecycle"] = "ready"
            journal_path.unlink(missing_ok=True)
            append_event(root, state, "CLOSED_ACTION_RECOVERED", batch_id=pending["batch_id"], ledger_status=status)
            save_state(root, state)
        elif status in {"prepared", "in_action", "open_repair", "blocked"}:
            state["open_action"] = pending
            state["lifecycle"] = {
                "prepared": "prepared",
                "in_action": "in_action",
                "open_repair": "repair_required",
                "blocked": "blocked",
            }[status]
            if status == "blocked" and not state.get("blocked"):
                state["blocked"] = {"reason_code": "recovered_block", "reason": row.get("measured", "blocked action")}
            state["next_action"] = {"kind": "inspect_pending_action", "token": pending.get("token")}
            append_event(root, state, "OPEN_ACTION_RECOVERED", batch_id=pending["batch_id"], ledger_status=status)
            save_state(root, state)
        else:
            raise ValueError(f"cannot recover unrecognized ledger status: {status}")
    print(json.dumps(status_payload(root, state), ensure_ascii=False, indent=2))
    return 0


def command_advance(args: argparse.Namespace) -> int:
    root = Path(args.run_dir).expanduser().resolve()
    with run_lock(root):
        state = load_state(root)
        if state["lifecycle"] != "ready" or state.get("open_action"):
            raise ValueError("advance requires ready state with no open action")
        ensure_no_drift(state)
        check_results = []
        for check_id in args.check_id:
            check = find_plan_check(root, check_id)
            if not check:
                raise ValueError(f"phase gate check not found: {check_id}")
            passed, detail, metrics = run_check(root, check)
            check_results.append({"id": check_id, "pass": passed, "detail": detail, "metrics": metrics})
            if not passed:
                raise ValueError(f"phase gate failed: {check_id}: {detail}")
        artifacts = []
        for value in args.artifact:
            candidate = Path(value).expanduser()
            if not candidate.is_absolute():
                candidate = root / candidate
            artifacts.append(fingerprint(candidate))
        seal = {"phase": state["phase"], "sealed_at": utc_now(), "checks": check_results, "artifacts": artifacts}
        seal_path = root / f"harness/phase_seals/{state['phase']}.json"
        atomic_json(seal_path, seal)
        state.setdefault("sealed_phases", {})[state["phase"]] = seal
        previous = state["phase"]
        state["phase"] = args.to_phase
        manifest = read_json(root / "run_manifest.json", "run manifest")
        manifest["current_phase"] = args.to_phase
        manifest["updated_at"] = utc_now()
        atomic_json(root / "run_manifest.json", manifest)
        append_event(root, state, "PHASE_ADVANCED", from_phase=previous, to_phase=args.to_phase, seal=str(seal_path))
        save_state(root, state)
    print(json.dumps(status_payload(root, state), ensure_ascii=False, indent=2))
    return 0


def command_unblock(args: argparse.Namespace) -> int:
    root = Path(args.run_dir).expanduser().resolve()
    with run_lock(root):
        state = load_state(root)
        if state["lifecycle"] != "blocked":
            raise ValueError("unblock is only valid for a blocked harness")
        if args.authorized_by != "user":
            raise ValueError("unblock requires explicit user authority: --authorized-by user")
        action = state.get("open_action")
        if action:
            if action.get("pre_checkpoint"):
                if not args.observation:
                    raise ValueError("unblocking a live action requires --observation proving restoration")
                restored = load_observation(Path(args.observation).expanduser().resolve())
                before = read_json(Path(action["pre_checkpoint"]["observation"]), "pre observation")
                restoration_failures = compare_observations(
                    before, restored, {field: "same" for field in LIVE_OBSERVATION_KEYS}
                )
                if restoration_failures:
                    raise ValueError("live state not restored: " + "; ".join(restoration_failures))
                unblock_evidence = evidence_paths(args.evidence, minimum=1)
                save_checkpoint(root, action["batch_id"], "user_unblock_restored", restored, unblock_evidence)
            action["attempt"] = int(action.get("attempt", 1)) + 1
            checkpoint_digest = action.get("pre_checkpoint", {}).get("observation_sha256", canonical_digest(action))
            action["token"] = make_token(state, action["action_key"], action["attempt"], checkpoint_digest)
            action["started_at"] = None
            update_ledger(root, action["batch_id"], status="open_repair", measured=args.reason)
        append_event(root, state, "USER_UNBLOCKED", reason=args.reason, previous_block=state.get("blocked"))
        state["blocked"] = None
        if action:
            state["next_action"] = {"kind": "retry_once", "token": action["token"]}
            state["lifecycle"] = "repair_required"
            atomic_json(pending_action_path(root), action)
        else:
            state["next_action"] = None
            state["lifecycle"] = "ready"
        save_state(root, state)
    print(json.dumps(status_payload(root, state), ensure_ascii=False, indent=2))
    return 0


def command_rebind(args: argparse.Namespace) -> int:
    root = Path(args.run_dir).expanduser().resolve()
    with run_lock(root):
        state = load_state(root)
        if args.authorized_by != "user":
            raise ValueError("rebind requires explicit user authority: --authorized-by user")
        if state.get("open_action") or state["lifecycle"] in {"prepared", "in_action", "repair_required", "closing", "complete"}:
            raise ValueError("rebind requires no open action and a non-complete run")
        previous = {
            "contract": state.get("contract_fingerprint"),
            "verification_plan": state.get("verification_plan_fingerprint"),
            "sealed_phases": sorted(state.get("sealed_phases", {})),
            "completed_action_count": len(state.get("completed_actions", [])),
        }
        state["contract_fingerprint"] = fingerprint(root / "request_contract.json")
        state["verification_plan_fingerprint"] = fingerprint(root / "verification_plan.json")
        state["sealed_phases"] = {}
        state["completed_actions"] = []
        state["recipe_success_streak"] = {}
        state["blocked"] = None
        state["next_action"] = None
        state["lifecycle"] = "ready"
        append_event(root, state, "CONTRACT_REBOUND", reason=args.reason, previous=previous)
        save_state(root, state)
    print(json.dumps(status_payload(root, state), ensure_ascii=False, indent=2))
    return 0


def final_order_passed(state: dict[str, Any]) -> bool:
    completed = [row.get("action_key") for row in state.get("completed_actions", [])]
    return tuple(completed[-len(FINAL_ACTION_ORDER) :]) == FINAL_ACTION_ORDER


def command_close(args: argparse.Namespace) -> int:
    root = Path(args.run_dir).expanduser().resolve()
    with run_lock(root):
        state = load_state(root)
        if state["lifecycle"] != "ready" or state.get("open_action"):
            raise ValueError("close requires ready state with no open action")
        if pending_action_path(root).exists():
            raise ValueError("close requires no pending action journal; run recover")
        ensure_no_drift(state)
        if not final_order_passed(state):
            raise ValueError(f"final close requires verified action order: {list(FINAL_ACTION_ORDER)}")
        rows = read_ledger(root / "batch_ledger.tsv")
        bad = [row.get("batch_id") for row in rows if row.get("status") not in {"pass", "waived"}]
        if bad:
            raise ValueError(f"batch ledger contains non-closed rows: {bad}")

        report = run_plan(root)
        failed = [row for row in report["results"] if row["required"] and not row["pass"]]
        if failed:
            raise ValueError("full objective plan failed: " + "; ".join(f"{row['id']}: {row['detail']}" for row in failed))

        manifest_path = root / "run_manifest.json"
        manifest = read_json(manifest_path, "run manifest")
        previous_status = manifest.get("status", "in_progress")
        previous_phase = manifest.get("current_phase", state["phase"])
        state["lifecycle"] = "closing"
        append_event(root, state, "CLOSE_PREPARED")
        save_state(root, state)
        manifest["status"] = "complete"
        manifest["current_phase"] = "complete"
        manifest["updated_at"] = utc_now()
        atomic_json(manifest_path, manifest)

        validator = Path(__file__).with_name("validate_run.py")
        completed = subprocess.run([sys.executable, str(validator), str(root)], capture_output=True, text=True, check=False)
        state = load_state(root)
        close_result = {
            "checked_at": utc_now(),
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        atomic_json(root / "harness/close_result.json", close_result)
        if completed.returncode != 0:
            manifest["status"] = previous_status if previous_status != "complete" else "in_progress"
            manifest["current_phase"] = previous_phase
            atomic_json(manifest_path, manifest)
            state["lifecycle"] = "blocked"
            state["blocked"] = {"reason_code": "final_validation_failed", "reason": completed.stdout or completed.stderr, "at": utc_now()}
            append_event(root, state, "CLOSE_ROLLED_BACK", returncode=completed.returncode)
            save_state(root, state)
            print(completed.stdout or completed.stderr)
            return 1
        state["lifecycle"] = "complete"
        state["phase"] = "complete"
        append_event(root, state, "RUN_COMPLETED")
        save_state(root, state)
    print("HARNESS CLOSE PASSED")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("run_dir")
    init.add_argument("--phase")
    init.set_defaults(func=command_init)

    for name in ("status", "resume"):
        command = sub.add_parser(name)
        command.add_argument("run_dir")
        command.set_defaults(func=command_status)

    recover = sub.add_parser("recover")
    recover.add_argument("run_dir")
    recover.set_defaults(func=command_recover)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("run_dir")
    prepare.add_argument("--action-key", required=True, choices=sorted(ACTION_REGISTRY))
    prepare.add_argument("--recipe-id", required=True)
    prepare.add_argument("--assumption", required=True)
    prepare.add_argument("--scope", required=True)
    prepare.add_argument("--unit-limit-key", required=True)
    prepare.add_argument("--unit-count", required=True, type=int)
    prepare.add_argument("--check-id", required=True)
    prepare.add_argument("--objective-check-id")
    prepare.add_argument("--observation")
    prepare.add_argument("--evidence", action="append")
    prepare.add_argument("--expect", action="append")
    prepare.add_argument("--media")
    prepare.add_argument("--timing-contract")
    prepare.add_argument("--loop-manifest")
    prepare.add_argument("--optional", action="store_true")
    prepare.set_defaults(func=command_prepare)

    begin = sub.add_parser("begin")
    begin.add_argument("run_dir")
    begin.add_argument("--token", required=True)
    begin.set_defaults(func=command_begin)

    skip = sub.add_parser("skip")
    skip.add_argument("run_dir")
    skip.add_argument("--token", required=True)
    skip.add_argument("--reason", required=True)
    skip.add_argument("--authorized-by", required=True, choices=("user",))
    skip.set_defaults(func=command_skip)

    verify = sub.add_parser("verify")
    verify.add_argument("run_dir")
    verify.add_argument("--token", required=True)
    verify.add_argument("--observation")
    verify.add_argument("--evidence", action="append", required=True)
    verify.add_argument("--measured", required=True)
    verify.add_argument("--rolled-back", action="store_true")
    verify.add_argument("--rollback-observation")
    verify.add_argument("--transaction-log")
    verify.add_argument("--loop-results")
    verify.set_defaults(func=command_verify)

    fail = sub.add_parser("fail")
    fail.add_argument("run_dir")
    fail.add_argument("--token", required=True)
    fail.add_argument(
        "--reason-code",
        required=True,
        choices=("no_change", "wrong_media", "check_failed", "protected_state_changed", "mutation_inconclusive", "bgm_provenance", "unrecoverable"),
    )
    fail.add_argument("--detail", required=True)
    fail.add_argument("--evidence", action="append", required=True)
    fail.add_argument("--observation")
    fail.add_argument("--rolled-back", action="store_true")
    fail.set_defaults(func=command_fail)

    advance = sub.add_parser("advance")
    advance.add_argument("run_dir")
    advance.add_argument("--to-phase", required=True)
    advance.add_argument("--check-id", action="append", required=True)
    advance.add_argument("--artifact", action="append", required=True)
    advance.set_defaults(func=command_advance)

    unblock = sub.add_parser("unblock")
    unblock.add_argument("run_dir")
    unblock.add_argument("--reason", required=True)
    unblock.add_argument("--authorized-by", required=True, choices=("user",))
    unblock.add_argument("--observation")
    unblock.add_argument("--evidence", action="append")
    unblock.set_defaults(func=command_unblock)

    rebind = sub.add_parser("rebind")
    rebind.add_argument("run_dir")
    rebind.add_argument("--reason", required=True)
    rebind.add_argument("--authorized-by", required=True, choices=("user",))
    rebind.set_defaults(func=command_rebind)

    close = sub.add_parser("close")
    close.add_argument("run_dir")
    close.set_defaults(func=command_close)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except (ValueError, OSError, KeyError) as exc:
        print(f"HARNESS BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
