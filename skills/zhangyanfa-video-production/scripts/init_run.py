#!/usr/bin/env python3
"""Initialize a bounded, objectively verifiable video-production run."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


SUBDIRS = (
    "narration",
    "captions",
    "hyperframes/project",
    "hyperframes/chunks",
    "hyperframes/qa",
    "hyperframes/stress",
    "hyperframes/proxy",
    "sources",
    "visuals/contact_sheets",
    "visuals/selected_evidence",
    "visuals/contact_sheets_final",
    "visuals/candidate_review",
    "visuals/patches",
    "visuals/aesthetic_review",
    "visuals/snapshots",
    "audio",
    "qa",
    "harness/checkpoints",
    "harness/checks",
    "harness/phase_seals",
)
MUSIC_SOURCE_ROOT = str(
    Path(os.environ.get("AI_VIDEO_MUSIC_ROOT") or (Path.home() / "Music")).expanduser().resolve()
)
SOURCE_PROXY_CACHE_ROOT = str(
    Path(
        os.environ.get("AI_VIDEO_SOURCE_PROXY_CACHE_ROOT")
        or (Path.home() / "Movies" / "AI-Video-Source-Proxies")
    )
    .expanduser()
    .resolve()
)


def write_if_missing(path: Path, text: str) -> None:
    if not path.exists():
        path.write_text(text, encoding="utf-8")


def parse_criterion(value: str, index: int) -> dict[str, str]:
    if "::" not in value:
        raise argparse.ArgumentTypeError("success criteria must use CLAIM::CHECK_ID")
    claim, check_id = (part.strip() for part in value.rsplit("::", 1))
    if not claim or not check_id:
        raise argparse.ArgumentTypeError("success criteria require both CLAIM and CHECK_ID")
    return {"id": f"SC{index:03d}", "claim": claim, "check_id": check_id, "kind": "objective"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, help="Run directory")
    parser.add_argument("--title", required=True, help="Video or draft title")
    parser.add_argument("--objective", required=True, help="One falsifiable production objective")
    parser.add_argument("--deliverable", required=True, help="One concrete deliverable")
    parser.add_argument("--in-scope", action="append", required=True, help="Repeat for each in-scope item")
    parser.add_argument("--out-of-scope", action="append", required=True, help="Repeat for each excluded item")
    parser.add_argument(
        "--success-criterion",
        action="append",
        required=True,
        help="Repeat as CLAIM::CHECK_ID; every criterion must name its objective check",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    for subdir in SUBDIRS:
        (root / subdir).mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()
    contract_path = root / "request_contract.json"
    if not contract_path.exists():
        criteria = [parse_criterion(value, index) for index, value in enumerate(args.success_criterion, start=1)]
        contract = {
            "title": args.title,
            "status": "locked",
            "objective": args.objective,
            "deliverable": args.deliverable,
            "scope": {"in_scope": args.in_scope, "out_of_scope": args.out_of_scope},
            "bgm_policy": {
                "source_root": MUSIC_SOURCE_ROOT,
                "allow_external_sources": False,
                "allow_generated_sources": False,
            },
            "render_policy": {
                "required_engine": "hyperframes",
                "required_for_video_generation": True,
                "minimum_cli_version": "0.7.101",
                "macos_preferred_encoder": "h264_videotoolbox",
                "standard_profile": "hyperframes_chunked_videotoolbox_v1",
                "low_disk_profile": "hyperframes_low_disk_stream_v1",
                "minimum_free_gib_after_render": 20,
                "forbid_full_frame_sequence": True,
                "jianying_picture_master_audio_policy": "video_only",
                "source_proxy": {
                    "profile": "1080p_cfr30_h264_gop30_yuv420p_bt709_v1",
                    "width": 1920,
                    "height": 1080,
                    "fps": 30,
                    "codec": "h264",
                    "pixel_format": "yuv420p",
                    "color_space": "bt709",
                    "color_primaries": "bt709",
                    "color_transfer": "bt709",
                    "max_gop_frames": 30,
                    "cache_root": SOURCE_PROXY_CACHE_ROOT,
                    "require_outside_icloud": True,
                },
            },
            "success_criteria": criteria,
            "workflow_profiles": {
                "visual_matching": "indexed_bulk_reviewed_v1",
                "video_rendering": "hyperframes_proxy_gated_v2",
            },
            "unit_limits": {
                "voxcpm_segments_per_batch": 1,
                "caption_rows_per_batch": 10,
                "match_rows_per_batch": 1,
                "visual_indexes_per_batch": 1,
                "match_plans_per_batch": 1,
                "match_review_bundles_per_batch": 1,
                "match_repair_sets_per_batch": 1,
                "picture_masters_per_batch": 1,
                "picture_patches_per_batch": 1,
                "source_proxy_manifests_per_batch": 1,
                "hyperframes_stress_tests_per_batch": 1,
                "aesthetic_proxy_approvals_per_batch": 1,
                "cards_per_batch": 1,
                "bgm_sections_per_batch": 1,
                "offline_artifacts_per_batch": 1,
                "live_timeline_mutations_per_batch": 1,
                "narration_loop_items_per_batch": 50,
            },
            "stop_conditions": [
                "a required objective check fails",
                "a required input is missing or invalid",
                f"a planned BGM source is outside {MUSIC_SOURCE_ROOT}",
                "the next action needs authority outside the contract",
                "a live-project mutation cannot be recovered or verified",
            ],
        }
        contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    visual_check_template = {
        "schema_version": 1,
        "workflow_profile": "indexed_bulk_reviewed_v1",
        "video_rendering_profile": "hyperframes_proxy_gated_v2",
        "instructions": (
            "Copy the needed checks into verification_plan.json, replace "
            "versioned paths before rebind, and keep every required flag."
        ),
        "checks": [
            {
                "id": "source_proxy_manifest_current",
                "type": "source_proxy_manifest_integrity",
                "path": "sources/proxy_manifest.json",
                "contract_path": "request_contract.json",
                "required_profile": "1080p_cfr30_h264_gop30_yuv420p_bt709_v1",
                "verify_source_sha256": True,
                "verify_proxy_sha256": True,
                "verify_max_gop_frames": True,
                "check_full_decode": True,
                "observes_mutations": ["offline.visual.source_proxy"],
                "observed_targets": [
                    "sources/proxy_manifest.json",
                    SOURCE_PROXY_CACHE_ROOT,
                ],
            },
            {
                "id": "visual_index_current",
                "type": "visual_index_integrity",
                "path": "visuals/shot_index.tsv",
                "ocr_index_path": "visuals/shot_ocr_index.tsv",
                "source_manifest_path": "visuals/source_identity_manifest.json",
                "contact_sheet_manifest_path": "visuals/contact_sheets/manifest.json",
                "proxy_manifest_path": "sources/proxy_manifest.json",
                "require_frame_files": True,
                "verify_source_sha256": True,
                "observes_mutations": ["offline.visual.index"],
                "observed_targets": [
                    "visuals/shot_index.tsv",
                    "visuals/shot_ocr_index.tsv",
                    "visuals/source_identity_manifest.json",
                ],
            },
            {
                "id": "visual_match_plan_current",
                "type": "visual_match_plan_integrity",
                "path": "visuals/match_sheet.tsv",
                "canonical_srt_path": "captions/canonical.srt",
                "manifest_path": "visuals/match_plan_manifest.json",
                "candidate_pool_path": "visuals/candidate_pool.jsonl",
                "shot_index_path": "visuals/shot_index.tsv",
                "ocr_index_path": "visuals/shot_ocr_index.tsv",
                "source_manifest_path": "visuals/source_identity_manifest.json",
                "require_manifest": True,
                "require_candidate_pool": True,
                "require_candidate_pool_evidence": True,
                "required_qa_status": "machine_proposed",
                "min_pool_candidates": 8,
                "preferred_pool_candidates": 12,
                "normal_pool_max_candidates": 12,
                "risk_pool_max_candidates": 32,
                "candidate_pool_granularity": "semantic_visual_units_v2",
                "require_candidate_shortfall_evidence": True,
                "require_candidate_ids": True,
                "require_index_binding": True,
                "require_semantic_visual_units": True,
                "min_semantic_unit_duration_seconds": 4,
                "max_semantic_unit_duration_seconds": 8,
                "observes_mutations": ["offline.visual.match_plan"],
                "observed_targets": [
                    "visuals/match_sheet.tsv",
                    "visuals/candidate_pool.jsonl",
                    "visuals/match_plan_manifest.json",
                ],
            },
            {
                "id": "visual_review_current",
                "type": "visual_selection_review_integrity",
                "path": "visuals/review_manifest.json",
                "match_sheet_path": "visuals/match_sheet.tsv",
                "evidence_manifest_path": "visuals/candidate_review/selected_evidence_manifest.tsv",
                "candidate_pool_path": "visuals/candidate_pool.jsonl",
                "source_manifest_path": "visuals/source_identity_manifest.json",
                "require_contact_sheets": True,
                "require_range_reviews": True,
                "require_named_identity": True,
                "require_opening_review": True,
                "require_ending_review": True,
                "require_layered_review": True,
                "require_risk_frame_matrix": True,
                "require_candidate_pool_binding": True,
                "require_source_manifest_binding": True,
                "review_granularity": "semantic_visual_units_v2",
                "candidate_pool_granularity": "semantic_visual_units_v2",
                "allow_unresolved": True,
                "observes_mutations": ["offline.visual.review"],
                "observed_targets": [
                    "visuals/review_manifest.json",
                    "visuals/candidate_review/selected_evidence_manifest.tsv",
                ],
            },
            {
                "id": "visual_repair_current",
                "type": "visual_match_repair_integrity",
                "path": "visuals/repair_result.json",
                "before_match_sheet_path": "visuals/snapshots/match_sheet.before.tsv",
                "after_match_sheet_path": "visuals/match_sheet.tsv",
                "canonical_srt_path": "captions/canonical.srt",
                "review_manifest_path": "visuals/review_manifest.json",
                "before_candidate_pool_path": "visuals/snapshots/candidate_pool.before.jsonl",
                "after_candidate_pool_path": "visuals/candidate_pool.jsonl",
                "source_manifest_path": "visuals/source_identity_manifest.json",
                "require_repair_evidence": True,
                "require_candidate_pool_evidence": True,
                "min_pool_candidates": 8,
                "preferred_pool_candidates": 12,
                "normal_pool_max_candidates": 12,
                "risk_pool_max_candidates": 32,
                "candidate_pool_granularity": "semantic_visual_units_v2",
                "review_granularity": "semantic_visual_units_v2",
                "require_candidate_shortfall_evidence": True,
                "require_repair_sequence_gates": True,
                "require_source_manifest_binding": True,
                "require_semantic_visual_units": True,
                "min_semantic_unit_duration_seconds": 4,
                "max_semantic_unit_duration_seconds": 8,
                "observes_mutations": ["offline.visual.repair"],
                "observed_targets": [
                    "visuals/repair_result.json",
                    "visuals/match_sheet.tsv",
                    "visuals/candidate_pool.jsonl",
                ],
            },
            {
                "id": "hyperframes_stress_test_current",
                "type": "hyperframes_stress_test_integrity",
                "path": "hyperframes/stress/stress_manifest.json",
                "sample_path": "hyperframes/stress/stress_sample.mp4",
                "source_proxy_manifest_path": "sources/proxy_manifest.json",
                "match_sheet_path": "visuals/match_sheet.tsv",
                "composition_path": "hyperframes/composition.json",
                "render_plan_path": "hyperframes/render_plan.json",
                "required_engine": "hyperframes",
                "minimum_duration_seconds": 30,
                "maximum_duration_seconds": 60,
                "check_full_decode": True,
                "check_black_frames": True,
                "check_transition_seams": True,
                "required_risk_classes": [
                    "shortest_unit",
                    "hard_cut",
                    "media_element_activation",
                ],
                "require_all_declared_asset_classes": True,
                "observes_mutations": ["offline.picture.stress_test"],
                "observed_targets": [
                    "hyperframes/stress/stress_manifest.json",
                    "hyperframes/stress/stress_sample.mp4",
                ],
            },
            {
                "id": "aesthetic_proxy_approval_current",
                "type": "aesthetic_proxy_approval_integrity",
                "path": "visuals/aesthetic_review/approval.json",
                "proxy_path": "hyperframes/proxy/aesthetic_proxy_720p.mp4",
                "stress_manifest_path": "hyperframes/stress/stress_manifest.json",
                "match_sheet_path": "visuals/match_sheet.tsv",
                "composition_path": "hyperframes/composition.json",
                "render_plan_path": "hyperframes/render_plan.json",
                "required_engine": "hyperframes",
                "expected_width": 1280,
                "expected_height": 720,
                "require_opening_review": True,
                "require_middle_review": True,
                "require_ending_review": True,
                "required_decisions": [
                    "opening_structure",
                    "ending_structure",
                    "geometry",
                    "typography",
                    "motion",
                    "pace",
                    "uid",
                    "framing",
                ],
                "observes_mutations": ["offline.picture.aesthetic_proxy"],
                "observed_targets": [
                    "visuals/aesthetic_review/approval.json",
                    "hyperframes/proxy/aesthetic_proxy_720p.mp4",
                ],
            },
            {
                "id": "picture_master_current",
                "type": "picture_master_integrity",
                "path": "visuals/picture_only_current.mp4",
                "manifest_path": "visuals/render_manifest.json",
                "match_sheet_path": "visuals/match_sheet.tsv",
                "approval_path": "visuals/review_manifest.json",
                "timing_contract_path": "timing_contract.json",
                "segment_manifest_path": "visuals/render_segment_manifest.tsv",
                "aesthetic_proxy_approval_path": "visuals/aesthetic_review/approval.json",
                "composition_path": "hyperframes/composition.json",
                "render_plan_path": "hyperframes/render_plan.json",
                "check_black_frames": True,
                "check_full_decode": True,
                "check_transition_seams": True,
                "render_unit_mode": "semantic_visual_units_v2",
                "require_segment_manifest": True,
                "require_approval_match_binding": True,
                "require_approval_sequence_gates": True,
                "observes_mutations": ["offline.picture.render"],
                "observed_targets": [
                    "visuals/picture_only_current.mp4",
                    "visuals/render_manifest.json",
                    "visuals/render_segment_manifest.tsv",
                ],
            },
            {
                "id": "picture_patch_current",
                "type": "picture_patch_integrity",
                "path": "visuals/patches/patch_manifest.json",
                "before_match_sheet_path": "visuals/snapshots/match_sheet.before_patch.tsv",
                "after_match_sheet_path": "visuals/match_sheet.tsv",
                "timing_contract_path": "timing_contract.json",
                "repair_approval_path": "visuals/repair_result.json",
                "base_approval_path": "visuals/render_manifest.json",
                "base_picture_path": "visuals/picture_only_current.mp4",
                "output_picture_path": "visuals/patches/picture_only_patched.mp4",
                "base_segment_manifest_path": "visuals/render_segment_manifest.tsv",
                "output_segment_manifest_path": "visuals/patches/output_segment_manifest.tsv",
                "chunk_verification_manifest_path": "visuals/patches/chunk_verification_manifest.json",
                "require_segment_manifests": False,
                "check_black_frames": True,
                "patch_verification_mode": "chunk_scoped_v2",
                "verify_decoded_segment_hashes": False,
                "verify_unchanged_chunk_sha256": True,
                "verify_changed_chunk_decoded_frames": True,
                "check_final_decode": True,
                "check_transition_seams": True,
                "observes_mutations": ["offline.picture.patch"],
                "observed_targets": [
                    "visuals/patches/patch_manifest.json",
                    "visuals/patches/picture_only_patched.mp4",
                ],
            },
        ],
    }
    write_if_missing(
        root / "visuals/indexed_bulk_checks.template.json",
        json.dumps(visual_check_template, ensure_ascii=False, indent=2) + "\n",
    )

    plan_path = root / "verification_plan.json"
    if not plan_path.exists():
        plan = {
            "checks": [
                {
                    "id": "request_contract_exists",
                    "type": "file_nonempty",
                    "path": "request_contract.json",
                    "observes_mutations": ["offline.artifact"],
                    "observed_targets": ["request_contract.json"],
                },
                {
                    "id": "run_manifest_exists",
                    "type": "file_nonempty",
                    "path": "run_manifest.json",
                    "observes_mutations": ["offline.artifact"],
                    "observed_targets": ["run_manifest.json"],
                },
                {
                    "id": "edit_ledger_exists",
                    "type": "file_nonempty",
                    "path": "edit_ledger.tsv",
                    "observes_mutations": ["offline.artifact"],
                    "observed_targets": ["edit_ledger.tsv"],
                },
                {
                    "id": "batch_ledger_exists",
                    "type": "file_nonempty",
                    "path": "batch_ledger.tsv",
                    "observes_mutations": ["offline.artifact"],
                    "observed_targets": ["batch_ledger.tsv"],
                },
                {
                    "id": "bgm_sources_within_music",
                    "type": "bgm_sources_within_root",
                    "path": "audio/bgm_manifest.json",
                    "source_root": MUSIC_SOURCE_ROOT,
                    "required": True,
                    "observes_mutations": ["offline.artifact"],
                    "observed_targets": ["audio/bgm_manifest.json", "sections[].source"],
                },
                {
                    "id": "timing_contract_live_clock",
                    "type": "json_assert",
                    "path": "timing_contract.json",
                    "required_fields": [
                        "fps",
                        "target_frame_count",
                        "target_seconds",
                        "target_timecode",
                        "clock_source",
                        "source_live_observation",
                    ],
                    "assertions": [
                        {
                            "field": "clock_source",
                            "op": "eq",
                            "value": "verified_live_jianying_narration_end",
                        },
                        {"field": "target_frame_count", "op": "gte", "value": 1},
                    ],
                    "observes_mutations": ["offline.artifact"],
                    "observed_targets": [
                        "timing_contract.json",
                        "source_live_observation.sha256",
                    ],
                },
                {
                    "id": "caption_raw_backup_exists",
                    "type": "file_nonempty",
                    "path": "captions/captions_matched_raw.srt",
                    "observes_mutations": ["live.caption.export_backup"],
                    "observed_targets": ["captions/captions_matched_raw.srt"],
                },
                {
                    "id": "acceptance_report_exists",
                    "type": "file_nonempty",
                    "path": "acceptance_report.md",
                    "observes_mutations": ["offline.artifact"],
                    "observed_targets": ["acceptance_report.md"],
                },
            ]
        }
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest_path = root / "run_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["updated_at"] = now
        manifest.setdefault("title", args.title)
    else:
        manifest = {
            "title": args.title,
            "created_at": now,
            "updated_at": now,
            "current_phase": "intake",
            "status": "in_progress",
            "workspace": str(root.parent),
            "jianying_draft": "",
            "project_timecode": "",
            "bgm_source_root": MUSIC_SOURCE_ROOT,
            "workflow_profiles": {
                "visual_matching": "indexed_bulk_reviewed_v1",
                "video_rendering": "hyperframes_proxy_gated_v2",
            },
            "export_authorized": False,
            "artifacts": {
                "request_contract": str(contract_path),
                "verification_plan": str(plan_path),
                "verification_results": str(root / "qa/verification_results.json"),
                "harness_state": str(root / "harness/state.json"),
                "harness_events": str(root / "harness/events.jsonl"),
                "harness_close_result": str(root / "harness/close_result.json"),
                "batch_ledger": str(root / "batch_ledger.tsv"),
                "clean_script": "",
                "segments": "",
                "narration_manifest": "",
                "srt_backup": "",
                "visual_index_manifest": "",
                "indexed_visual_check_template": str(
                    root / "visuals/indexed_bulk_checks.template.json"
                ),
                "match_sheet": "",
                "visual_review_manifest": "",
                "picture_render_manifest": "",
                "picture_render": "",
                "picture_patch_manifest": "",
                "source_proxy_manifest": str(root / "sources/proxy_manifest.json"),
                "hyperframes_stress_manifest": str(
                    root / "hyperframes/stress/stress_manifest.json"
                ),
                "aesthetic_proxy_approval": str(
                    root / "visuals/aesthetic_review/approval.json"
                ),
                "hyperframes_project": str(root / "hyperframes/project"),
                "hyperframes_environment": str(root / "hyperframes/environment.json"),
                "hyperframes_render_plan": str(root / "hyperframes/render_plan.json"),
                "hyperframes_check_result": str(root / "hyperframes/check_result.json"),
                "hyperframes_render_manifest": str(root / "hyperframes/render_manifest.json"),
                "bgm": "",
                "bgm_manifest": str(root / "audio/bgm_manifest.json"),
                "source_ledger": str(root / "sources.tsv"),
                "edit_ledger": str(root / "edit_ledger.tsv"),
                "acceptance_audit": "",
                "acceptance_report": str(root / "acceptance_report.md"),
                "export": "",
            },
        }
    artifacts = manifest.setdefault("artifacts", {})
    manifest.setdefault("workflow_profiles", {}).setdefault(
        "visual_matching",
        "indexed_bulk_reviewed_v1",
    )
    manifest.setdefault("workflow_profiles", {}).setdefault(
        "video_rendering",
        "hyperframes_proxy_gated_v2",
    )
    artifacts.setdefault("harness_state", str(root / "harness/state.json"))
    artifacts.setdefault("harness_events", str(root / "harness/events.jsonl"))
    artifacts.setdefault("harness_close_result", str(root / "harness/close_result.json"))
    artifacts.setdefault("bgm_manifest", str(root / "audio/bgm_manifest.json"))
    artifacts.setdefault("visual_index_manifest", "")
    artifacts.setdefault("source_proxy_manifest", str(root / "sources/proxy_manifest.json"))
    artifacts.setdefault(
        "hyperframes_stress_manifest",
        str(root / "hyperframes/stress/stress_manifest.json"),
    )
    artifacts.setdefault(
        "aesthetic_proxy_approval",
        str(root / "visuals/aesthetic_review/approval.json"),
    )
    artifacts.setdefault(
        "indexed_visual_check_template",
        str(root / "visuals/indexed_bulk_checks.template.json"),
    )
    artifacts.setdefault("match_sheet", "")
    artifacts.setdefault("visual_review_manifest", "")
    artifacts.setdefault("picture_render_manifest", "")
    artifacts.setdefault("picture_render", "")
    artifacts.setdefault("picture_patch_manifest", "")
    artifacts.setdefault("hyperframes_project", str(root / "hyperframes/project"))
    artifacts.setdefault("hyperframes_environment", str(root / "hyperframes/environment.json"))
    artifacts.setdefault("hyperframes_render_plan", str(root / "hyperframes/render_plan.json"))
    artifacts.setdefault("hyperframes_check_result", str(root / "hyperframes/check_result.json"))
    artifacts.setdefault("hyperframes_render_manifest", str(root / "hyperframes/render_manifest.json"))
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    write_if_missing(
        root / "sources.tsv",
        "source_id\tpublisher\ttitle\tsource_url\tretrieved_at\trights_status\tlocal_path\tintended_line\tsource_in\tsource_out\tapplied\tnotes\n",
    )
    write_if_missing(
        root / "edit_ledger.tsv",
        "priority\tcategory\tfeedback\ttimeline_range\tplanned_edit\tassets\tacceptance_test\tstatus\n",
    )
    write_if_missing(
        root / "batch_ledger.tsv",
        "batch_id\tphase\tassumption\tscope\tmutation\tunit_limit_key\tunit_count\tcheck_id\texpected\tmeasured\tstatus\tevidence\twaiver_reason\tsuperseded_by\topened_at\tclosed_at\n",
    )
    write_if_missing(root / "acceptance_report.md", f"# {args.title} 验收报告\n\n## 结论\n\n待验收。\n")
    harness_state = root / "harness/state.json"
    if not harness_state.exists():
        from harness import append_event, initial_state

        state = initial_state(root, manifest.get("current_phase", "intake"))
        append_event(root, state, "HARNESS_INITIALIZED", phase=state["phase"], source="init_run.py")
        harness_state.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
