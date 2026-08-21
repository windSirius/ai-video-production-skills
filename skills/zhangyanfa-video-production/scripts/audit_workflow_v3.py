#!/usr/bin/env python3
"""Audit workflow v3 creative-release gates before render or project seal.

This auditor intentionally separates technical existence from human release.  A
work authorization can never satisfy an artifact-bound approval gate.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

from audit_authority_chain import audit_authority_bundle


PROFILE = "artifact_bound_release_v3"
PASS_VALUES = {"pass", "approved", "approved_by_user", "frozen", "current"}
DEFAULT_ARTIFACTS = {
    "approval_ledger": "approvals/approval_ledger.jsonl",
    "research_evidence_matrix": "research/evidence_matrix.tsv",
    "script_qa": "script/script_qa.json",
    "voice_release": "narration/voice_release.json",
    "semantic_coverage_qa": "visuals/semantic_coverage_qa.json",
    "visual_reuse_qa": "visuals/reuse_qa.json",
    "match_sheet": "visuals/match_sheet.tsv",
    "visual_review_manifest": "visuals/review_manifest.json",
    "b_review_manifest": "tracks/review_manifest.json",
    "static_asset_review_bundle": "visuals/static_asset_review_bundle.json",
    "hyperframes_composition": "hyperframes/composition.json",
    "hyperframes_render_plan": "hyperframes/render_plan.json",
    "hyperframes_stress_manifest": "hyperframes/stress/stress_manifest.json",
    "full_review_proxy": "hyperframes/proxy/aesthetic_proxy_720p.mp4",
    "full_review_approval": "visuals/aesthetic_review/approval.json",
    "bgm_manifest": "audio/bgm_manifest.json",
    "cover_review_manifest": "cover/review_manifest.json",
    "current_pointer": "CURRENT.json",
}
RESEARCH_COLUMNS = {
    "claim_id",
    "claim_level",
    "claim_text",
    "game_evidence",
    "real_prototype",
    "narrative_function",
    "internal_cross_validation",
    "counterevidence",
    "confidence",
    "source_refs",
    "status",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def norm(value: object) -> str:
    return str(value or "").strip().lower()


def dotted(data: Any, key: str, default: Any = None) -> Any:
    current = data
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def parse_iso(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(value)
    return rows


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value or "")).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def manifest_artifact(root: Path, manifest: dict[str, Any], key: str) -> Path:
    configured = dotted(manifest, f"artifacts.{key}", "")
    return resolve(root, configured or DEFAULT_ARTIFACTS[key])


def ffprobe(path: Path) -> dict[str, Any]:
    executable = shutil.which("ffprobe")
    if not executable:
        raise RuntimeError("ffprobe not found")
    completed = subprocess.run(
        [
            executable,
            "-v",
            "error",
            "-count_frames",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or "ffprobe failed")
    return json.loads(completed.stdout)


def video_summary(path: Path) -> dict[str, Any]:
    probe = ffprobe(path)
    streams = probe.get("streams", [])
    videos = [row for row in streams if row.get("codec_type") == "video"]
    audios = [row for row in streams if row.get("codec_type") == "audio"]
    video = videos[0] if videos else {}
    rate_text = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
    rate = float(Fraction(rate_text)) if rate_text not in {"0/0", "0"} else 0.0
    frames_text = video.get("nb_read_frames") or video.get("nb_frames") or "0"
    try:
        frames = int(frames_text)
    except (TypeError, ValueError):
        frames = 0
    return {
        "width": int(video.get("width", 0) or 0),
        "height": int(video.get("height", 0) or 0),
        "fps": rate,
        "frames": frames,
        "video_streams": len(videos),
        "audio_streams": len(audios),
    }


class Audit:
    def __init__(self, root: Path, stage: str) -> None:
        self.root = root
        self.stage = stage
        self.checks: list[dict[str, Any]] = []

    def add(self, check_id: str, passed: bool, detail: str, **metrics: Any) -> None:
        self.checks.append(
            {"id": check_id, "pass": bool(passed), "detail": detail, "metrics": metrics}
        )

    def require_file(self, check_id: str, path: Path) -> bool:
        passed = path.is_file() and path.stat().st_size > 0
        self.add(check_id, passed, str(path), size=path.stat().st_size if path.is_file() else 0)
        return passed

    def result(self) -> dict[str, Any]:
        failures = [row for row in self.checks if not row["pass"]]
        return {
            "schema_version": 1,
            "workflow_profile": PROFILE,
            "stage": self.stage,
            "status": "PASS" if not failures else "FAIL",
            "ok": not failures,
            "run_dir": str(self.root),
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "check_count": len(self.checks),
            "failure_count": len(failures),
            "checks": self.checks,
        }


def audit_contract(audit: Audit, contract: dict[str, Any]) -> None:
    failures: list[str] = []
    if norm(dotted(contract, "workflow_profiles.production_control", "")) != PROFILE:
        failures.append("workflow_profiles.production_control")
    approval_raw = contract.get("approval_policy", {})
    approval = approval_raw if isinstance(approval_raw, dict) else {}
    if not isinstance(approval_raw, dict):
        failures.append("approval_policy must be an object")
    for field in (
        "work_authorization_cannot_release_unseen_artifacts",
        "require_artifact_sha256",
        "require_artifact_created_before_showing",
        "require_showing_before_approval",
        "require_exact_user_quote",
    ):
        if approval.get(field) is not True:
            failures.append(f"approval_policy.{field}")
    creative_raw = contract.get("creative_release_policy", {})
    creative = creative_raw if isinstance(creative_raw, dict) else {}
    if not isinstance(creative_raw, dict):
        failures.append("creative_release_policy must be an object")
    for field in (
        "require_research_counterevidence",
        "require_whole_document_script_qa",
        "require_voice_lexical_and_prosody_gates",
        "require_cross_episode_reuse_ledger",
        "require_full_length_720p_proxy",
        "full_length_proxy_requires_frozen_narration",
        "require_bgm_human_audition",
        "require_artifact_bound_bgm_review",
        "require_deterministic_exact_subject_cover_assets",
        "require_artifact_bound_cover_review",
    ):
        if creative.get(field) is not True:
            failures.append(f"creative_release_policy.{field}")
    try:
        if float(creative.get("minimum_a_direct_plus_strong_ratio", 0)) < 0.80:
            failures.append("creative_release_policy.minimum_a_direct_plus_strong_ratio")
        if float(creative.get("minimum_a_plus_b_ratio", 0)) < 0.90:
            failures.append("creative_release_policy.minimum_a_plus_b_ratio")
        if int(creative.get("maximum_consecutive_visual_family", 999999)) > 3:
            failures.append("creative_release_policy.maximum_consecutive_visual_family")
    except (TypeError, ValueError):
        failures.append("creative release numeric thresholds")
    audit.add(
        "workflow_v3_contract_locked",
        not failures,
        f"failed={failures}" if failures else "v3 approval and creative policies are locked",
    )


def audit_research(audit: Audit, path: Path) -> None:
    if not audit.require_file("research_matrix_exists", path):
        return
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = set(reader.fieldnames or [])
        rows = list(reader)
    missing_columns = sorted(RESEARCH_COLUMNS - fields)
    core_rows = [row for row in rows if norm(row.get("claim_level")) == "core"]
    failures: list[str] = []
    if missing_columns:
        failures.append(f"missing columns={missing_columns}")
    if not core_rows:
        failures.append("no core claims")
    required_values = RESEARCH_COLUMNS - {"claim_level"}
    for row_number, row in enumerate(core_rows, start=2):
        missing = sorted(field for field in required_values if not str(row.get(field, "")).strip())
        if missing:
            failures.append(f"core row {row_number} missing={missing}")
        if norm(row.get("confidence")) not in {"direct", "strong_inference", "speculative"}:
            failures.append(f"core row {row_number} invalid confidence")
        if norm(row.get("status")) != "reviewed":
            failures.append(f"core row {row_number} status must be reviewed")
    audit.add(
        "research_core_claims_reviewed",
        not failures,
        "; ".join(failures) if failures else f"core_claims={len(core_rows)}",
        rows=len(rows),
        core_claims=len(core_rows),
    )


def audit_script_qa(audit: Audit, path: Path, authority: dict[str, Any]) -> None:
    if not audit.require_file("script_qa_exists", path):
        return
    data = load_json(path)
    required = [
        "structure_pass",
        "evidence_pass",
        "chinese_oral_pass",
        "anti_calque_pass",
        "persona_pass",
        "entity_pronoun_pass",
        "read_aloud_pass",
    ]
    failures = [field for field in required if data.get(field) is not True]
    script_sha = dotted(authority, "authorities.script.sha256", "")
    if str(data.get("script_sha256", "")).lower() != str(script_sha).lower():
        failures.append("script_sha256")
    if norm(data.get("human_status")) not in PASS_VALUES:
        failures.append("human_status")
    audit.add(
        "script_whole_document_release",
        not failures,
        f"failed={failures}" if failures else "all whole-document passes are current",
    )


def audit_voice_release(audit: Audit, path: Path, authority: dict[str, Any]) -> None:
    if not audit.require_file("voice_release_exists", path):
        return
    data = load_json(path)
    failures: list[str] = []
    if norm(data.get("lexical_status")) != "pass":
        failures.append("lexical_status")
    if norm(data.get("pronunciation_status")) not in {"pass", "pass_with_minor_warnings"}:
        failures.append("pronunciation_status")
    if norm(data.get("prosody_status")) != "pass":
        failures.append("prosody_status")
    if norm(data.get("punctuation_topology")) != "preserved":
        failures.append("punctuation_topology")
    if data.get("micro_splice_used") is not False:
        failures.append("micro_splice_used")
    if norm(data.get("full_length_audition_status")) != "pass":
        failures.append("full_length_audition_status")
    if not str(data.get("approval_ledger_id", "")).strip():
        failures.append("approval_ledger_id")
    narration = dotted(authority, "authorities.narration", {})
    expected_sha = str(narration.get("sha256", "")).lower()
    if str(data.get("narration_sha256", "")).lower() != expected_sha:
        failures.append("narration_sha256")
    narration_path = resolve(audit.root, narration.get("path", ""))
    if not narration_path.is_file() or (expected_sha and sha256_file(narration_path) != expected_sha):
        failures.append("actual narration file/hash")
    audit.add(
        "voice_lexical_and_prosody_release",
        not failures,
        f"failed={failures}" if failures else "lexical, major pronunciation, prosody and full audition pass",
    )


def audit_semantic_coverage(
    audit: Audit,
    path: Path,
    minimum_a_ratio: float,
    minimum_ab_ratio: float,
) -> None:
    if not audit.require_file("semantic_coverage_exists", path):
        return
    data = load_json(path)
    a_ratio = float(dotted(data, "a_track_semantic_rubric.direct_plus_strong_ratio", 0) or 0)
    ab_ratio = float(dotted(data, "composite_a_plus_b_rubric.ratio", 0) or 0)
    unresolved = int(data.get("unresolved_units", len(data.get("failures", []) or [])) or 0)
    opening = dotted(data, "opening_gate.cg_like_only", data.get("opening_cg_like_only"))
    failures: list[str] = []
    if norm(data.get("status")) != "pass":
        failures.append("status")
    if a_ratio < minimum_a_ratio:
        failures.append(f"A direct+strong={a_ratio:.4f}<{minimum_a_ratio:.4f}")
    if ab_ratio < minimum_ab_ratio:
        failures.append(f"A+B direct/strong/exact={ab_ratio:.4f}<{minimum_ab_ratio:.4f}")
    if unresolved:
        failures.append(f"unresolved_units={unresolved}")
    if opening is not True:
        failures.append("opening 0-10s is not cg_like_only")
    audit.add(
        "semantic_coverage_gate",
        not failures,
        "; ".join(failures) if failures else "semantic coverage thresholds pass",
        a_direct_strong_ratio=a_ratio,
        a_plus_b_ratio=ab_ratio,
        unresolved_units=unresolved,
        minimum_a_ratio=minimum_a_ratio,
        minimum_a_plus_b_ratio=minimum_ab_ratio,
    )


def audit_reuse(audit: Audit, path: Path, maximum_family_streak: int) -> None:
    if not audit.require_file("visual_reuse_qa_exists", path):
        return
    data = load_json(path)
    values: dict[str, int] = {}
    failures: list[str] = []
    for field in (
        "max_consecutive_same_visual_family",
        "unresolved_overlap_count",
        "cross_episode_cooldown_violations",
    ):
        raw = data.get(field)
        if raw is None or isinstance(raw, bool):
            failures.append(f"{field} missing")
            values[field] = 999999
            continue
        try:
            values[field] = int(raw)
        except (TypeError, ValueError):
            failures.append(f"{field} invalid")
            values[field] = 999999
    max_family = values["max_consecutive_same_visual_family"]
    overlap = values["unresolved_overlap_count"]
    cooldown = values["cross_episode_cooldown_violations"]
    if norm(data.get("status")) != "pass":
        failures.append("status")
    if max_family > maximum_family_streak:
        failures.append(
            f"max consecutive visual family={max_family}>{maximum_family_streak}"
        )
    if overlap:
        failures.append(f"unresolved overlaps={overlap}")
    if cooldown:
        failures.append(f"cross-episode cooldown violations={cooldown}")
    if data.get("visual_family_ids_complete") is not True:
        failures.append("visual_family_ids_complete")
    audit.add(
        "visual_family_reuse_gate",
        not failures,
        "; ".join(failures) if failures else "visual-family and cross-episode reuse pass",
        max_consecutive_same_visual_family=max_family,
        unresolved_overlap_count=overlap,
        cross_episode_cooldown_violations=cooldown,
        maximum_allowed_family_streak=maximum_family_streak,
    )


def audit_approval_entry(
    audit: Audit,
    ledger_rows: list[dict[str, Any]],
    check_id: str,
    kind: str,
    approval_id: str,
    artifact_path: Path,
    artifact_sha: str,
) -> dict[str, Any] | None:
    matches = [
        row
        for row in ledger_rows
        if row.get("approval_id") == approval_id
        and norm(row.get("kind")) == kind
        and norm(row.get("status")) == "approved"
    ]
    failures: list[str] = []
    if len(matches) != 1:
        failures.append(f"expected one current {kind} approval, got {len(matches)}")
        entry: dict[str, Any] = {}
    else:
        entry = matches[0]
        if resolve(audit.root, entry.get("artifact_path", "")) != artifact_path.resolve():
            failures.append("artifact_path")
        if str(entry.get("artifact_sha256", "")).lower() != artifact_sha:
            failures.append("artifact_sha256")
        if not str(entry.get("exact_user_quote", "")).strip():
            failures.append("exact_user_quote")
        if norm(entry.get("user_verdict")) not in {"pass", "approved"}:
            failures.append("user_verdict")
        times = [parse_iso(entry.get(field)) for field in ("artifact_created_at", "shown_at", "approved_at")]
        if any(value is None for value in times):
            failures.append("approval timestamps")
        elif not (times[0] <= times[1] <= times[2]):
            failures.append("approval happened before artifact/showing")
        elif artifact_path.stat().st_mtime > times[2].timestamp() + 5:
            failures.append("artifact was modified after approval")
        elif times[2] > datetime.now(timezone.utc) + timedelta(seconds=5):
            failures.append("approval timestamp is in the future")
    audit.add(
        check_id,
        not failures,
        f"failed={failures}" if failures else f"approval_id={approval_id}",
        ledger_rows=len(ledger_rows),
        approval_kind=kind,
    )
    return entry if not failures else None


def audit_script_audio_approval(
    audit: Audit,
    voice_release_path: Path,
    authority_path: Path,
    ledger_rows: list[dict[str, Any]],
) -> None:
    if not voice_release_path.is_file() or not authority_path.is_file():
        return
    release = load_json(voice_release_path)
    approval_id = str(release.get("approval_ledger_id", "")).strip()
    if not approval_id:
        audit.add("script_audio_freeze_approval", False, "voice_release approval_ledger_id missing")
        return
    audit_approval_entry(
        audit,
        ledger_rows,
        "script_audio_freeze_approval",
        "script_audio_freeze",
        approval_id,
        authority_path,
        sha256_file(authority_path),
    )


def audit_static_asset_review(
    audit: Audit,
    bundle_path: Path,
    visual_review_path: Path,
    b_review_path: Path,
    ledger_rows: list[dict[str, Any]],
) -> None:
    required = [
        audit.require_file("static_asset_review_bundle_exists", bundle_path),
        audit.require_file("a_visual_review_manifest_exists", visual_review_path),
        audit.require_file("b_review_manifest_exists", b_review_path),
    ]
    if not all(required):
        return
    bundle = load_json(bundle_path)
    failures: list[str] = []
    if norm(bundle.get("status")) != "pass":
        failures.append("status")
    if norm(bundle.get("human_status")) != "approved_by_user":
        failures.append("human_status")
    for field, path in (
        ("a_visual_review_manifest_sha256", visual_review_path),
        ("b_review_manifest_sha256", b_review_path),
    ):
        if str(bundle.get(field, "")).lower() != sha256_file(path):
            failures.append(field)
    for label, path in (("A", visual_review_path), ("B", b_review_path)):
        review = load_json(path)
        if norm(review.get("status")) != "pass":
            failures.append(f"{label} review status")
        if norm(review.get("human_status")) != "approved_by_user":
            failures.append(f"{label} review human_status")
        if review.get("render_authorized") is not True:
            failures.append(f"{label} review render_authorized")
    approval_id = str(bundle.get("approval_ledger_id", "")).strip()
    if not approval_id:
        failures.append("approval_ledger_id")
    audit.add(
        "static_asset_review_bundle",
        not failures,
        f"failed={failures}" if failures else "A/B static review manifests are frozen",
    )
    if approval_id:
        audit_approval_entry(
            audit,
            ledger_rows,
            "static_asset_review_approval",
            "static_asset_review",
            approval_id,
            bundle_path,
            sha256_file(bundle_path),
        )


def audit_full_proxy(
    audit: Audit,
    proxy_path: Path,
    approval_path: Path,
    ledger_rows: list[dict[str, Any]],
    authority_path: Path,
    semantic_path: Path,
    reuse_path: Path,
    match_sheet_path: Path,
    visual_review_path: Path,
    b_review_path: Path,
    static_review_bundle_path: Path,
    composition_path: Path,
    render_plan_path: Path,
    stress_manifest_path: Path,
    authority: dict[str, Any],
) -> None:
    required = [
        audit.require_file("full_review_proxy_exists", proxy_path),
        audit.require_file("full_review_approval_exists", approval_path),
    ]
    for key, path in (
        ("authority", authority_path),
        ("semantic_coverage", semantic_path),
        ("visual_reuse", reuse_path),
        ("match_sheet", match_sheet_path),
        ("a_visual_review", visual_review_path),
        ("b_review", b_review_path),
        ("static_review_bundle", static_review_bundle_path),
        ("composition", composition_path),
        ("render_plan", render_plan_path),
        ("stress_manifest", stress_manifest_path),
    ):
        required.append(audit.require_file(f"full_proxy_binding_{key}_exists", path))
    if not all(required):
        return
    approval = load_json(approval_path)
    proxy_sha = sha256_file(proxy_path)
    target = int(dotted(authority, "delivery_spec.target_frame_count", 0) or 0)
    fps = int(dotted(authority, "delivery_spec.fps", 0) or 0)
    media = video_summary(proxy_path)
    failures: list[str] = []
    if norm(approval.get("status")) != "pass":
        failures.append("status")
    if norm(approval.get("human_status")) != "approved_by_user":
        failures.append("human_status")
    if approval.get("render_authorized") is not True:
        failures.append("render_authorized")
    if approval.get("full_timeline_reviewed") is not True:
        failures.append("full_timeline_reviewed")
    if int(approval.get("review_start_frame", -1)) != 0:
        failures.append("review_start_frame")
    if int(approval.get("review_end_frame", -1)) != target:
        failures.append("review_end_frame")
    if str(approval.get("proxy_sha256", "")).lower() != proxy_sha:
        failures.append("proxy_sha256")
    for field, path in (
        ("authority_bundle_sha256", authority_path),
        ("semantic_coverage_sha256", semantic_path),
        ("visual_reuse_qa_sha256", reuse_path),
        ("match_sheet_sha256", match_sheet_path),
        ("visual_review_manifest_sha256", visual_review_path),
        ("b_review_manifest_sha256", b_review_path),
        ("static_asset_review_bundle_sha256", static_review_bundle_path),
        ("composition_sha256", composition_path),
        ("render_plan_sha256", render_plan_path),
        ("stress_manifest_sha256", stress_manifest_path),
    ):
        if str(approval.get(field, "")).lower() != sha256_file(path):
            failures.append(field)
    if media["width"] != 1280 or media["height"] != 720:
        failures.append(f"proxy dimensions={media['width']}x{media['height']}")
    if abs(float(media["fps"]) - fps) > 0.01:
        failures.append(f"proxy fps={media['fps']} expected={fps}")
    if media["frames"] != target:
        failures.append(f"proxy frames={media['frames']} expected={target}")
    if media["video_streams"] != 1:
        failures.append("proxy must contain exactly one video stream")
    if media["audio_streams"] < 1:
        failures.append("v3 full review proxy must include frozen narration")
    narration_sha = str(dotted(authority, "authorities.narration.sha256", "")).lower()
    if str(approval.get("narration_authority_sha256", "")).lower() != narration_sha:
        failures.append("narration_authority_sha256")
    approval_id = str(approval.get("approval_ledger_id", "")).strip()
    if not approval_id:
        failures.append("approval_ledger_id")
    audit.add(
        "full_timeline_dynamic_proxy",
        not failures,
        "; ".join(failures) if failures else "full 720p A/B proxy covers the entire frozen clock",
        **media,
        target_frame_count=target,
    )
    if approval_id:
        audit_approval_entry(
            audit,
            ledger_rows,
            "full_proxy_render_authorization",
            "full_proxy_render_authorization",
            approval_id,
            proxy_path,
            proxy_sha,
        )


def audit_bgm(audit: Audit, path: Path, ledger_rows: list[dict[str, Any]]) -> None:
    if not audit.require_file("bgm_manifest_exists", path):
        return
    data = load_json(path)
    failures: list[str] = []
    if data.get("human_audition_performed") is not True:
        failures.append("human_audition_performed")
    if norm(data.get("human_status")) not in PASS_VALUES:
        failures.append("human_status")
    checkpoints = data.get("audition_checkpoints", {})
    for field in ("hook", "densest_evidence", "emotional_turn", "ending"):
        if norm(checkpoints.get(field) if isinstance(checkpoints, dict) else "") != "pass":
            failures.append(f"audition_checkpoints.{field}")
    master_path = resolve(audit.root, data.get("bgm_master_path", ""))
    audition_path = resolve(audit.root, data.get("audition_mix_path", ""))
    if not master_path.is_file() or str(data.get("bgm_master_sha256", "")).lower() != (
        sha256_file(master_path) if master_path.is_file() else ""
    ):
        failures.append("bgm_master_path/sha256")
    if not audition_path.is_file() or str(data.get("audition_mix_sha256", "")).lower() != (
        sha256_file(audition_path) if audition_path.is_file() else ""
    ):
        failures.append("audition_mix_path/sha256")
    approval_id = str(data.get("approval_ledger_id", "")).strip()
    if not approval_id:
        failures.append("approval_ledger_id")
    audit.add("bgm_human_audition", not failures, f"failed={failures}" if failures else "four BGM checkpoints pass")
    if approval_id and audition_path.is_file():
        audit_approval_entry(
            audit,
            ledger_rows,
            "bgm_mix_user_approval",
            "bgm_mix_review",
            approval_id,
            audition_path,
            sha256_file(audition_path),
        )


def audit_cover(audit: Audit, path: Path, ledger_rows: list[dict[str, Any]]) -> None:
    if not audit.require_file("cover_review_manifest_exists", path):
        return
    data = load_json(path)
    failures: list[str] = []
    for field in (
        "identity_pass",
        "shot_pass",
        "same_space_pass",
        "text_pass",
        "thumbnail_pass",
        "edge_artifact_pass",
    ):
        if data.get(field) is not True:
            failures.append(field)
    route = norm(data.get("exact_subject_route"))
    if route not in {"deterministic_official_foreground", "generated_full_scene_user_authorized", "not_applicable"}:
        failures.append("exact_subject_route")
    if data.get("contains_exact_official_weapon_or_ui") is True and route != "deterministic_official_foreground":
        failures.append("official weapon/UI was generatively redrawn")
    if norm(data.get("human_status")) not in PASS_VALUES:
        failures.append("human_status")
    cover_path = resolve(audit.root, data.get("approved_artifact_path", ""))
    if not cover_path.is_file() or str(data.get("approved_artifact_sha256", "")).lower() != (
        sha256_file(cover_path) if cover_path.is_file() else ""
    ):
        failures.append("approved_artifact_path/sha256")
    approval_id = str(data.get("approval_ledger_id", "")).strip()
    if not approval_id:
        failures.append("approval_ledger_id")
    audit.add("cover_identity_and_asset_route", not failures, f"failed={failures}" if failures else f"route={route}")
    if approval_id and cover_path.is_file():
        audit_approval_entry(
            audit,
            ledger_rows,
            "cover_user_approval",
            "cover_review",
            approval_id,
            cover_path,
            sha256_file(cover_path),
        )


def audit_current(
    audit: Audit,
    path: Path,
    authority: dict[str, Any],
    bgm_manifest_path: Path,
    cover_review_path: Path,
) -> None:
    if not audit.require_file("current_pointer_exists", path):
        return
    data = load_json(path)
    failures: list[str] = []
    if norm(data.get("workflow_profile")) != PROFILE:
        failures.append("workflow_profile")
    if norm(data.get("status")) != "current":
        failures.append("status")
    updated = parse_iso(data.get("updated_at"))
    if updated is None:
        failures.append("updated_at")
    artifacts = data.get("artifacts", {})
    required = ("script", "narration", "subtitle", "picture_master", "bgm_master", "cover_16_9")
    for key in required:
        row = artifacts.get(key, {}) if isinstance(artifacts, dict) else {}
        candidate = resolve(audit.root, row.get("path", ""))
        expected = str(row.get("sha256", "")).lower()
        if not candidate.is_file() or not expected or sha256_file(candidate) != expected:
            failures.append(f"artifacts.{key}")
    authority_map = {
        "script": dotted(authority, "authorities.script.sha256", ""),
        "narration": dotted(authority, "authorities.narration.sha256", ""),
        "subtitle": dotted(authority, "authorities.subtitle.sha256", ""),
    }
    for key, expected in authority_map.items():
        if str(dotted(data, f"artifacts.{key}.sha256", "")).lower() != str(expected).lower():
            failures.append(f"CURRENT {key} differs from authority")
    if bgm_manifest_path.is_file():
        bgm = load_json(bgm_manifest_path)
        if str(dotted(data, "artifacts.bgm_master.sha256", "")).lower() != str(
            bgm.get("bgm_master_sha256", "")
        ).lower():
            failures.append("CURRENT bgm_master differs from approved BGM manifest")
    if cover_review_path.is_file():
        cover = load_json(cover_review_path)
        if str(dotted(data, "artifacts.cover_16_9.sha256", "")).lower() != str(
            cover.get("approved_artifact_sha256", "")
        ).lower():
            failures.append("CURRENT cover differs from approved cover review")
    audit.add("single_current_pointer", not failures, f"failed={failures}" if failures else "CURRENT.json is the sole sealed entry point")


def run_audit(root: Path, stage: str) -> dict[str, Any]:
    audit = Audit(root, stage)
    manifest_path = root / "run_manifest.json"
    contract_path = root / "request_contract.json"
    authority_path = root / "authority_bundle.json"
    if not audit.require_file("request_contract_exists", contract_path):
        return audit.result()
    contract = load_json(contract_path)
    audit_contract(audit, contract)
    if not audit.require_file("run_manifest_exists", manifest_path):
        return audit.result()
    manifest = load_json(manifest_path)
    profile = dotted(manifest, "workflow_profiles.production_control", "")
    audit.add("workflow_profile_v3", profile == PROFILE, f"production_control={profile!r}")
    if not audit.require_file("authority_bundle_exists", authority_path):
        return audit.result()
    authority = load_json(authority_path)
    authority_result = audit_authority_bundle(
        root,
        authority_path,
        require_descendants=set(),
        allow_provisional=False,
    )
    audit.add(
        "authority_chain_strict",
        authority_result["ok"],
        "; ".join(authority_result["errors"]) if authority_result["errors"] else "strict authority chain pass",
    )
    narration = dotted(authority, "authorities.narration", {})
    narration_failures = []
    for field in ("lexical_status", "prosody_status", "full_length_audition_status"):
        if norm(narration.get(field)) != "pass":
            narration_failures.append(field)
    if norm(narration.get("pronunciation_hotspots_status")) not in {"pass", "pass_with_minor_warnings"}:
        narration_failures.append("pronunciation_hotspots_status")
    audit.add(
        "authority_voice_dual_gate",
        not narration_failures,
        f"failed={narration_failures}" if narration_failures else "voice dual gate recorded in authority",
    )

    paths = {key: manifest_artifact(root, manifest, key) for key in DEFAULT_ARTIFACTS}
    ledger_rows: list[dict[str, Any]] = []
    if audit.require_file("approval_ledger_exists", paths["approval_ledger"]):
        ledger_rows = read_jsonl(paths["approval_ledger"])
    audit_research(audit, paths["research_evidence_matrix"])
    audit_script_qa(audit, paths["script_qa"], authority)
    audit_voice_release(audit, paths["voice_release"], authority)
    audit_script_audio_approval(
        audit,
        paths["voice_release"],
        authority_path,
        ledger_rows,
    )
    creative_value = contract.get("creative_release_policy", {})
    creative = creative_value if isinstance(creative_value, dict) else {}
    try:
        minimum_a_ratio = float(creative.get("minimum_a_direct_plus_strong_ratio", 0.80))
        minimum_ab_ratio = float(creative.get("minimum_a_plus_b_ratio", 0.90))
        maximum_family_streak = int(creative.get("maximum_consecutive_visual_family", 3))
    except (TypeError, ValueError):
        # audit_contract already records the malformed contract.  Keep the
        # remaining checks fail-closed without turning the auditor into a crash.
        minimum_a_ratio = 1.0
        minimum_ab_ratio = 1.0
        maximum_family_streak = 0
    audit_semantic_coverage(
        audit,
        paths["semantic_coverage_qa"],
        minimum_a_ratio,
        minimum_ab_ratio,
    )
    audit_reuse(audit, paths["visual_reuse_qa"], maximum_family_streak)
    audit_static_asset_review(
        audit,
        paths["static_asset_review_bundle"],
        paths["visual_review_manifest"],
        paths["b_review_manifest"],
        ledger_rows,
    )
    audit_full_proxy(
        audit,
        paths["full_review_proxy"],
        paths["full_review_approval"],
        ledger_rows,
        authority_path,
        paths["semantic_coverage_qa"],
        paths["visual_reuse_qa"],
        paths["match_sheet"],
        paths["visual_review_manifest"],
        paths["b_review_manifest"],
        paths["static_asset_review_bundle"],
        paths["hyperframes_composition"],
        paths["hyperframes_render_plan"],
        paths["hyperframes_stress_manifest"],
        authority,
    )
    if stage == "seal":
        audit_bgm(audit, paths["bgm_manifest"], ledger_rows)
        audit_cover(audit, paths["cover_review_manifest"], ledger_rows)
        audit_current(
            audit,
            paths["current_pointer"],
            authority,
            paths["bgm_manifest"],
            paths["cover_review_manifest"],
        )
    return audit.result()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir")
    parser.add_argument("--stage", choices=("pre-render", "seal"), default="pre-render")
    parser.add_argument("--output")
    args = parser.parse_args()
    root = Path(args.run_dir).expanduser().resolve()
    result = run_audit(root, args.stage)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = resolve(root, args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
