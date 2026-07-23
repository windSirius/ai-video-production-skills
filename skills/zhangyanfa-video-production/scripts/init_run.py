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
    "visuals/contact_sheets",
    "audio",
    "qa",
    "harness/checkpoints",
    "harness/checks",
    "harness/phase_seals",
)
MUSIC_SOURCE_ROOT = str(
    Path(os.environ.get("AI_VIDEO_MUSIC_ROOT") or (Path.home() / "Music")).expanduser().resolve()
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
            "success_criteria": criteria,
            "unit_limits": {
                "voxcpm_segments_per_batch": 1,
                "caption_rows_per_batch": 10,
                "match_rows_per_batch": 1,
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
                "match_sheet": "",
                "picture_render": "",
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
    artifacts.setdefault("harness_state", str(root / "harness/state.json"))
    artifacts.setdefault("harness_events", str(root / "harness/events.jsonl"))
    artifacts.setdefault("harness_close_result", str(root / "harness/close_result.json"))
    artifacts.setdefault("bgm_manifest", str(root / "audio/bgm_manifest.json"))
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
