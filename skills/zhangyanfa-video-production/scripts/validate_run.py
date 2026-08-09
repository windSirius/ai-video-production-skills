#!/usr/bin/env python3
"""Validate request precision, batch closure, and objective evidence."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

from harness import (
    FINAL_ACTION_ORDER,
    SCHEMA_VERSION,
    VIDEO_RENDERING_V2_PROFILE,
    fingerprint_matches,
    final_order_passed,
    run_plan_cached,
    specialized_visual_targets,
)
from run_objective_checks import SUPPORTED_TYPES


REQUIRED_MANIFEST_KEYS = ("title", "current_phase", "status", "artifacts")
REQUIRED_ARTIFACT_KEYS = (
    "request_contract",
    "verification_plan",
    "batch_ledger",
    "edit_ledger",
    "acceptance_report",
    "harness_state",
)
MUSIC_SOURCE_ROOT = str(
    Path(os.environ.get("AI_VIDEO_MUSIC_ROOT") or (Path.home() / "Music")).expanduser().resolve()
)
VISUAL_WORKFLOW_RULES = {
    "offline.visual.source_proxy": (
        "source_proxy_manifests_per_batch",
        "source_proxy_manifest_integrity",
    ),
    "offline.visual.index": ("visual_indexes_per_batch", "visual_index_integrity"),
    "offline.visual.match_plan": ("match_plans_per_batch", "visual_match_plan_integrity"),
    "offline.visual.review": ("match_review_bundles_per_batch", "visual_selection_review_integrity"),
    "offline.visual.repair": ("match_repair_sets_per_batch", "visual_match_repair_integrity"),
    "offline.picture.render": ("picture_masters_per_batch", "picture_master_integrity"),
    "offline.picture.patch": ("picture_patches_per_batch", "picture_patch_integrity"),
    "offline.picture.stress_test": (
        "hyperframes_stress_tests_per_batch",
        "hyperframes_stress_test_integrity",
    ),
    "offline.picture.aesthetic_proxy": (
        "aesthetic_proxy_approvals_per_batch",
        "aesthetic_proxy_approval_integrity",
    ),
}


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def load_json(path: Path, errors: list[str]) -> dict:
    if not path.exists():
        errors.append(f"missing {path.name}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception as exc:
        errors.append(f"invalid {path.name}: {exc}")
        return {}


def validate_contract(contract: dict, plan: dict, errors: list[str]) -> None:
    for field in ("objective", "deliverable"):
        if not str(contract.get(field, "")).strip():
            errors.append(f"request contract missing precise {field}")
    scope = contract.get("scope", {})
    if not scope.get("in_scope"):
        errors.append("request contract requires nonempty in_scope")
    if not scope.get("out_of_scope"):
        errors.append("request contract requires nonempty out_of_scope")
    criteria = contract.get("success_criteria", [])
    if not criteria:
        errors.append("request contract requires success_criteria")
    check_ids = [check.get("id") for check in plan.get("checks", [])]
    if not check_ids or any(not value for value in check_ids):
        errors.append("verification plan requires named checks")
    if len(check_ids) != len(set(check_ids)):
        errors.append("verification plan check IDs must be unique")
    checks = plan.get("checks", [])
    for check in checks:
        if check.get("type") not in SUPPORTED_TYPES:
            errors.append(f"unsupported check type for {check.get('id')}: {check.get('type')}")
    bgm_check = next((check for check in checks if check.get("id") == "bgm_sources_within_music"), None)
    if not bgm_check:
        errors.append("verification plan requires bgm_sources_within_music")
    else:
        if bgm_check.get("type") != "bgm_sources_within_root":
            errors.append("bgm_sources_within_music must use bgm_sources_within_root")
        if bgm_check.get("path") != "audio/bgm_manifest.json":
            errors.append("bgm_sources_within_music must inspect audio/bgm_manifest.json")
        if bgm_check.get("source_root") != MUSIC_SOURCE_ROOT:
            errors.append(f"bgm_sources_within_music source_root must be {MUSIC_SOURCE_ROOT}")
        if bgm_check.get("required") is not True:
            errors.append("bgm_sources_within_music must be required")
    criterion_check_ids = []
    for criterion in criteria:
        if not criterion.get("claim"):
            errors.append(f"criterion {criterion.get('id')} missing claim")
        check_id = criterion.get("check_id")
        criterion_check_ids.append(check_id)
        if check_id not in check_ids:
            errors.append(f"criterion {criterion.get('id')} references missing check: {check_id}")
    if len(criterion_check_ids) != len(set(criterion_check_ids)):
        errors.append("each success criterion must use a unique check ID")
    limits = contract.get("unit_limits", {})
    if not limits or any(not isinstance(value, int) or value <= 0 for value in limits.values()):
        errors.append("all unit_limits must be positive integers")
    if not contract.get("stop_conditions"):
        errors.append("request contract requires stop_conditions")
    bgm_policy = contract.get("bgm_policy", {})
    if bgm_policy.get("source_root") != MUSIC_SOURCE_ROOT:
        errors.append(f"request contract bgm_policy.source_root must be {MUSIC_SOURCE_ROOT}")
    if bgm_policy.get("allow_external_sources") is not False:
        errors.append("request contract must forbid external BGM sources")
    if bgm_policy.get("allow_generated_sources") is not False:
        errors.append("request contract must forbid generated BGM sources")
    video_profile = contract.get("workflow_profiles", {}).get("video_rendering")
    if video_profile == VIDEO_RENDERING_V2_PROFILE:
        source_proxy = contract.get("render_policy", {}).get("source_proxy", {})
        required_proxy_fields = {
            "profile",
            "width",
            "height",
            "fps",
            "codec",
            "pixel_format",
            "color_space",
            "color_primaries",
            "color_transfer",
            "max_gop_frames",
            "cache_root",
        }
        missing_proxy_fields = sorted(required_proxy_fields - set(source_proxy))
        if missing_proxy_fields:
            errors.append(
                f"v2 source proxy policy missing fields={missing_proxy_fields}"
            )
        cache_root = str(source_proxy.get("cache_root", "")).strip()
        if not cache_root or not Path(cache_root).expanduser().is_absolute():
            errors.append("v2 source proxy cache_root must be absolute")
        elif "Library/Mobile Documents" in str(
            Path(cache_root).expanduser().resolve()
        ):
            errors.append("v2 source proxy cache_root must resolve outside iCloud")
        if source_proxy.get("require_outside_icloud") is not True:
            errors.append("v2 source proxy policy must require outside-iCloud cache")


def validate_tsv_status(path: Path, accepted: tuple[str, ...], errors: list[str], label: str, priorities: set[str] | None = None) -> None:
    if not path.exists():
        errors.append(f"missing {path.name}")
        return
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    for index, row in enumerate(rows, start=2):
        if priorities and row.get("priority") not in priorities:
            continue
        if not row.get("status", "").lower().startswith(accepted):
            errors.append(f"open {label} row at line {index}: {row.get('feedback') or row.get('assumption') or ''}")


def validate_batch_ledger(path: Path, limits: dict, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing {path.name}")
        return
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    for index, row in enumerate(rows, start=2):
        status = row.get("status", "").lower()
        harness_managed = row.get("batch_id", "").startswith("H")
        if harness_managed and status not in {"pass", "waived", "cancelled_no_mutation"}:
            errors.append(f"open harness batch row at line {index}: {row.get('assumption', '')}")
        elif not harness_managed and not status.startswith(("pass", "waived")):
            errors.append(f"open batch row at line {index}: {row.get('assumption', '')}")
        if status == "waived":
            if not row.get("waiver_reason", "").strip():
                errors.append(f"waived batch line {index} requires waiver_reason")
            if not row.get("superseded_by", "").strip():
                errors.append(f"waived batch line {index} requires superseded_by or user authorization reference")
        if status == "cancelled_no_mutation":
            if not row.get("superseded_by", "").startswith("user-authorized:"):
                errors.append(f"cancelled batch line {index} requires explicit user authorization")
        if harness_managed and status in {"pass", "cancelled_no_mutation"}:
            result_value = row.get("evidence", "").split(";", 1)[0]
            result_path = Path(result_value).expanduser()
            if not result_path.is_absolute():
                result_path = path.parent / result_path
            if not result_path.is_file():
                errors.append(f"harness batch line {index} missing verifier result: {result_path}")
            else:
                result = load_json(result_path, errors)
                if result.get("pass") is not True:
                    errors.append(f"harness batch line {index} verifier result is not pass")
                if result.get("batch_id") != row.get("batch_id"):
                    errors.append(f"harness batch line {index} verifier batch_id mismatch")
                if result.get("mutation") != row.get("mutation"):
                    errors.append(f"harness batch line {index} verifier mutation mismatch")
                if result.get("ledger_check_id") != row.get("check_id"):
                    errors.append(f"harness batch line {index} verifier/check binding mismatch")
                if status == "cancelled_no_mutation":
                    if result.get("status") != "cancelled_no_mutation":
                        errors.append(f"cancelled batch line {index} verifier status mismatch")
                    if result.get("agent_ui_steps_authorized") != 0:
                        errors.append(f"cancelled batch line {index} authorized an agent UI step")
                    if result.get("agent_ui_steps_completed") != 0:
                        errors.append(f"cancelled batch line {index} completed an agent UI step")
                    if result.get("claims_user_mutations") is not False:
                        errors.append(f"cancelled batch line {index} must not claim user mutations")
        limit_key = row.get("unit_limit_key", "")
        if limit_key not in limits:
            errors.append(f"batch line {index} uses unknown unit_limit_key: {limit_key}")
            continue
        try:
            unit_count = int(row.get("unit_count", ""))
        except ValueError:
            errors.append(f"batch line {index} has invalid unit_count: {row.get('unit_count', '')}")
            continue
        if unit_count <= 0 or unit_count > int(limits[limit_key]):
            errors.append(f"batch line {index} unit_count={unit_count} exceeds {limit_key}={limits[limit_key]}")


def validate_visual_workflow(
    ledger_path: Path,
    contract: dict,
    plan: dict,
    errors: list[str],
) -> None:
    """Conditionally enforce the indexed-bulk stage order without changing old runs."""

    if not ledger_path.exists():
        return
    with ledger_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    visual_rows = [
        (index, row)
        for index, row in enumerate(rows, start=2)
        if row.get("status") == "pass" and row.get("mutation") in VISUAL_WORKFLOW_RULES
    ]
    profile = contract.get("workflow_profiles", {}).get("visual_matching")
    video_profile = contract.get("workflow_profiles", {}).get("video_rendering")
    checks = {
        check.get("id"): check
        for check in plan.get("checks", [])
        if isinstance(check, dict)
    }
    if profile == "indexed_bulk_reviewed_v1":
        for line_number, row in enumerate(rows, start=2):
            if (
                row.get("status") != "pass"
                or row.get("mutation") != "offline.artifact"
            ):
                continue
            check_id = row.get("check_id", "").split("+", 1)[0]
            forbidden_targets = specialized_visual_targets(
                checks.get(check_id, {})
            )
            forbidden_targets.extend(
                specialized_visual_targets({"path": row.get("scope", "")})
            )
            forbidden_targets = sorted(set(forbidden_targets))
            if forbidden_targets:
                errors.append(
                    f"batch line {line_number} used offline.artifact for "
                    f"specialized visual targets={forbidden_targets}"
                )
    if not visual_rows:
        return

    if profile != "indexed_bulk_reviewed_v1":
        errors.append(
            "visual workflow actions require workflow_profiles.visual_matching="
            "indexed_bulk_reviewed_v1"
        )
    v2_mutations = {
        "offline.visual.source_proxy",
        "offline.picture.stress_test",
        "offline.picture.aesthetic_proxy",
    }
    if video_profile != VIDEO_RENDERING_V2_PROFILE and any(
        row.get("mutation") in v2_mutations for _, row in visual_rows
    ):
        errors.append(
            "v2 video-generation actions require workflow_profiles.video_rendering="
            f"{VIDEO_RENDERING_V2_PROFILE}"
        )
    limits = contract.get("unit_limits", {})
    seen: list[str] = []
    last_render_or_patch = -1
    last_repair = -1
    production_render_count = 0
    for sequence, (line_number, row) in enumerate(visual_rows):
        mutation = row["mutation"]
        limit_key, check_type = VISUAL_WORKFLOW_RULES[mutation]
        if limits.get(limit_key) != 1:
            errors.append(f"visual batch line {line_number} requires {limit_key}=1")
        if row.get("unit_limit_key") != limit_key or row.get("unit_count") != "1":
            errors.append(
                f"visual batch line {line_number} must use {limit_key} with unit_count=1"
            )
        check_id = row.get("check_id", "").split("+", 1)[0]
        if checks.get(check_id, {}).get("type") != check_type:
            errors.append(
                f"visual batch line {line_number} requires primary check type {check_type}"
            )

        if mutation == "offline.visual.match_plan" and "offline.visual.index" not in seen:
            errors.append(f"visual batch line {line_number} built a plan before an index")
        elif mutation == "offline.visual.review" and "offline.visual.match_plan" not in seen:
            errors.append(f"visual batch line {line_number} reviewed before a match plan")
        elif mutation == "offline.visual.repair" and "offline.visual.review" not in seen:
            errors.append(f"visual batch line {line_number} repaired before selected review")
        elif mutation == "offline.picture.render" and not any(
            value in seen for value in ("offline.visual.review", "offline.visual.repair")
        ):
            errors.append(f"visual batch line {line_number} rendered before review")
        elif mutation == "offline.picture.patch":
            if last_render_or_patch < 0:
                errors.append(f"visual batch line {line_number} patched before a base master")
            if last_repair <= last_render_or_patch:
                errors.append(
                    f"visual batch line {line_number} has no post-master declared repair"
                )
        if video_profile == VIDEO_RENDERING_V2_PROFILE:
            if mutation == "offline.visual.index" and "offline.visual.source_proxy" not in seen:
                errors.append(
                    f"visual batch line {line_number} indexed before source proxies"
                )
            elif mutation == "offline.picture.stress_test" and not any(
                value in seen
                for value in ("offline.visual.review", "offline.visual.repair")
            ):
                errors.append(
                    f"visual batch line {line_number} stress-tested before review"
                )
            elif mutation == "offline.picture.aesthetic_proxy" and (
                "offline.picture.stress_test" not in seen
            ):
                errors.append(
                    f"visual batch line {line_number} approved a proxy before stress test"
                )
            elif mutation == "offline.picture.render" and (
                "offline.picture.aesthetic_proxy" not in seen
            ):
                errors.append(
                    f"visual batch line {line_number} rendered production master "
                    "before 720p aesthetic approval"
                )
        seen.append(mutation)
        if mutation == "offline.visual.repair":
            last_repair = sequence
        if mutation in {"offline.picture.render", "offline.picture.patch"}:
            last_render_or_patch = sequence
        if mutation == "offline.picture.render":
            production_render_count += 1
    if video_profile == VIDEO_RENDERING_V2_PROFILE and production_render_count > 1:
        errors.append(
            f"v2 visual workflow permits one production render, got {production_render_count}"
        )


def validate_harness(root: Path, final: bool, errors: list[str]) -> dict:
    state = load_json(root / "harness/state.json", errors)
    if not state:
        return {}
    if state.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"unsupported harness schema: {state.get('schema_version')}")
    if state.get("run_dir") != str(root):
        errors.append("harness run_dir does not match validation root")
    if state.get("open_action"):
        errors.append("harness has an open action")
    lifecycle = state.get("lifecycle")
    if lifecycle == "blocked":
        errors.append(f"harness is blocked: {state.get('blocked', {}).get('reason', '')}")
    for label in ("contract_fingerprint", "verification_plan_fingerprint"):
        saved = state.get(label)
        if not isinstance(saved, dict) or not fingerprint_matches(saved):
            errors.append(f"harness fingerprint drift: {label}")
    for phase, seal in state.get("sealed_phases", {}).items():
        for artifact in seal.get("artifacts", []):
            if not fingerprint_matches(artifact):
                errors.append(f"sealed artifact drift: {phase}: {artifact.get('path')}")
    if final:
        if lifecycle not in {"closing", "complete"}:
            errors.append(f"final validation requires harness lifecycle closing/complete, got {lifecycle}")
        if not final_order_passed(state):
            errors.append(f"harness final action order incomplete: {list(FINAL_ACTION_ORDER)}")
    elif lifecycle not in {"ready", "complete"}:
        errors.append(f"contract-only validation requires ready harness, got {lifecycle}")
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--contract-only", action="store_true")
    args = parser.parse_args()
    root = Path(args.run_dir).expanduser().resolve()
    errors: list[str] = []

    manifest = load_json(root / "run_manifest.json", errors)
    contract = load_json(root / "request_contract.json", errors)
    plan = load_json(root / "verification_plan.json", errors)
    for key in REQUIRED_MANIFEST_KEYS:
        if key not in manifest:
            errors.append(f"manifest missing key: {key}")
    validate_contract(contract, plan, errors)
    validate_harness(root, final=not args.contract_only, errors=errors)

    if args.contract_only:
        if errors:
            print("CONTRACT VALIDATION FAILED")
            for error in errors:
                print(f"- {error}")
            return 1
        print("CONTRACT VALIDATION PASSED")
        return 0

    artifacts = manifest.get("artifacts", {}) if isinstance(manifest, dict) else {}
    for key in REQUIRED_ARTIFACT_KEYS:
        value = artifacts.get(key)
        if not value:
            errors.append(f"manifest artifact missing path: {key}")
        elif not resolve_path(root, value).exists():
            errors.append(f"artifact does not exist: {key} -> {value}")

    validate_tsv_status(root / "edit_ledger.tsv", ("done", "waived"), errors, "P0/P1 ledger", {"P0", "P1"})
    validate_batch_ledger(root / "batch_ledger.tsv", contract.get("unit_limits", {}), errors)
    validate_visual_workflow(root / "batch_ledger.tsv", contract, plan, errors)

    if manifest.get("status") != "complete":
        errors.append("run_manifest status must be complete for final validation")

    if not errors:
        report = run_plan_cached(root)
        result_by_id = {row["id"]: row for row in report["results"]}
        for row in report["results"]:
            if row["required"] and not row["pass"]:
                errors.append(f"objective check failed: {row['id']} -> {row['detail']}")
        for criterion in contract.get("success_criteria", []):
            result = result_by_id.get(criterion.get("check_id"))
            if not result or not result.get("pass"):
                errors.append(f"success criterion unproven: {criterion.get('id')} {criterion.get('claim')}")

    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
