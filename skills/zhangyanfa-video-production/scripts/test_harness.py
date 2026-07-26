#!/usr/bin/env python3
"""Regression tests for the production transaction harness."""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from run_objective_checks import (
    CAPTION_FORBIDDEN_TERMINAL_PUNCTUATION,
    CAPTION_TRAILING_CLOSING_MARKS,
    decoded_frame_hashes,
    file_sha256,
    frame_slice_sha256,
    read_tsv,
    run_check,
)
from validate_run import validate_batch_ledger
from harness import (
    ACTION_REGISTRY,
    SCHEMA_VERSION,
    UI_HIT_TEST_MAX_AGE_SECONDS,
    UI_ROUTE_SCHEMA_VERSION,
    compare_observations,
    fingerprint,
    sha256_file,
    utc_now,
    validate_caption_terminal_punctuation_policy,
    validate_caption_transaction,
    validate_prerequisite_config_bindings,
    validate_required_ui_route_checkpoints,
)


INIT = SCRIPT_DIR / "init_run.py"
HARNESS = SCRIPT_DIR / "harness.py"
VALIDATE = SCRIPT_DIR / "validate_run.py"
FREEZE_TIMING = SCRIPT_DIR / "freeze_live_timing_contract.py"


def observation(draft_name: str = "测试草稿") -> dict:
    return {
        "app_bundle_version": "9.9.9-test",
        "window_signature": "1920x1080-main-v1",
        "ui_recipe_profile": "test-profile-v1",
        "ui_recipe_calibrated": True,
        "draft_name": draft_name,
        "timeline_name": "时间线 01",
        "timeline_count": 1,
        "project_timecode": "00:01:00:00",
        "caption_track_count": 1,
        "caption_count": 10,
        "narration_track_count": 1,
        "narration_clip_count": 2,
        "picture_track_count": 1,
        "picture_clip_count": 1,
        "bgm_track_count": 1,
        "bgm_clip_count": 1,
        "protected_tracks_locked": True,
        "authoritative_timeline": True,
    }


class HarnessTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "run"
        completed = self.run_command(
            INIT,
            "--root",
            self.root,
            "--title",
            "测试",
            "--objective",
            "得到一个可验证草稿",
            "--deliverable",
            "草稿",
            "--in-scope",
            "剪映草稿",
            "--out-of-scope",
            "最终导出",
            "--success-criterion",
            "合同存在::request_contract_exists",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_command(self, script: Path, *args: object) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *[str(value) for value in args]],
            capture_output=True,
            text=True,
            check=False,
        )

    def write_json(self, name: str, value: object) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def evidence(self, name: str) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((name * 8).encode("utf-8"))
        return path

    def write_tsv(
        self, name: str, fieldnames: list[str], rows: list[dict[str, object]]
    ) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=fieldnames,
                delimiter="\t",
                lineterminator="\n",
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(rows)
        return path

    def visual_fixture(self) -> dict[str, object]:
        canonical = self.root / "captions/canonical.srt"
        canonical.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n角色甲作出回答\n\n"
            "2\n00:00:01,000 --> 00:00:02,000\n故事走向尾声\n",
            encoding="utf-8",
        )
        source_a = self.evidence("visual_sources/source_a.mp4")
        source_b = self.evidence("visual_sources/source_b.mp4")
        source_c = self.evidence("visual_sources/source_c.mp4")
        fields = [
            "line_id",
            "caption_start",
            "caption_end",
            "duration",
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
            "selected_candidate",
            "match_reason",
            "confidence",
            "retry_round",
            "reuse_group",
            "qa_status",
            "named_entities_expected",
        ]
        rows = [
            {
                "line_id": 1,
                "caption_start": "0.000",
                "caption_end": "1.000",
                "duration": "1.000",
                "text": "角色甲作出回答",
                "candidate_a": "SRC_A|0.0-1.0|king",
                "candidate_a_score": "9.0",
                "candidate_b": "SRC_B|0.0-1.0|reaction",
                "candidate_b_score": "8.0",
                "candidate_c": "SRC_C|0.0-1.0|wide",
                "candidate_c_score": "7.0",
                "source_id": "SRC_A",
                "source_file": str(source_a),
                "source_in": "0.000",
                "source_out": "1.000",
                "selected_candidate": "A",
                "match_reason": "人物、动作与台词一致",
                "confidence": "high",
                "retry_round": "1",
                "reuse_group": "SRC_A:0001",
                "qa_status": "verified",
                "named_entities_expected": "角色甲",
            },
            {
                "line_id": 2,
                "caption_start": "1.000",
                "caption_end": "2.000",
                "duration": "1.000",
                "text": "故事走向尾声",
                "candidate_a": "SRC_B|1.0-2.0|farewell",
                "candidate_a_score": "9.0",
                "candidate_b": "SRC_C|1.0-2.0|wide",
                "candidate_b_score": "8.0",
                "candidate_c": "SRC_A|1.0-2.0|motif",
                "candidate_c_score": "7.0",
                "source_id": "SRC_B",
                "source_file": str(source_b),
                "source_in": "1.000",
                "source_out": "2.000",
                "selected_candidate": "A",
                "match_reason": "结尾情绪与最终意象一致",
                "confidence": "high",
                "retry_round": "1",
                "reuse_group": "SRC_B:0002",
                "qa_status": "verified",
                "named_entities_expected": "",
            },
        ]
        match_sheet = self.write_tsv("visuals/match_sheet.tsv", fields, rows)
        match_manifest = self.write_json(
            "visuals/match_plan_manifest.json",
            {
                "schema_version": 1,
                "status": "PASS",
                "canonical_srt_sha256": file_sha256(canonical),
                "match_sheet_sha256": file_sha256(match_sheet),
                "row_count": 2,
            },
        )
        evidence_1 = self.evidence("visuals/selected_evidence/cue_001.jpg")
        evidence_2 = self.evidence("visuals/selected_evidence/cue_002.jpg")
        evidence_fields = [
            "line_id",
            "caption",
            "source_id",
            "source_file",
            "source_in",
            "source_out",
            "evidence_image",
            "black_midpoint",
            "visual_review",
        ]
        evidence_rows = [
            {
                "line_id": 1,
                "caption": rows[0]["text"],
                "source_id": rows[0]["source_id"],
                "source_file": rows[0]["source_file"],
                "source_in": rows[0]["source_in"],
                "source_out": rows[0]["source_out"],
                "evidence_image": str(evidence_1),
                "black_midpoint": "False",
                "visual_review": "approved_manual",
            },
            {
                "line_id": 2,
                "caption": rows[1]["text"],
                "source_id": rows[1]["source_id"],
                "source_file": rows[1]["source_file"],
                "source_in": rows[1]["source_in"],
                "source_out": rows[1]["source_out"],
                "evidence_image": str(evidence_2),
                "black_midpoint": "False",
                "visual_review": "approved_manual",
            },
        ]
        evidence_manifest = self.write_tsv(
            "visuals/selected_evidence_manifest.tsv",
            evidence_fields,
            evidence_rows,
        )
        contact = self.evidence("visuals/contact_sheets_final/selected_01.jpg")
        review_manifest = self.write_json(
            "visuals/selected_review_manifest.json",
            {
                "schema_version": 1,
                "status": "PASS",
                "match_sheet_sha256": file_sha256(match_sheet),
                "evidence_manifest_sha256": file_sha256(evidence_manifest),
                "row_count": 2,
                "contact_sheets": [str(contact)],
                "range_reviews": [{"range": "1-2", "status": "PASS"}],
                "identity_checks": [
                    {
                        "cue_id": 1,
                        "expected": ["角色甲"],
                        "visible": ["角色甲"],
                        "status": "PASS",
                    }
                ],
                "unresolved_cue_ids": [],
            },
        )
        return {
            "canonical": canonical,
            "sources": [source_a, source_b, source_c],
            "fields": fields,
            "rows": rows,
            "match_sheet": match_sheet,
            "match_manifest": match_manifest,
            "evidence_manifest": evidence_manifest,
            "review_manifest": review_manifest,
        }

    def ui_target(
        self,
        *,
        name: str,
        identifier: str,
        visible_text: str,
        x: int = 100,
        y: int = 100,
        include_geometry: bool = False,
    ) -> dict:
        target = {
            "role": "AXButton",
            "name": name,
            "identifier": identifier,
            "visible_text": visible_text,
            "ancestor_path": [
                {
                    "role": "AXWindow",
                    "name": "剪映专业版主窗口",
                    "identifier": "jianying-main-window",
                }
            ],
        }
        if include_geometry:
            target["bounds"] = {"x": x, "y": y, "width": 120, "height": 40}
            target["hit_test_point"] = {"x": x + 20, "y": y + 20}
        return target

    def materialize_step(self, step: dict, *, x: int = 100, y: int = 100) -> dict:
        result = json.loads(json.dumps(step, ensure_ascii=False))
        result["target"].setdefault("bounds", {"x": x, "y": y, "width": 120, "height": 40})
        result["target"].setdefault("hit_test_point", {"x": x + 20, "y": y + 20})
        return result

    def route_preflight(
        self,
        observation_path: Path,
        evidence_paths: list[Path],
        name: str = "ui_route_preflight.json",
        *,
        status: str = "available",
        target_visible_text: str = "草稿名输入框",
        action_key: str = "rename_unicode",
        recipe_id: str = "jianying.ax-or-clipboard-unicode.v1",
        method: str = "accessibility",
        steps: list[dict] | None = None,
        binding_overrides: dict[str, object] | None = None,
    ) -> Path:
        live_observation = json.loads(observation_path.read_text(encoding="utf-8"))
        binding = {
            "action_key": action_key,
            "recipe_id": recipe_id,
            "required_control": ACTION_REGISTRY[action_key]["ui_required_control"],
            "window_signature": live_observation["window_signature"],
            "ui_recipe_profile": live_observation["ui_recipe_profile"],
            "pre_observation_sha256": sha256_file(observation_path),
            "evidence_sha256": sorted(sha256_file(path) for path in evidence_paths),
        }
        binding.update(binding_overrides or {})
        planned_steps = json.loads(json.dumps(steps, ensure_ascii=False)) if steps is not None else [
            {
                "sequence": 1,
                "action": "press",
                "target": self.ui_target(
                    name="确认改名",
                    identifier="rename-confirm",
                    visible_text=target_visible_text,
                ),
            }
        ]
        for step in planned_steps:
            step.setdefault("window_signature", live_observation["window_signature"])
        return self.write_json(
            name,
            {
                "schema_version": UI_ROUTE_SCHEMA_VERSION,
                "captured_at": utc_now(),
                **binding,
                "status": status,
                "selected_route": {
                    "route_id": ACTION_REGISTRY[action_key]["ui_route_id"],
                    "method": method,
                    "steps": planned_steps,
                },
                "visible_forbidden_regions": [
                    {
                        "label": "试试剪映助手",
                        "bounds": {"x": 1600, "y": 900, "width": 260, "height": 80},
                    }
                ],
                "forbidden_targets_interacted": [],
            },
        )

    def interaction_trace(
        self,
        token: str,
        name: str,
        *,
        events: list[dict] | None = None,
        coverage_complete: bool = True,
    ) -> Path:
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        action = state["open_action"]
        route = action["ui_route_preflight"]
        trace_path = Path(action["ui_execution"]["trace_path"])
        if not coverage_complete:
            return trace_path
        planned_inputs = events if events is not None else route["planned_step_inputs"]
        for index, step in enumerate(planned_inputs, start=1):
            actual_step = self.materialize_step(step, x=100 + index * 10, y=100 + index * 10)
            hit_test = self.write_json(
                f"{name}.hit-{index}.json",
                {
                    "schema_version": UI_ROUTE_SCHEMA_VERSION,
                    "observed_at": utc_now(),
                    "window_signature": actual_step["window_signature"],
                    "step": actual_step,
                    "visible_forbidden_regions": [
                        {
                            "label": region["label"][0],
                            "bounds": region["bounds"],
                        }
                        for region in route["visible_forbidden_regions"]
                    ],
                },
            )
            authorized = self.run_command(
                HARNESS,
                "authorize-ui-step",
                self.root,
                "--token",
                token,
                "--hit-test",
                hit_test,
            )
            self.assertEqual(authorized.returncode, 0, authorized.stderr)
            authorization_token = json.loads(authorized.stdout)["authorization_token"]
            evidence = self.evidence(f"{name}.step-{index}.png")
            completed = self.run_command(
                HARNESS,
                "complete-ui-step",
                self.root,
                "--token",
                token,
                "--authorization",
                authorization_token,
                "--evidence",
                evidence,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
        return trace_path

    def authorize_ui_step(
        self,
        token: str,
        name: str,
        step: dict,
        *,
        visible_forbidden_regions: list[dict] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        action = state["open_action"]
        route = action["ui_route_preflight"]
        sequence = int(action["ui_execution"]["next_sequence"])
        step = json.loads(json.dumps(step, ensure_ascii=False))
        step.setdefault("window_signature", route["planned_step_inputs"][sequence - 1]["window_signature"])
        actual_step = self.materialize_step(step)
        hit_test = self.write_json(
            name,
            {
                "schema_version": UI_ROUTE_SCHEMA_VERSION,
                "observed_at": utc_now(),
                "window_signature": actual_step["window_signature"],
                "step": actual_step,
                "visible_forbidden_regions": visible_forbidden_regions
                if visible_forbidden_regions is not None
                else [
                    {"label": region["label"][0], "bounds": region["bounds"]}
                    for region in route["visible_forbidden_regions"]
                ],
            },
        )
        return self.run_command(
            HARNESS,
            "authorize-ui-step",
            self.root,
            "--token",
            token,
            "--hit-test",
            hit_test,
        )

    def run_prepare_rename(
        self,
        pre: Path,
        pre_evidence: Path,
        preflight: Path,
        expected_name: str = "新草稿",
    ) -> subprocess.CompletedProcess[str]:
        return self.run_command(
            HARNESS,
            "prepare",
            self.root,
            "--action-key",
            "rename_unicode",
            "--recipe-id",
            "jianying.ax-or-clipboard-unicode.v1",
            "--assumption",
            "AX 改名可见",
            "--scope",
            "草稿名",
            "--unit-limit-key",
            "live_timeline_mutations_per_batch",
            "--unit-count",
            1,
            "--check-id",
            "harness_live_state_delta",
            "--observation",
            pre,
            "--evidence",
            pre_evidence,
            "--ui-route-preflight",
            preflight,
            "--expect",
            f"draft_name={expected_name}",
        )

    def prepare_rename(self, expected_name: str = "新草稿") -> str:
        pre = self.write_json("pre.json", observation())
        pre_evidence = self.evidence("pre.png")
        preflight = self.route_preflight(pre, [pre_evidence])
        completed = self.run_prepare_rename(pre, pre_evidence, preflight, expected_name)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        return state["open_action"]["token"]

    def test_live_action_passes_only_after_exact_delta(self) -> None:
        token = self.prepare_rename()
        first = self.run_command(HARNESS, "begin", self.root, "--token", token)
        self.assertEqual(first.returncode, 0, first.stderr)
        repeated = self.run_command(HARNESS, "begin", self.root, "--token", token)
        self.assertEqual(repeated.returncode, 2)

        trace = self.interaction_trace(token, "trace-pass.json")
        post = self.write_json("post.json", observation("新草稿"))
        post_evidence = self.evidence("post.png")
        verified = self.run_command(
            HARNESS,
            "verify",
            self.root,
            "--token",
            token,
            "--observation",
            post,
            "--evidence",
            post_evidence,
            "--ui-interaction-trace",
            trace,
            "--measured",
            "草稿名已变化，其余字段不变",
        )
        self.assertEqual(verified.returncode, 0, verified.stderr)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "ready")
        self.assertIsNone(state["open_action"])
        ledger = (self.root / "batch_ledger.tsv").read_text(encoding="utf-8")
        self.assertIn("\tpass\t", ledger)

    def test_second_identical_no_change_blocks(self) -> None:
        token = self.prepare_rename()
        self.assertEqual(self.run_command(HARNESS, "begin", self.root, "--token", token).returncode, 0)
        rollback = self.write_json("rollback1.json", observation())
        evidence = self.evidence("fail1.png")
        trace = self.interaction_trace(token, "trace-fail-1.json")
        failed = self.run_command(
            HARNESS,
            "fail",
            self.root,
            "--token",
            token,
            "--reason-code",
            "no_change",
            "--detail",
            "UI 无变化",
            "--evidence",
            evidence,
            "--ui-interaction-trace",
            trace,
            "--observation",
            rollback,
            "--rolled-back",
        )
        self.assertEqual(failed.returncode, 1)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "repair_required")
        retry_token = state["open_action"]["token"]

        self.assertEqual(self.run_command(HARNESS, "begin", self.root, "--token", retry_token).returncode, 0)
        rollback2 = self.write_json("rollback2.json", observation())
        evidence2 = self.evidence("fail2.png")
        trace2 = self.interaction_trace(retry_token, "trace-fail-2.json")
        failed_again = self.run_command(
            HARNESS,
            "fail",
            self.root,
            "--token",
            retry_token,
            "--reason-code",
            "no_change",
            "--detail",
            "同一 recipe 再次无变化",
            "--evidence",
            evidence2,
            "--ui-interaction-trace",
            trace2,
            "--observation",
            rollback2,
            "--rolled-back",
        )
        self.assertEqual(failed_again.returncode, 1)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "blocked")
        resumed = self.run_command(HARNESS, "resume", self.root)
        self.assertEqual(resumed.returncode, 1)
        self.assertIn("request_user_decision", resumed.stdout)
        unblock_evidence = self.evidence("unblock.png")
        unblock_preflight = self.route_preflight(
            rollback2,
            [unblock_evidence],
            "unblock-route.json",
        )
        unblocked = self.run_command(
            HARNESS,
            "unblock",
            self.root,
            "--authorized-by",
            "user",
            "--reason",
            "用户明确要求在已恢复的同一状态重试",
            "--observation",
            rollback2,
            "--evidence",
            unblock_evidence,
            "--ui-route-preflight",
            unblock_preflight,
        )
        self.assertEqual(unblocked.returncode, 0, unblocked.stderr)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "repair_required")

    def test_prepare_crash_recovers_without_new_action(self) -> None:
        token = self.prepare_rename()
        state_path = self.root / "harness/state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["open_action"] = None
        state["lifecycle"] = "ready"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        resumed = self.run_command(HARNESS, "resume", self.root)
        self.assertEqual(resumed.returncode, 0)
        self.assertIn("recover_pending_transaction", resumed.stdout)
        recovered = self.run_command(HARNESS, "recover", self.root)
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "prepared")
        self.assertEqual(state["open_action"]["token"], token)

    def test_contract_drift_blocks_resume(self) -> None:
        plan_path = self.root / "verification_plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["checks"].append(
            {
                "id": "drift",
                "type": "file_exists",
                "path": "x",
                "observes_mutations": ["offline.artifact"],
                "observed_targets": ["x"],
            }
        )
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        resumed = self.run_command(HARNESS, "resume", self.root)
        self.assertEqual(resumed.returncode, 1)
        self.assertIn("verification_plan drift", resumed.stdout)
        rebound = self.run_command(
            HARNESS,
            "rebind",
            self.root,
            "--authorized-by",
            "user",
            "--reason",
            "用户明确增加验收检查",
        )
        self.assertEqual(rebound.returncode, 0, rebound.stderr)
        resumed = self.run_command(HARNESS, "resume", self.root)
        self.assertEqual(resumed.returncode, 0, resumed.stderr)

    def test_contract_only_validation_accepts_initialized_harness(self) -> None:
        completed = self.run_command(VALIDATE, self.root, "--contract-only")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_status_exposes_permanent_jianying_assistant_guardrail(self) -> None:
        completed = self.run_command(HARNESS, "resume", self.root)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        assistant = payload["global_ui_guardrails"]["forbidden_ui_targets"]["jianying_assistant"]
        self.assertEqual(assistant["policy"], "never_interact")
        self.assertIn("试试剪映助手", assistant["labels"])
        self.assertIn("剪映助手", assistant["labels"])

    def test_first_narration_clip_may_create_exactly_one_track(self) -> None:
        before = observation()
        before["narration_track_count"] = 0
        before["narration_clip_count"] = 0
        after = dict(before)
        after["narration_track_count"] = 1
        after["narration_clip_count"] = 1
        failures = compare_observations(
            before,
            after,
            ACTION_REGISTRY["append_narration_clip"]["expect"],
        )
        self.assertEqual(failures, [])

        duplicate_track = dict(after)
        duplicate_track["narration_track_count"] = 2
        failures = compare_observations(
            before,
            duplicate_track,
            ACTION_REGISTRY["append_narration_clip"]["expect"],
        )
        self.assertTrue(any("narration_track_count" in failure for failure in failures))

    def test_stale_hit_test_is_retryable_and_does_not_block(self) -> None:
        self.assertGreaterEqual(UI_HIT_TEST_MAX_AGE_SECONDS, 30)
        token = self.prepare_rename()
        begun = self.run_command(HARNESS, "begin", self.root, "--token", token)
        self.assertEqual(begun.returncode, 0, begun.stderr)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        planned = state["open_action"]["ui_route_preflight"]["planned_step_inputs"][0]
        stale_step = self.materialize_step(planned)
        stale_hit_test = self.write_json(
            "stale-hit-test.json",
            {
                "schema_version": UI_ROUTE_SCHEMA_VERSION,
                "observed_at": "2000-01-01T00:00:00+00:00",
                "window_signature": stale_step["window_signature"],
                "step": stale_step,
                "visible_forbidden_regions": [
                    {
                        "label": "试试剪映助手",
                        "bounds": {"x": 1600, "y": 900, "width": 260, "height": 80},
                    }
                ],
            },
        )
        rejected = self.run_command(
            HARNESS,
            "authorize-ui-step",
            self.root,
            "--token",
            token,
            "--hit-test",
            stale_hit_test,
        )
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("ui_evidence_stale", rejected.stderr)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "in_action")
        self.assertIsNone(state["blocked"])
        self.assertEqual(state["open_action"]["ui_execution"]["next_sequence"], 1)
        self.assertIsNone(state["open_action"]["ui_execution"]["pending_authorization"])

    def test_user_can_adopt_manual_baseline_only_before_agent_ui_steps(self) -> None:
        token = self.prepare_rename()
        begun = self.run_command(HARNESS, "begin", self.root, "--token", token)
        self.assertEqual(begun.returncode, 0, begun.stderr)
        manual = observation("用户手工推进后的草稿")
        manual["narration_clip_count"] = 22
        manual["caption_count"] = None
        manual["unresolved_measurements"] = ["caption_count"]
        manual_path = self.write_json("manual-live-baseline.json", manual)
        manual_evidence = self.evidence("manual-live-baseline.png")
        adopted = self.run_command(
            HARNESS,
            "adopt-live-baseline",
            self.root,
            "--authorized-by",
            "user",
            "--reason",
            "用户已手工推进当前剪映工程",
            "--observation",
            manual_path,
            "--evidence",
            manual_evidence,
        )
        self.assertEqual(adopted.returncode, 0, adopted.stderr)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "ready")
        self.assertIsNone(state["open_action"])
        self.assertIsNone(state["blocked"])
        self.assertEqual(
            state["adopted_live_baseline"]["checkpoint"]["observation_sha256"],
            sha256_file(
                Path(state["adopted_live_baseline"]["checkpoint"]["observation"])
            ),
        )
        ledger = (self.root / "batch_ledger.tsv").read_text(encoding="utf-8")
        self.assertIn("\tcancelled_no_mutation\t", ledger)
        contract = json.loads((self.root / "request_contract.json").read_text(encoding="utf-8"))
        ledger_errors: list[str] = []
        validate_batch_ledger(
            self.root / "batch_ledger.tsv",
            contract["unit_limits"],
            ledger_errors,
        )
        self.assertEqual(ledger_errors, [])

    def test_caption_backup_export_late_binds_unknown_caption_count(self) -> None:
        pre_observation = observation()
        pre_observation["caption_count"] = None
        pre_observation["unresolved_measurements"] = ["caption_count"]
        pre = self.write_json("caption-backup-pre.json", pre_observation)
        pre_evidence = self.evidence("caption-backup-pre.png")
        steps = [
            {
                "sequence": 1,
                "action": "press",
                "target": self.ui_target(
                    name="打开导出",
                    identifier="open-export",
                    visible_text="导出",
                ),
            },
            {
                "sequence": 2,
                "action": "press",
                "target": self.ui_target(
                    name="仅导出当前字幕备份",
                    identifier="caption-backup-export",
                    visible_text="字幕导出",
                ),
            },
            {
                "sequence": 3,
                "action": "confirm",
                "target": self.ui_target(
                    name="确认导出",
                    identifier="confirm-caption-backup-export",
                    visible_text="确认导出",
                ),
            },
        ]
        preflight = self.route_preflight(
            pre,
            [pre_evidence],
            "caption-backup-route.json",
            action_key="caption_backup_export",
            recipe_id="jianying.caption-only-export-backup.v2",
            steps=steps,
        )
        prepared = self.run_command(
            HARNESS,
            "prepare",
            self.root,
            "--action-key",
            "caption_backup_export",
            "--recipe-id",
            "jianying.caption-only-export-backup.v2",
            "--assumption",
            "可只导出当前字幕",
            "--scope",
            "原始字幕备份",
            "--unit-limit-key",
            "live_timeline_mutations_per_batch",
            "--unit-count",
            1,
            "--check-id",
            "harness_live_state_delta",
            "--objective-check-id",
            "caption_raw_backup_exists",
            "--observation",
            pre,
            "--evidence",
            pre_evidence,
            "--ui-route-preflight",
            preflight,
        )
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        token = state["open_action"]["token"]
        self.assertEqual(self.run_command(HARNESS, "begin", self.root, "--token", token).returncode, 0)
        trace = self.interaction_trace(token, "caption-backup-trace.json")

        backup = self.root / "captions/captions_matched_raw.srt"
        backup.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n测试字幕\n",
            encoding="utf-8",
        )
        post_observation = observation()
        post_observation["caption_count"] = 10
        post = self.write_json("caption-backup-post.json", post_observation)
        post_evidence = self.evidence("caption-backup-post.png")
        verified = self.run_command(
            HARNESS,
            "verify",
            self.root,
            "--token",
            token,
            "--observation",
            post,
            "--evidence",
            post_evidence,
            "--ui-interaction-trace",
            trace,
            "--measured",
            "原始字幕已导出，字幕数量完成迟绑定",
        )
        self.assertEqual(verified.returncode, 0, verified.stderr)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "ready")

    def test_manual_baseline_adoption_rejects_completed_agent_ui_step(self) -> None:
        token = self.prepare_rename()
        begun = self.run_command(HARNESS, "begin", self.root, "--token", token)
        self.assertEqual(begun.returncode, 0, begun.stderr)
        self.interaction_trace(token, "completed-before-adoption.json")
        manual_path = self.write_json("late-manual-live-baseline.json", observation("用户后续修改"))
        manual_evidence = self.evidence("late-manual-live-baseline.png")
        rejected = self.run_command(
            HARNESS,
            "adopt-live-baseline",
            self.root,
            "--authorized-by",
            "user",
            "--reason",
            "尝试在代理操作后接管",
            "--observation",
            manual_path,
            "--evidence",
            manual_evidence,
        )
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("after an agent-authorized UI step", rejected.stderr)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "in_action")
        self.assertIsNotNone(state["open_action"])

    def test_ready_run_can_record_user_authored_live_baseline(self) -> None:
        manual_path = self.write_json("ready-manual-live-baseline.json", observation("用户已完成装配"))
        manual_evidence = self.evidence("ready-manual-live-baseline.png")
        adopted = self.run_command(
            HARNESS,
            "adopt-live-baseline",
            self.root,
            "--authorized-by",
            "user",
            "--reason",
            "用户在无开放事务时手工推进工程",
            "--observation",
            manual_path,
            "--evidence",
            manual_evidence,
        )
        self.assertEqual(adopted.returncode, 0, adopted.stderr)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "ready")
        self.assertEqual(state["adopted_live_baseline"]["baseline_id"], "B0001")
        self.assertIsNone(state["adopted_live_baseline"]["cancelled_batch_id"])
        ledger_rows = (self.root / "batch_ledger.tsv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(ledger_rows), 1)

    def test_live_timing_contract_uses_measured_jianying_end(self) -> None:
        live = observation()
        live["project_timecode"] = "00:11:49:17"
        live["narration_end_timecode"] = "00:11:49:17"
        live["narration_clip_count"] = 22
        live_path = self.write_json("live-timing-state.json", live)
        output = self.root / "timing_contract.json"
        completed = self.run_command(
            FREEZE_TIMING,
            "--observation",
            live_path,
            "--output",
            output,
            "--expected-narration-clips",
            22,
            "--narration-seconds",
            709.12,
            "--caption-final-end-seconds",
            709.137,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        contract = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(contract["target_frame_count"], 42557)
        self.assertEqual(contract["target_timecode"], "00:11:49:17")
        self.assertEqual(contract["clock_source"], "verified_live_jianying_narration_end")
        self.assertEqual(contract["caption_tail_hold_frames"], 8)

        live["narration_end_timecode"] = "00:11:49:18"
        live_path.write_text(json.dumps(live, ensure_ascii=False), encoding="utf-8")
        replaced = self.run_command(
            FREEZE_TIMING,
            "--observation",
            live_path,
            "--output",
            output,
            "--expected-narration-clips",
            22,
            "--force",
        )
        self.assertEqual(replaced.returncode, 0, replaced.stderr)
        replacement = json.loads(output.read_text(encoding="utf-8"))
        self.assertTrue(Path(replacement["supersedes"]["recoverable_backup"]).is_file())

    def test_live_timing_contract_rejects_project_total_as_implicit_narration_end(self) -> None:
        live = observation()
        live["project_timecode"] = "00:11:50:00"
        live["narration_clip_count"] = 22
        live_path = self.write_json("missing-narration-end.json", live)
        completed = self.run_command(
            FREEZE_TIMING,
            "--observation",
            live_path,
            "--output",
            self.root / "unsafe-timing-contract.json",
            "--expected-narration-clips",
            22,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("requires narration_end_timecode", completed.stderr)

    def test_timing_contract_can_be_created_inside_verified_offline_action(self) -> None:
        prepared = self.run_command(
            HARNESS,
            "prepare",
            self.root,
            "--action-key",
            "offline_artifact",
            "--recipe-id",
            "offline.objective-check.v1",
            "--assumption",
            "旁白轨端点已经独立测量",
            "--scope",
            "创建 timing_contract.json",
            "--unit-limit-key",
            "offline_artifacts_per_batch",
            "--unit-count",
            1,
            "--check-id",
            "timing_contract_live_clock",
        )
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        token = json.loads(prepared.stdout)["next_action"]["token"]
        begun = self.run_command(HARNESS, "begin", self.root, "--token", token)
        self.assertEqual(begun.returncode, 0, begun.stderr)

        live = observation()
        live["project_timecode"] = "00:11:50:00"
        live["narration_end_timecode"] = "00:11:49:17"
        live["narration_clip_count"] = 22
        live_path = self.write_json("offline-timing-live-state.json", live)
        output = self.root / "timing_contract.json"
        frozen = self.run_command(
            FREEZE_TIMING,
            "--observation",
            live_path,
            "--output",
            output,
            "--expected-narration-clips",
            22,
        )
        self.assertEqual(frozen.returncode, 0, frozen.stderr)
        verified = self.run_command(
            HARNESS,
            "verify",
            self.root,
            "--token",
            token,
            "--evidence",
            output,
            "--measured",
            "旁白活体端点已冻结",
        )
        self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_blocked_non_assistant_route_receives_no_token(self) -> None:
        pre = self.write_json("blocked-pre.json", observation())
        evidence = self.evidence("blocked-pre.png")
        preflight = self.route_preflight(pre, [evidence], "blocked-route.json", status="blocked")
        completed = self.run_command(
            HARNESS,
            "prepare",
            self.root,
            "--action-key",
            "rename_unicode",
            "--recipe-id",
            "jianying.ax-or-clipboard-unicode.v1",
            "--assumption",
            "改名控件可见",
            "--scope",
            "草稿名",
            "--unit-limit-key",
            "live_timeline_mutations_per_batch",
            "--unit-count",
            1,
            "--check-id",
            "harness_live_state_delta",
            "--observation",
            pre,
            "--evidence",
            evidence,
            "--ui-route-preflight",
            preflight,
            "--expect",
            "draft_name=新草稿",
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("forbidden_ui_route_unavailable", completed.stderr)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "blocked")
        self.assertIsNone(state["open_action"])

    def test_prepare_rejects_assistant_as_selected_target(self) -> None:
        pre = self.write_json("assistant-pre.json", observation())
        evidence = self.evidence("assistant-pre.png")
        preflight = self.route_preflight(
            pre,
            [evidence],
            "assistant-route.json",
            target_visible_text="试试剪映助手",
        )
        completed = self.run_command(
            HARNESS,
            "prepare",
            self.root,
            "--action-key",
            "rename_unicode",
            "--recipe-id",
            "jianying.ax-or-clipboard-unicode.v1",
            "--assumption",
            "改名控件可见",
            "--scope",
            "草稿名",
            "--unit-limit-key",
            "live_timeline_mutations_per_batch",
            "--unit-count",
            1,
            "--check-id",
            "harness_live_state_delta",
            "--observation",
            pre,
            "--evidence",
            evidence,
            "--ui-route-preflight",
            preflight,
            "--expect",
            "draft_name=新草稿",
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("forbidden_ui_interaction", completed.stderr)

    def test_prepare_rejects_control_inside_assistant_ancestor(self) -> None:
        pre = self.write_json("assistant-ancestor-pre.json", observation())
        evidence = self.evidence("assistant-ancestor-pre.png")
        target = self.ui_target(
            name="确认改名",
            identifier="rename-confirm",
            visible_text="确定",
        )
        target["ancestor_path"] = [
            {
                "role": "AXGroup",
                "name": "试试剪映助手",
                "identifier": "assistant-panel",
            }
        ]
        preflight = self.route_preflight(
            pre,
            [evidence],
            "assistant-ancestor-route.json",
            steps=[{"sequence": 1, "action": "press", "target": target}],
        )
        completed = self.run_prepare_rename(pre, evidence, preflight)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("selected_route contains Jianying Assistant", completed.stderr)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "blocked")

    def test_normalized_assistant_target_is_blocked_before_click(self) -> None:
        token = self.prepare_rename()
        self.assertEqual(self.run_command(HARNESS, "begin", self.root, "--token", token).returncode, 0)
        authorized = self.authorize_ui_step(
            token,
            "assistant-hit-test.json",
            {
                "sequence": 1,
                "action": "press",
                "target": self.ui_target(
                    name="辅助入口",
                    identifier="assistant-entry",
                    visible_text="【试 试·剪映助手】",
                ),
            },
        )
        self.assertEqual(authorized.returncode, 2)
        self.assertIn("forbidden_ui_interaction", authorized.stderr)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "blocked")
        self.assertEqual(state["blocked"]["reason_code"], "forbidden_ui_interaction")

    def test_incomplete_interaction_trace_blocks_without_retry(self) -> None:
        token = self.prepare_rename()
        self.assertEqual(self.run_command(HARNESS, "begin", self.root, "--token", token).returncode, 0)
        trace = self.interaction_trace(
            token,
            "incomplete-trace.json",
            coverage_complete=False,
        )
        post = self.write_json("incomplete-post.json", observation("新草稿"))
        evidence = self.evidence("incomplete-post.png")
        completed = self.run_command(
            HARNESS,
            "verify",
            self.root,
            "--token",
            token,
            "--observation",
            post,
            "--evidence",
            evidence,
            "--ui-interaction-trace",
            trace,
            "--measured",
            "草稿名已变化",
        )
        self.assertEqual(completed.returncode, 1)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "blocked")
        self.assertEqual(state["blocked"]["reason_code"], "forbidden_ui_interaction")

    def test_route_occlusion_after_begin_blocks_without_retry(self) -> None:
        token = self.prepare_rename()
        self.assertEqual(self.run_command(HARNESS, "begin", self.root, "--token", token).returncode, 0)
        trace = self.interaction_trace(
            token,
            "occluded-route-trace.json",
            events=[],
        )
        restored = self.write_json("occluded-restored.json", observation())
        evidence = self.evidence("occluded-restored.png")
        completed = self.run_command(
            HARNESS,
            "fail",
            self.root,
            "--token",
            token,
            "--reason-code",
            "forbidden_ui_route_unavailable",
            "--detail",
            "剪映助手遮挡必要控件，且没有已验证的非助手路线",
            "--evidence",
            evidence,
            "--observation",
            restored,
            "--rolled-back",
            "--ui-interaction-trace",
            trace,
        )
        self.assertEqual(completed.returncode, 1)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "blocked")
        self.assertEqual(state["blocked"]["reason_code"], "forbidden_ui_route_unavailable")

    def test_unregistered_route_method_and_role_only_target_cannot_mint_token(self) -> None:
        pre = self.write_json("weak-route-pre.json", observation())
        evidence = self.evidence("weak-route-pre.png")
        unregistered = self.route_preflight(
            pre,
            [evidence],
            "unregistered-route.json",
            method="trust-me",
        )
        completed = self.run_prepare_rename(pre, evidence, unregistered)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("method is not registered", completed.stderr)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "blocked")

        unblock = self.run_command(
            HARNESS,
            "unblock",
            self.root,
            "--authorized-by",
            "user",
            "--reason",
            "重新准备严格路线",
        )
        self.assertEqual(unblock.returncode, 0, unblock.stderr)
        role_only = self.route_preflight(
            pre,
            [evidence],
            "role-only-route.json",
            steps=[
                {
                    "sequence": 1,
                    "action": "press",
                    "target": {"role": "AXButton"},
                }
            ],
        )
        completed = self.run_prepare_rename(pre, evidence, role_only)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("role alone is insufficient", completed.stderr)

    def test_route_binding_mismatch_blocks_before_token(self) -> None:
        pre = self.write_json("binding-pre.json", observation())
        evidence = self.evidence("binding-pre.png")
        preflight = self.route_preflight(
            pre,
            [evidence],
            "binding-mismatch-route.json",
            binding_overrides={"recipe_id": "jianying.wrong-recipe.v1"},
        )
        completed = self.run_prepare_rename(pre, evidence, preflight)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("binding mismatch for recipe_id", completed.stderr)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        self.assertIsNone(state["open_action"])
        self.assertEqual(state["lifecycle"], "blocked")

    def test_registered_route_rejects_an_unrelated_help_control(self) -> None:
        pre = self.write_json("unrelated-route-pre.json", observation())
        evidence = self.evidence("unrelated-route-pre.png")
        preflight = self.route_preflight(
            pre,
            [evidence],
            "unrelated-help-route.json",
            steps=[
                {
                    "sequence": 1,
                    "action": "press",
                    "target": self.ui_target(
                        name="帮助",
                        identifier="help-button",
                        visible_text="帮助",
                    ),
                }
            ],
        )
        completed = self.run_prepare_rename(pre, evidence, preflight)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("do not identify the registered action control", completed.stderr)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "blocked")

    def test_trace_must_exactly_match_preapproved_route(self) -> None:
        token = self.prepare_rename()
        self.assertEqual(self.run_command(HARNESS, "begin", self.root, "--token", token).returncode, 0)
        authorized = self.authorize_ui_step(
            token,
            "route-mismatch-hit-test.json",
            {
                "sequence": 1,
                "action": "press",
                "target": self.ui_target(
                    name="取消改名",
                    identifier="rename-cancel",
                    visible_text="取消",
                ),
            },
        )
        self.assertEqual(authorized.returncode, 2)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["blocked"]["reason_code"], "forbidden_ui_interaction")

    def test_live_hit_test_rejects_assistant_overlay_before_click(self) -> None:
        token = self.prepare_rename()
        self.assertEqual(self.run_command(HARNESS, "begin", self.root, "--token", token).returncode, 0)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        planned = state["open_action"]["ui_route_preflight"]["planned_step_inputs"][0]
        authorized = self.authorize_ui_step(
            token,
            "overlay-hit-test.json",
            planned,
            visible_forbidden_regions=[
                {
                    "label": "试试剪映助手",
                    "bounds": {"x": 90, "y": 90, "width": 160, "height": 80},
                }
            ],
        )
        self.assertEqual(authorized.returncode, 2)
        self.assertIn("intersects the Jianying Assistant region", authorized.stderr)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "blocked")

    def test_save_home_reopen_route_allows_registered_per_step_layouts(self) -> None:
        pre = self.write_json("save-reopen-pre.json", observation())
        pre_evidence = self.evidence("save-reopen-pre.png")
        home_target = self.ui_target(
            name="返回首页",
            identifier="return-home",
            visible_text="首页",
        )
        draft_target = self.ui_target(
            name="重新打开测试草稿",
            identifier="draft-card-test",
            visible_text="测试草稿",
        )
        draft_target["ancestor_path"] = [
            {"role": "AXWindow", "name": "剪映首页", "identifier": "jianying-home-window"}
        ]
        steps = [
            {
                "sequence": 1,
                "action": "press",
                "window_signature": "1920x1080-main-v1",
                "target": self.ui_target(name="保存", identifier="save-draft", visible_text="保存"),
            },
            {
                "sequence": 2,
                "action": "press",
                "window_signature": "1920x1080-main-v1",
                "target": home_target,
            },
            {
                "sequence": 3,
                "action": "press",
                "window_signature": "1920x1080-home-v1",
                "target": draft_target,
            },
        ]
        preflight = self.route_preflight(
            pre,
            [pre_evidence],
            "save-reopen-route.json",
            action_key="save_reopen_verify",
            recipe_id="jianying.save-home-reopen-verify.v1",
            steps=steps,
        )
        prepared = self.run_command(
            HARNESS,
            "prepare",
            self.root,
            "--action-key",
            "save_reopen_verify",
            "--recipe-id",
            "jianying.save-home-reopen-verify.v1",
            "--assumption",
            "保存、首页与草稿卡均有语义目标",
            "--scope",
            "保存并重新打开同一草稿",
            "--unit-limit-key",
            "live_timeline_mutations_per_batch",
            "--unit-count",
            1,
            "--check-id",
            "harness_live_state_delta",
            "--observation",
            pre,
            "--evidence",
            pre_evidence,
            "--ui-route-preflight",
            preflight,
        )
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        token = state["open_action"]["token"]
        self.assertEqual(self.run_command(HARNESS, "begin", self.root, "--token", token).returncode, 0)
        trace = self.interaction_trace(token, "save-reopen-trace.json")
        post_value = observation()
        post_value["reopened"] = True
        post = self.write_json("save-reopen-post.json", post_value)
        post_evidence = self.evidence("save-reopen-post.png")
        verified = self.run_command(
            HARNESS,
            "verify",
            self.root,
            "--token",
            token,
            "--observation",
            post,
            "--evidence",
            post_evidence,
            "--ui-interaction-trace",
            trace,
            "--measured",
            "草稿保存并重新打开，保护状态不变",
        )
        self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_self_authored_trace_cannot_replace_controlled_executor_log(self) -> None:
        token = self.prepare_rename()
        self.assertEqual(self.run_command(HARNESS, "begin", self.root, "--token", token).returncode, 0)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        action = state["open_action"]
        trace_path = Path(action["ui_execution"]["trace_path"])
        forged_evidence = self.evidence("forged-step.png")
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        trace["coverage_complete"] = True
        trace["events"] = [
            {
                "sequence": 1,
                "step": action["ui_route_preflight"]["planned_steps"][0],
                "authorization_token": "forged",
                "authorized_at": utc_now(),
                "completed_at": utc_now(),
                "hit_test_fingerprint": fingerprint(forged_evidence),
                "evidence": [fingerprint(forged_evidence)],
            }
        ]
        trace_path.write_text(json.dumps(trace, ensure_ascii=False), encoding="utf-8")
        post = self.write_json("forged-trace-post.json", observation("新草稿"))
        post_evidence = self.evidence("forged-trace-post.png")
        verified = self.run_command(
            HARNESS,
            "verify",
            self.root,
            "--token",
            token,
            "--observation",
            post,
            "--evidence",
            post_evidence,
            "--ui-interaction-trace",
            trace_path,
            "--measured",
            "草稿名已变化",
        )
        self.assertEqual(verified.returncode, 1)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["blocked"]["reason_code"], "forbidden_ui_interaction")

    def test_changed_preflight_persists_block_and_unblock_requires_fresh_route(self) -> None:
        token = self.prepare_rename()
        state_path = self.root / "harness/state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        preflight_path = Path(state["open_action"]["ui_route_preflight"]["fingerprint"]["path"])
        preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
        preflight["tampered_after_prepare"] = True
        preflight_path.write_text(json.dumps(preflight, ensure_ascii=False), encoding="utf-8")

        begun = self.run_command(HARNESS, "begin", self.root, "--token", token)
        self.assertEqual(begun.returncode, 2)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "blocked")
        self.assertEqual(state["blocked"]["reason_code"], "forbidden_ui_route_unavailable")

        restored = self.write_json("begin-block-restored.json", observation())
        evidence = self.evidence("begin-block-restored.png")
        missing_route = self.run_command(
            HARNESS,
            "unblock",
            self.root,
            "--authorized-by",
            "user",
            "--reason",
            "恢复后改走安全路线",
            "--observation",
            restored,
            "--evidence",
            evidence,
        )
        self.assertEqual(missing_route.returncode, 2)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "blocked")

        fresh_route = self.route_preflight(restored, [evidence], "fresh-unblock-route.json")
        unblocked = self.run_command(
            HARNESS,
            "unblock",
            self.root,
            "--authorized-by",
            "user",
            "--reason",
            "恢复后改走安全路线",
            "--observation",
            restored,
            "--evidence",
            evidence,
            "--ui-route-preflight",
            fresh_route,
        )
        self.assertEqual(unblocked.returncode, 0, unblocked.stderr)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "repair_required")
        self.assertEqual(
            state["open_action"]["ui_route_preflight"]["fingerprint"]["path"],
            str(fresh_route.resolve()),
        )

    def test_schema_v1_open_live_action_migrates_to_persistent_block(self) -> None:
        self.prepare_rename()
        state_path = self.root / "harness/state.json"
        pending_path = self.root / "harness/pending_action.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["schema_version"] = 1
        state["open_action"].pop("ui_route_preflight", None)
        pending = dict(state["open_action"])
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        pending_path.write_text(json.dumps(pending, ensure_ascii=False), encoding="utf-8")

        resumed = self.run_command(HARNESS, "resume", self.root)
        self.assertEqual(resumed.returncode, 1, resumed.stderr)
        migrated = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(migrated["schema_version"], SCHEMA_VERSION)
        self.assertEqual(migrated["lifecycle"], "blocked")
        self.assertEqual(migrated["blocked"]["reason_code"], "forbidden_ui_route_unavailable")

    def test_fail_without_trace_is_a_fatal_forbidden_interaction(self) -> None:
        token = self.prepare_rename()
        self.assertEqual(self.run_command(HARNESS, "begin", self.root, "--token", token).returncode, 0)
        restored = self.write_json("missing-trace-restored.json", observation())
        evidence = self.evidence("missing-trace-restored.png")
        failed = self.run_command(
            HARNESS,
            "fail",
            self.root,
            "--token",
            token,
            "--reason-code",
            "no_change",
            "--detail",
            "没有变化",
            "--evidence",
            evidence,
            "--observation",
            restored,
            "--rolled-back",
        )
        self.assertEqual(failed.returncode, 1)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["lifecycle"], "blocked")
        self.assertEqual(state["blocked"]["reason_code"], "forbidden_ui_interaction")

    def test_every_live_registry_action_declares_required_control(self) -> None:
        for action_key, spec in ACTION_REGISTRY.items():
            if spec["live"]:
                self.assertTrue(spec.get("ui_required_control"), action_key)
                self.assertTrue(spec.get("ui_route_id"), action_key)
                self.assertTrue(spec.get("ui_anchor_terms"), action_key)

    def test_visual_index_integrity_recomputes_sources_rows_and_evidence(self) -> None:
        source = self.evidence("visual_sources/index_source.mp4")
        frame = self.evidence("visuals/index_frames/frame_001.jpg")
        shot_index = self.write_tsv(
            "visuals/shot_index.tsv",
            ["shot_id", "source_id", "source_file", "frame_path"],
            [
                {
                    "shot_id": "S0001",
                    "source_id": "SRC1",
                    "source_file": str(source),
                    "frame_path": str(frame),
                }
            ],
        )
        ocr_index = self.write_tsv(
            "visuals/shot_ocr_index.tsv",
            ["source_id", "source_file", "evidence_frame", "text"],
            [
                {
                    "source_id": "SRC1",
                    "source_file": str(source),
                    "evidence_frame": str(frame),
                    "text": "角色甲",
                }
            ],
        )
        source_manifest = self.write_json(
            "visuals/source_identity_manifest.json",
            {
                "primary_sources": [
                    {
                        "source_id": "SRC1",
                        "path": str(source),
                        "sha256": file_sha256(source),
                        "probe": {"ok": True, "duration_s": 10.0},
                    }
                ]
            },
        )
        contact = self.evidence("visuals/contact_sheets/index_01.jpg")
        contacts = self.write_json(
            "visuals/contact_sheet_manifest.json",
            {"contact_sheets": [str(contact)]},
        )
        check = {
            "type": "visual_index_integrity",
            "path": str(shot_index),
            "ocr_index_path": str(ocr_index),
            "source_manifest_path": str(source_manifest),
            "contact_sheet_manifest_path": str(contacts),
            "min_shot_rows": 1,
            "min_ocr_rows": 1,
        }
        passed, _, metrics = run_check(self.root, check)
        self.assertTrue(passed, metrics)
        frame.unlink()
        passed, _, metrics = run_check(self.root, check)
        self.assertFalse(passed)
        self.assertTrue(
            any("missing indexed evidence" in item for item in metrics["failures"])
        )

    def test_visual_match_plan_integrity_catches_srt_drift_and_duplicate_candidates(
        self,
    ) -> None:
        fixture = self.visual_fixture()
        check = {
            "type": "visual_match_plan_integrity",
            "path": str(fixture["match_sheet"]),
            "canonical_srt_path": str(fixture["canonical"]),
            "manifest_path": str(fixture["match_manifest"]),
            "min_candidates": 3,
            "max_reuse": 2,
        }
        passed, _, metrics = run_check(self.root, check)
        self.assertTrue(passed, metrics)

        Path(fixture["canonical"]).write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n角色乙作出回答\n\n"
            "2\n00:00:01,000 --> 00:00:02,000\n故事走向尾声\n",
            encoding="utf-8",
        )
        passed, _, metrics = run_check(self.root, check)
        self.assertFalse(passed)
        self.assertTrue(
            any("canonical SRT" in item for item in metrics["failures"])
        )

        fixture = self.visual_fixture()
        rows = json.loads(json.dumps(fixture["rows"], ensure_ascii=False))
        rows[0]["candidate_b"] = rows[0]["candidate_a"]
        match_sheet = self.write_tsv(
            "visuals/match_sheet.tsv", fixture["fields"], rows
        )
        manifest = json.loads(
            Path(fixture["match_manifest"]).read_text(encoding="utf-8")
        )
        manifest["match_sheet_sha256"] = file_sha256(match_sheet)
        Path(fixture["match_manifest"]).write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        passed, _, metrics = run_check(self.root, check)
        self.assertFalse(passed)
        self.assertTrue(
            any("distinct candidates" in item for item in metrics["failures"])
        )

    def test_visual_selection_review_rejects_missing_cue_identity_and_stale_hash(
        self,
    ) -> None:
        fixture = self.visual_fixture()
        check = {
            "type": "visual_selection_review_integrity",
            "path": str(fixture["review_manifest"]),
            "match_sheet_path": str(fixture["match_sheet"]),
            "evidence_manifest_path": str(fixture["evidence_manifest"]),
            "require_named_identity": True,
        }
        passed, _, metrics = run_check(self.root, check)
        self.assertTrue(passed, metrics)

        fields, rows = read_tsv(Path(fixture["evidence_manifest"]))
        self.write_tsv(
            "visuals/selected_evidence_manifest.tsv", fields, rows[:1]
        )
        review = json.loads(
            Path(fixture["review_manifest"]).read_text(encoding="utf-8")
        )
        review["evidence_manifest_sha256"] = file_sha256(
            Path(fixture["evidence_manifest"])
        )
        Path(fixture["review_manifest"]).write_text(
            json.dumps(review, ensure_ascii=False), encoding="utf-8"
        )
        passed, _, metrics = run_check(self.root, check)
        self.assertFalse(passed)
        self.assertTrue(
            any("evidence coverage" in item for item in metrics["failures"])
        )

        fixture = self.visual_fixture()
        review = json.loads(
            Path(fixture["review_manifest"]).read_text(encoding="utf-8")
        )
        review["identity_checks"] = []
        Path(fixture["review_manifest"]).write_text(
            json.dumps(review, ensure_ascii=False), encoding="utf-8"
        )
        passed, _, metrics = run_check(self.root, check)
        self.assertFalse(passed)
        self.assertTrue(
            any("identity check missing" in item for item in metrics["failures"])
        )

        fixture = self.visual_fixture()
        review = json.loads(
            Path(fixture["review_manifest"]).read_text(encoding="utf-8")
        )
        review["match_sheet_sha256"] = "0" * 64
        Path(fixture["review_manifest"]).write_text(
            json.dumps(review, ensure_ascii=False), encoding="utf-8"
        )
        passed, _, metrics = run_check(self.root, check)
        self.assertFalse(passed)
        self.assertTrue(
            any("stale match_sheet" in item for item in metrics["failures"])
        )

    def test_visual_selection_review_can_record_complete_needs_repair_pass(
        self,
    ) -> None:
        fixture = self.visual_fixture()
        review = json.loads(
            Path(fixture["review_manifest"]).read_text(encoding="utf-8")
        )
        review["status"] = "NEEDS_REPAIR"
        review["unresolved_cue_ids"] = [2]
        Path(fixture["review_manifest"]).write_text(
            json.dumps(review, ensure_ascii=False), encoding="utf-8"
        )
        check = {
            "type": "visual_selection_review_integrity",
            "path": str(fixture["review_manifest"]),
            "match_sheet_path": str(fixture["match_sheet"]),
            "evidence_manifest_path": str(fixture["evidence_manifest"]),
            "allow_unresolved": True,
        }
        passed, _, metrics = run_check(self.root, check)
        self.assertTrue(passed, metrics)
        self.assertFalse(metrics["workflow_ready"])
        self.assertEqual(metrics["unresolved_cue_ids"], [2])

    def test_visual_match_repair_recomputes_hash_chain_and_exact_diff(self) -> None:
        fixture = self.visual_fixture()
        before_rows = json.loads(json.dumps(fixture["rows"], ensure_ascii=False))
        after_rows = json.loads(json.dumps(fixture["rows"], ensure_ascii=False))
        after_rows[0]["selected_candidate"] = "B"
        after_rows[0]["source_id"] = "SRC_B"
        after_rows[0]["source_file"] = str(fixture["sources"][1])
        after_rows[0]["match_reason"] = "复核后改用正确的角色甲反应镜头"
        before = self.write_tsv(
            "visuals/snapshots/match_sheet.before.tsv",
            fixture["fields"],
            before_rows,
        )
        after = self.write_tsv(
            "visuals/match_sheet.repaired.tsv",
            fixture["fields"],
            after_rows,
        )
        evidence = self.evidence("visuals/repairs/cue_001.jpg")
        repair_manifest = self.write_json(
            "visuals/repair_manifest.json",
            {
                "schema_version": 1,
                "status": "PASS",
                "before_match_sheet_sha256": file_sha256(before),
                "after_match_sheet_sha256": file_sha256(after),
                "changed_cue_ids": [1],
                "repairs": [
                    {
                        "cue_id": 1,
                        "reason": "人物身份复核纠正",
                        "evidence": str(evidence),
                        "identity_check": {
                            "visible": ["角色甲"],
                            "status": "PASS",
                        },
                    }
                ],
                "unresolved_after": [],
            },
        )
        check = {
            "type": "visual_match_repair_integrity",
            "path": str(repair_manifest),
            "before_match_sheet_path": str(before),
            "after_match_sheet_path": str(after),
            "canonical_srt_path": str(fixture["canonical"]),
        }
        passed, _, metrics = run_check(self.root, check)
        self.assertTrue(passed, metrics)

        hidden_rows = json.loads(json.dumps(after_rows, ensure_ascii=False))
        hidden_rows[1]["match_reason"] = "未申报的隐藏改动"
        self.write_tsv(
            "visuals/match_sheet.repaired.tsv",
            fixture["fields"],
            hidden_rows,
        )
        manifest = json.loads(repair_manifest.read_text(encoding="utf-8"))
        manifest["after_match_sheet_sha256"] = file_sha256(after)
        repair_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        passed, _, metrics = run_check(self.root, check)
        self.assertFalse(passed)
        self.assertTrue(
            any("hidden or missing repair" in item for item in metrics["failures"])
        )

        self.write_tsv(
            "visuals/match_sheet.repaired.tsv",
            fixture["fields"],
            after_rows,
        )
        manifest["after_match_sheet_sha256"] = file_sha256(after)
        manifest["before_match_sheet_sha256"] = "0" * 64
        repair_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        passed, _, metrics = run_check(self.root, check)
        self.assertFalse(passed)
        self.assertTrue(
            any("stale before_match_sheet" in item for item in metrics["failures"])
        )

    def test_visual_match_repair_rebinds_selection_to_after_candidate_pool(
        self,
    ) -> None:
        fixture = self.visual_fixture()
        fields = list(fixture["fields"]) + [
            "selected_candidate_id",
            "selected_source_id",
        ]
        before_rows = json.loads(json.dumps(fixture["rows"], ensure_ascii=False))
        after_rows = json.loads(json.dumps(fixture["rows"], ensure_ascii=False))
        pool_rows = []
        for row in before_rows:
            identity = int(row["line_id"])
            candidates = []
            for index, source in enumerate(fixture["sources"], start=1):
                candidate_evidence = {
                    sample: str(
                        self.evidence(
                            "visuals/pool_repair/"
                            f"cue_{identity}_{index}_{sample}.jpg"
                        )
                    )
                    for sample in ("head", "mid", "tail")
                }
                candidates.append(
                    {
                        "candidate_id": f"cue-{identity}-candidate-{index}",
                        "source_id": f"SRC_{chr(64 + index)}",
                        "source_file": str(source),
                        "source_in": float(row["source_in"]),
                        "source_out": float(row["source_out"]),
                        "evidence": candidate_evidence,
                    }
                )
            selected_index = ord(row["source_id"][-1]) - ord("A")
            row["selected_candidate_id"] = candidates[selected_index][
                "candidate_id"
            ]
            row["selected_source_id"] = row["source_id"]
            pool_rows.append(
                {
                    "cue_id": identity,
                    "candidates": candidates,
                    "candidate_shortfall_reason": "fixture has three sources",
                    "candidate_expansion_attempts": [
                        {"source_scope": "fixture", "result": "exhausted"}
                    ],
                }
            )
        after_rows = json.loads(json.dumps(before_rows, ensure_ascii=False))
        after_rows[0]["selected_candidate"] = "B"
        after_rows[0]["source_id"] = "SRC_B"
        after_rows[0]["selected_source_id"] = "SRC_B"
        after_rows[0]["source_file"] = str(fixture["sources"][1])
        after_rows[0]["match_reason"] = "修复后选中 B，但故意保留 A 的 candidate_id"

        before = self.write_tsv(
            "visuals/snapshots/pool_binding.before.tsv", fields, before_rows
        )
        after = self.write_tsv(
            "visuals/pool_binding.after.tsv", fields, after_rows
        )
        before_pool = self.root / "visuals/snapshots/candidate_pool.before.jsonl"
        after_pool = self.root / "visuals/candidate_pool.after.jsonl"
        pool_text = "".join(
            json.dumps(item, ensure_ascii=False) + "\n" for item in pool_rows
        )
        before_pool.parent.mkdir(parents=True, exist_ok=True)
        after_pool.parent.mkdir(parents=True, exist_ok=True)
        before_pool.write_text(pool_text, encoding="utf-8")
        after_pool.write_text(pool_text, encoding="utf-8")
        bound_review = self.write_json(
            "visuals/review_for_pool_repair.json",
            {
                "schema_version": 2,
                "status": "NEEDS_REPAIR",
                "match_sheet_sha256": file_sha256(before),
                "candidate_pool_sha256": file_sha256(before_pool),
                "unresolved_cue_ids": [1],
            },
        )
        evidence = self.evidence("visuals/repairs/cue_001_pool_binding.jpg")
        repair_manifest = self.write_json(
            "visuals/repair_pool_binding_manifest.json",
            {
                "schema_version": 1,
                "status": "PASS",
                "before_match_sheet_sha256": file_sha256(before),
                "after_match_sheet_sha256": file_sha256(after),
                "before_candidate_pool_sha256": file_sha256(before_pool),
                "after_candidate_pool_sha256": file_sha256(after_pool),
                "review_manifest_sha256": file_sha256(bound_review),
                "changed_cue_ids": [1],
                "added_candidate_ids": [],
                "repairs": [
                    {
                        "cue_id": 1,
                        "reason": "验证修复后的候选池绑定",
                        "evidence": str(evidence),
                        "identity_check": {
                            "visible": ["角色甲"],
                            "status": "PASS",
                        },
                    }
                ],
                "unresolved_after": [],
            },
        )
        check = {
            "type": "visual_match_repair_integrity",
            "path": str(repair_manifest),
            "before_match_sheet_path": str(before),
            "after_match_sheet_path": str(after),
            "before_candidate_pool_path": str(before_pool),
            "after_candidate_pool_path": str(after_pool),
            "review_manifest_path": str(bound_review),
            "canonical_srt_path": str(fixture["canonical"]),
            "require_candidate_pool_evidence": True,
            "min_pool_candidates": 3,
            "preferred_pool_candidates": 32,
            "require_candidate_shortfall_evidence": True,
        }
        passed, _, metrics = run_check(self.root, check)
        self.assertFalse(passed)
        self.assertTrue(
            any(
                "selected pool source_id differs" in item
                for item in metrics["failures"]
            )
        )

        after_rows[0]["selected_candidate_id"] = "cue-1-candidate-2"
        after = self.write_tsv(
            "visuals/pool_binding.after.tsv", fields, after_rows
        )
        manifest = json.loads(repair_manifest.read_text(encoding="utf-8"))
        manifest["after_match_sheet_sha256"] = file_sha256(after)
        repair_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        passed, _, metrics = run_check(self.root, check)
        self.assertTrue(passed, metrics)

        review_data = json.loads(bound_review.read_text(encoding="utf-8"))
        review_data["unresolved_cue_ids"] = [2]
        bound_review.write_text(
            json.dumps(review_data, ensure_ascii=False), encoding="utf-8"
        )
        manifest["review_manifest_sha256"] = file_sha256(bound_review)
        repair_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        passed, _, metrics = run_check(self.root, check)
        self.assertFalse(passed)
        self.assertTrue(
            any(
                "did not cover input-review unresolved cues" in item
                for item in metrics["failures"]
            )
        )
        review_data["unresolved_cue_ids"] = [1]
        bound_review.write_text(
            json.dumps(review_data, ensure_ascii=False), encoding="utf-8"
        )
        manifest["review_manifest_sha256"] = file_sha256(bound_review)

        degraded_pool_rows = json.loads(
            json.dumps(pool_rows, ensure_ascii=False)
        )
        degraded_pool_rows[0]["candidates"] = [
            degraded_pool_rows[0]["candidates"][1]
        ]
        after_pool.write_text(
            "".join(
                json.dumps(item, ensure_ascii=False) + "\n"
                for item in degraded_pool_rows
            ),
            encoding="utf-8",
        )
        manifest["after_candidate_pool_sha256"] = file_sha256(after_pool)
        repair_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        passed, _, metrics = run_check(self.root, check)
        self.assertFalse(passed)
        self.assertTrue(
            any(
                "candidate pool has 1, expected>=3" in item
                for item in metrics["failures"]
            )
        )

    def test_visual_match_plan_binds_selected_range_to_full_candidate_pool(self) -> None:
        fixture = self.visual_fixture()
        fields = list(fixture["fields"])
        fields.extend(
            [
                "candidate_a_id",
                "candidate_b_id",
                "candidate_c_id",
                "selected_candidate_id",
            ]
        )
        rows = json.loads(json.dumps(fixture["rows"], ensure_ascii=False))
        pool_rows = []
        for row in rows:
            row["qa_status"] = "machine_proposed"
            line_id = int(row["line_id"])
            candidates = []
            for index, source in enumerate(fixture["sources"], start=1):
                candidate_id = f"cue-{line_id}-candidate-{index}"
                evidence = {
                    sample: str(
                        self.evidence(
                            f"visuals/pool/cue_{line_id}_{index}_{sample}.jpg"
                        )
                    )
                    for sample in ("head", "mid", "tail")
                }
                candidates.append(
                    {
                        "candidate_id": candidate_id,
                        "source_id": f"SRC_{chr(64 + index)}",
                        "source_file": str(source),
                        "source_in": float(row["source_in"]),
                        "source_out": float(row["source_out"]),
                        "evidence": evidence,
                    }
                )
            for letter in "abc":
                descriptor_source_id = row[f"candidate_{letter}"].split(
                    "|", 1
                )[0]
                row[f"candidate_{letter}_id"] = next(
                    candidate["candidate_id"]
                    for candidate in candidates
                    if candidate["source_id"] == descriptor_source_id
                )
            selected_index = ord(row["source_id"][-1]) - ord("A")
            row["selected_candidate_id"] = candidates[selected_index][
                "candidate_id"
            ]
            pool_rows.append({"cue_id": line_id, "candidates": candidates})
        match_sheet = self.write_tsv("visuals/match_sheet.tsv", fields, rows)
        pool_path = self.root / "visuals/candidate_pool.jsonl"
        pool_path.write_text(
            "".join(
                json.dumps(item, ensure_ascii=False) + "\n"
                for item in pool_rows
            ),
            encoding="utf-8",
        )
        manifest = json.loads(
            Path(fixture["match_manifest"]).read_text(encoding="utf-8")
        )
        manifest["match_sheet_sha256"] = file_sha256(match_sheet)
        manifest["candidate_pool_sha256"] = file_sha256(pool_path)
        shot_index = self.evidence("visuals/shot_index_for_plan.tsv")
        ocr_index = self.evidence("visuals/shot_ocr_for_plan.tsv")
        source_manifest = self.write_json(
            "visuals/source_manifest_for_plan.json",
            {
                "primary_sources": [
                    {
                        "source_id": f"SRC_{chr(64 + index)}",
                        "path": str(source),
                    }
                    for index, source in enumerate(
                        fixture["sources"], start=1
                    )
                ]
            },
        )
        manifest["shot_index_sha256"] = file_sha256(shot_index)
        manifest["ocr_index_sha256"] = file_sha256(ocr_index)
        manifest["source_manifest_sha256"] = file_sha256(source_manifest)
        Path(fixture["match_manifest"]).write_text(
            json.dumps(manifest, ensure_ascii=False),
            encoding="utf-8",
        )
        check = {
            "type": "visual_match_plan_integrity",
            "path": str(match_sheet),
            "canonical_srt_path": str(fixture["canonical"]),
            "manifest_path": str(fixture["match_manifest"]),
            "candidate_pool_path": str(pool_path),
            "require_manifest": True,
            "require_candidate_pool": True,
            "require_candidate_pool_evidence": True,
            "required_qa_status": "machine_proposed",
            "shot_index_path": str(shot_index),
            "ocr_index_path": str(ocr_index),
            "source_manifest_path": str(source_manifest),
            "require_index_binding": True,
            "require_source_manifest_binding": True,
            "require_candidate_ids": True,
        }
        passed, _, metrics = run_check(self.root, check)
        self.assertTrue(passed, metrics)

        shot_index_original = shot_index.read_bytes()
        shot_index.write_bytes(b"stale replacement")
        passed, _, metrics = run_check(self.root, check)
        self.assertFalse(passed)
        self.assertTrue(
            any(
                "stale shot_index_path SHA" in item
                for item in metrics["failures"]
            )
        )
        shot_index.write_bytes(shot_index_original)
        self.assertEqual(file_sha256(shot_index), manifest["shot_index_sha256"])

        pool_rows[0]["candidates"][1]["source_id"] = "UNKNOWN_SOURCE"
        pool_path.write_text(
            "".join(
                json.dumps(item, ensure_ascii=False) + "\n"
                for item in pool_rows
            ),
            encoding="utf-8",
        )
        manifest["candidate_pool_sha256"] = file_sha256(pool_path)
        Path(fixture["match_manifest"]).write_text(
            json.dumps(manifest, ensure_ascii=False),
            encoding="utf-8",
        )
        passed, _, metrics = run_check(self.root, check)
        self.assertFalse(passed)
        self.assertTrue(
            any(
                "unknown_source_id" in item
                for item in metrics["failures"]
            )
        )
        pool_rows[0]["candidates"][1]["source_id"] = "SRC_B"
        pool_path.write_text(
            "".join(
                json.dumps(item, ensure_ascii=False) + "\n"
                for item in pool_rows
            ),
            encoding="utf-8",
        )
        manifest["candidate_pool_sha256"] = file_sha256(pool_path)
        Path(fixture["match_manifest"]).write_text(
            json.dumps(manifest, ensure_ascii=False),
            encoding="utf-8",
        )

        original_candidate_b_id = rows[1]["candidate_b_id"]
        rows[1]["candidate_b_id"] = "not-in-current-pool"
        match_sheet = self.write_tsv("visuals/match_sheet.tsv", fields, rows)
        manifest["match_sheet_sha256"] = file_sha256(match_sheet)
        Path(fixture["match_manifest"]).write_text(
            json.dumps(manifest, ensure_ascii=False),
            encoding="utf-8",
        )
        passed, _, metrics = run_check(self.root, check)
        self.assertFalse(passed)
        self.assertTrue(
            any(
                "candidate_b_id is not in candidate pool" in item
                for item in metrics["failures"]
            )
        )
        rows[1]["candidate_b_id"] = original_candidate_b_id
        match_sheet = self.write_tsv("visuals/match_sheet.tsv", fields, rows)
        manifest["match_sheet_sha256"] = file_sha256(match_sheet)
        Path(fixture["match_manifest"]).write_text(
            json.dumps(manifest, ensure_ascii=False),
            encoding="utf-8",
        )

        check["preferred_pool_candidates"] = 32
        check["require_candidate_shortfall_evidence"] = True
        passed, _, metrics = run_check(self.root, check)
        self.assertFalse(passed)
        self.assertTrue(
            any(
                "without candidate_shortfall_reason" in item
                for item in metrics["failures"]
            )
        )
        for entry in pool_rows:
            entry["candidate_shortfall_reason"] = "fixture has only three sources"
            entry["candidate_expansion_attempts"] = [
                {"source_scope": "fixture", "result": "exhausted"}
            ]
        pool_path.write_text(
            "".join(
                json.dumps(item, ensure_ascii=False) + "\n"
                for item in pool_rows
            ),
            encoding="utf-8",
        )
        manifest["candidate_pool_sha256"] = file_sha256(pool_path)
        Path(fixture["match_manifest"]).write_text(
            json.dumps(manifest, ensure_ascii=False),
            encoding="utf-8",
        )
        passed, _, metrics = run_check(self.root, check)
        self.assertTrue(passed, metrics)

        rows[0]["selected_candidate_id"] = pool_rows[0]["candidates"][1][
            "candidate_id"
        ]
        match_sheet = self.write_tsv("visuals/match_sheet.tsv", fields, rows)
        manifest["match_sheet_sha256"] = file_sha256(match_sheet)
        Path(fixture["match_manifest"]).write_text(
            json.dumps(manifest, ensure_ascii=False),
            encoding="utf-8",
        )
        passed, _, metrics = run_check(self.root, check)
        self.assertFalse(passed)
        self.assertTrue(
            any("selected pool source" in item for item in metrics["failures"])
        )

    def test_layered_review_requires_risk_candidate_and_trusted_file_coverage(
        self,
    ) -> None:
        fixture = self.visual_fixture()
        risk_sheet = self.evidence("visuals/candidate_review/risk_0001.jpg")
        selected_sheet = self.root / "visuals/contact_sheets_final/selected_01.jpg"
        _, evidence_rows = read_tsv(Path(fixture["evidence_manifest"]))
        trusted_files = [
            {
                "kind": "selected_sheet",
                "path": str(selected_sheet),
                "sha256": file_sha256(selected_sheet),
                "cue_ids": [1, 2],
            },
            {
                "kind": "risk_abc_sheet",
                "path": str(risk_sheet),
                "sha256": file_sha256(risk_sheet),
                "cue_ids": [1, 2],
            },
        ]
        for row in evidence_rows:
            evidence_path = Path(row["evidence_image"])
            trusted_files.append(
                {
                    "kind": "evidence_frame",
                    "path": str(evidence_path),
                    "sha256": file_sha256(evidence_path),
                    "cue_ids": [int(row["line_id"])],
                }
            )
        review_path = Path(fixture["review_manifest"])
        review = json.loads(review_path.read_text(encoding="utf-8"))
        review.update(
            {
                "selected_reviewed_ids": [1, 2],
                "risk_row_ids": [1, 2],
                "candidate_reviewed_ids": [1, 2],
                "identity_required_ids": [1],
                "identity_verified": {"1": "角色甲"},
                "opening_review": {"status": "PASS"},
                "ending_review": {"status": "PASS"},
                "files": trusted_files,
                "unresolved_ids": [],
            }
        )
        review_path.write_text(
            json.dumps(review, ensure_ascii=False),
            encoding="utf-8",
        )
        check = {
            "type": "visual_selection_review_integrity",
            "path": str(review_path),
            "match_sheet_path": str(fixture["match_sheet"]),
            "evidence_manifest_path": str(fixture["evidence_manifest"]),
            "require_named_identity": True,
            "require_contact_sheets": True,
            "require_range_reviews": True,
            "require_opening_review": True,
            "require_ending_review": True,
            "require_layered_review": True,
        }
        passed, _, metrics = run_check(self.root, check)
        self.assertTrue(passed, metrics)

        review["candidate_reviewed_ids"] = [1]
        review_path.write_text(
            json.dumps(review, ensure_ascii=False),
            encoding="utf-8",
        )
        passed, _, metrics = run_check(self.root, check)
        self.assertFalse(passed)
        self.assertTrue(
            any(
                "candidate review coverage" in item
                for item in metrics["failures"]
            )
        )

    def test_layered_review_binds_every_risk_abc_head_mid_tail_frame(
        self,
    ) -> None:
        fixture = self.visual_fixture()
        fields = list(fixture["fields"]) + [
            "candidate_a_id",
            "candidate_b_id",
            "candidate_c_id",
            "selected_candidate_id",
        ]
        rows = json.loads(json.dumps(fixture["rows"], ensure_ascii=False))
        pool_rows = []
        risk_frame_records = []
        for row in rows:
            identity = int(row["line_id"])
            pool_candidates = []
            for index, (letter, source) in enumerate(
                zip("abc", fixture["sources"]), start=1
            ):
                candidate_id = f"cue-{identity}-{letter}"
                row[f"candidate_{letter}_id"] = candidate_id
                pool_candidates.append(
                    {
                        "candidate_id": candidate_id,
                        "source_id": f"SRC_{chr(64 + index)}",
                        "source_file": str(source),
                        "source_in": float(row["source_in"]),
                        "source_out": float(row["source_out"]),
                    }
                )
                for sample_index, sample in enumerate(
                    ("head", "mid", "tail"), start=1
                ):
                    frame = self.evidence(
                        "visuals/candidate_review/frames/"
                        f"cue_{identity}_{letter}_{sample}.jpg"
                    )
                    risk_frame_records.append(
                        {
                            "kind": "evidence_frame",
                            "path": str(frame),
                            "sha256": file_sha256(frame),
                            "cue_ids": [identity],
                            "view": letter.upper(),
                            "sample": sample,
                            "candidate_id": candidate_id,
                            "source_id": f"SRC_{chr(64 + index)}",
                            "source_file": str(source),
                            "source_in": float(row["source_in"]),
                            "source_out": float(row["source_out"]),
                            "timestamp": (
                                float(row["source_in"])
                                + (float(row["source_out"]) - float(row["source_in"]))
                                * sample_index
                                / 4
                            ),
                        }
                    )
            row["selected_candidate_id"] = row["candidate_a_id"]
            pool_rows.append(
                {"cue_id": identity, "candidates": pool_candidates}
            )
        match_sheet = self.write_tsv(
            "visuals/risk_matrix_match.tsv", fields, rows
        )
        candidate_pool = self.root / "visuals/risk_matrix_pool.jsonl"
        candidate_pool.write_text(
            "".join(
                json.dumps(item, ensure_ascii=False) + "\n"
                for item in pool_rows
            ),
            encoding="utf-8",
        )
        selected_sheet = self.evidence(
            "visuals/contact_sheets_final/risk_matrix_selected.jpg"
        )
        risk_sheet = self.evidence(
            "visuals/candidate_review/risk_matrix_abc.jpg"
        )
        _, selected_evidence_rows = read_tsv(
            Path(fixture["evidence_manifest"])
        )
        files = [
            {
                "kind": "selected_sheet",
                "path": str(selected_sheet),
                "sha256": file_sha256(selected_sheet),
                "cue_ids": [1, 2],
            },
            {
                "kind": "risk_abc_sheet",
                "path": str(risk_sheet),
                "sha256": file_sha256(risk_sheet),
                "cue_ids": [1, 2],
            },
            *risk_frame_records,
        ]
        for evidence_row in selected_evidence_rows:
            evidence_path = Path(evidence_row["evidence_image"])
            files.append(
                {
                    "kind": "selected_frame",
                    "path": str(evidence_path),
                    "sha256": file_sha256(evidence_path),
                    "cue_ids": [int(evidence_row["line_id"])],
                }
            )
        review = {
            "schema_version": 2,
            "status": "PASS",
            "match_sheet_sha256": file_sha256(match_sheet),
            "evidence_manifest_sha256": file_sha256(
                Path(fixture["evidence_manifest"])
            ),
            "candidate_pool_sha256": file_sha256(candidate_pool),
            "row_count": 2,
            "selected_reviewed_ids": [1, 2],
            "risk_row_ids": [1, 2],
            "candidate_reviewed_ids": [1, 2],
            "identity_required_ids": [1],
            "identity_verified": {"1": "角色甲"},
            "opening_review": {"status": "PASS"},
            "ending_review": {"status": "PASS"},
            "unresolved_ids": [],
            "range_reviews": [{"range": "1-2", "status": "PASS"}],
            "files": files,
        }
        review_path = self.write_json(
            "visuals/risk_matrix_review.json", review
        )
        check = {
            "type": "visual_selection_review_integrity",
            "path": str(review_path),
            "match_sheet_path": str(match_sheet),
            "evidence_manifest_path": str(fixture["evidence_manifest"]),
            "candidate_pool_path": str(candidate_pool),
            "require_named_identity": True,
            "require_contact_sheets": True,
            "require_range_reviews": True,
            "require_opening_review": True,
            "require_ending_review": True,
            "require_layered_review": True,
            "require_risk_frame_matrix": True,
            "require_candidate_pool_binding": True,
        }
        passed, _, metrics = run_check(self.root, check)
        self.assertTrue(passed, metrics)

        original_pool_text = candidate_pool.read_text(encoding="utf-8")
        mutated_pool_rows = json.loads(
            json.dumps(pool_rows, ensure_ascii=False)
        )
        mutated_pool_rows[0]["generation_note"] = "stale review probe"
        candidate_pool.write_text(
            "".join(
                json.dumps(item, ensure_ascii=False) + "\n"
                for item in mutated_pool_rows
            ),
            encoding="utf-8",
        )
        passed, _, metrics = run_check(self.root, check)
        self.assertFalse(passed)
        self.assertTrue(
            any(
                "stale candidate_pool_sha256" in item
                for item in metrics["failures"]
            )
        )
        candidate_pool.write_text(original_pool_text, encoding="utf-8")

        review["files"] = [
            record
            for record in files
            if not (
                record.get("kind") == "evidence_frame"
                and record.get("cue_ids") == [1]
                and record.get("view") == "B"
                and record.get("sample") == "mid"
            )
        ]
        review_path.write_text(
            json.dumps(review, ensure_ascii=False), encoding="utf-8"
        )
        passed, _, metrics = run_check(self.root, check)
        self.assertFalse(passed)
        self.assertTrue(
            any(
                "missing risk evidence frame=(1, 'B', 'mid')" in item
                for item in metrics["failures"]
            )
        )

    def test_picture_master_and_patch_integrity_bind_media_and_unchanged_segments(
        self,
    ) -> None:
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        if not ffmpeg or not ffprobe:
            self.skipTest("ffmpeg and ffprobe are required")
        fixture = self.visual_fixture()
        timing = self.write_json(
            "timing_contract.json",
            {
                "fps": 10,
                "target_frame_count": 10,
                "target_seconds": 1.0,
                "target_timecode": "00:00:01:00",
            },
        )

        def render_halves(name: str, first_color: str, second_color: str) -> Path:
            output = self.root / name
            output.parent.mkdir(parents=True, exist_ok=True)
            completed = subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c={first_color}:s=64x64:r=10:d=0.5",
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c={second_color}:s=64x64:r=10:d=0.5",
                    "-filter_complex",
                    "[0:v][1:v]concat=n=2:v=1:a=0,format=yuv420p[v]",
                    "-map",
                    "[v]",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-y",
                    str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            return output

        base_picture = render_halves("visuals/picture_base.mp4", "red", "green")
        approval = Path(fixture["review_manifest"])
        approval_data = json.loads(approval.read_text(encoding="utf-8"))
        approval_data["opening_review"] = {"status": "PASS"}
        approval_data["ending_review"] = {"status": "PASS"}
        approval.write_text(
            json.dumps(approval_data, ensure_ascii=False), encoding="utf-8"
        )
        render_manifest = self.write_json(
            "visuals/render_manifest.json",
            {
                "schema_version": 1,
                "status": "PASS",
                "picture_master_sha256": file_sha256(base_picture),
                "match_sheet_sha256": file_sha256(Path(fixture["match_sheet"])),
                "approval_sha256": file_sha256(approval),
                "timing_contract_sha256": file_sha256(timing),
                "cue_count": 2,
                "all_match_rows_rendered": True,
            },
        )
        master_check = {
            "type": "picture_master_integrity",
            "path": str(base_picture),
            "manifest_path": str(render_manifest),
            "match_sheet_path": str(fixture["match_sheet"]),
            "approval_path": str(approval),
            "timing_contract_path": str(timing),
            "require_approval_match_binding": True,
            "require_approval_sequence_gates": True,
        }
        passed, _, metrics = run_check(self.root, master_check)
        self.assertTrue(passed, metrics)

        approval_data["match_sheet_sha256"] = "0" * 64
        approval.write_text(
            json.dumps(approval_data, ensure_ascii=False), encoding="utf-8"
        )
        render_data = json.loads(
            render_manifest.read_text(encoding="utf-8")
        )
        render_data["approval_sha256"] = file_sha256(approval)
        render_manifest.write_text(
            json.dumps(render_data, ensure_ascii=False), encoding="utf-8"
        )
        passed, _, metrics = run_check(self.root, master_check)
        self.assertFalse(passed)
        self.assertTrue(
            any(
                "approval is not bound to the current match sheet" in item
                for item in metrics["failures"]
            )
        )
        approval_data["match_sheet_sha256"] = file_sha256(
            Path(fixture["match_sheet"])
        )
        approval.write_text(
            json.dumps(approval_data, ensure_ascii=False), encoding="utf-8"
        )
        render_data["approval_sha256"] = file_sha256(approval)
        render_manifest.write_text(
            json.dumps(render_data, ensure_ascii=False), encoding="utf-8"
        )

        output_picture = render_halves(
            "visuals/picture_patched.mp4", "blue", "green"
        )
        before_rows = json.loads(json.dumps(fixture["rows"], ensure_ascii=False))
        after_rows = json.loads(json.dumps(fixture["rows"], ensure_ascii=False))
        after_rows[0]["match_reason"] = "用户反馈后更换第一镜"
        before = self.write_tsv(
            "visuals/snapshots/picture.before.tsv",
            fixture["fields"],
            before_rows,
        )
        after = self.write_tsv(
            "visuals/picture.after.tsv", fixture["fields"], after_rows
        )
        base_frame_hashes = decoded_frame_hashes(base_picture)
        output_frame_hashes = decoded_frame_hashes(output_picture)
        self.assertEqual(len(base_frame_hashes), 10)
        self.assertEqual(len(output_frame_hashes), 10)
        base_segments = self.write_tsv(
            "visuals/base_segments.tsv",
            [
                "line_id",
                "output_start_frame",
                "output_end_frame",
                "segment_sha256",
            ],
            [
                {
                    "line_id": 1,
                    "output_start_frame": 0,
                    "output_end_frame": 5,
                    "segment_sha256": frame_slice_sha256(
                        base_frame_hashes, 0, 5
                    ),
                },
                {
                    "line_id": 2,
                    "output_start_frame": 5,
                    "output_end_frame": 10,
                    "segment_sha256": frame_slice_sha256(
                        base_frame_hashes, 5, 10
                    ),
                },
            ],
        )
        output_segments = self.write_tsv(
            "visuals/output_segments.tsv",
            [
                "line_id",
                "output_start_frame",
                "output_end_frame",
                "segment_sha256",
            ],
            [
                {
                    "line_id": 1,
                    "output_start_frame": 0,
                    "output_end_frame": 5,
                    "segment_sha256": frame_slice_sha256(
                        output_frame_hashes, 0, 5
                    ),
                },
                {
                    "line_id": 2,
                    "output_start_frame": 5,
                    "output_end_frame": 10,
                    "segment_sha256": frame_slice_sha256(
                        output_frame_hashes, 5, 10
                    ),
                },
            ],
        )
        repair_approval = self.write_json(
            "visuals/patches/repair_approval.json",
            {
                "schema_version": 2,
                "status": "PASS",
                "before_match_sheet_sha256": file_sha256(before),
                "after_match_sheet_sha256": file_sha256(after),
                "unresolved_after": [],
                "opening_review": {"status": "PASS"},
                "ending_review": {"status": "PASS"},
            },
        )
        patch_evidence = self.evidence("visuals/patches/cue_001.jpg")
        patch_manifest = self.write_json(
            "visuals/picture_patch_manifest.json",
            {
                "schema_version": 1,
                "status": "PASS",
                "base_picture": {
                    "path": str(base_picture),
                    "sha256": file_sha256(base_picture),
                },
                "output_picture": {
                    "path": str(output_picture),
                    "sha256": file_sha256(output_picture),
                },
                "before_match_sheet_sha256": file_sha256(before),
                "after_match_sheet_sha256": file_sha256(after),
                "base_segment_manifest_sha256": file_sha256(base_segments),
                "output_segment_manifest_sha256": file_sha256(output_segments),
                "repair_approval_sha256": file_sha256(repair_approval),
                "base_approval_sha256": file_sha256(render_manifest),
                "changed_cue_ids": [1],
                "corrections": [
                    {
                        "cue_id": 1,
                        "reason": "用户反馈后的增量修复",
                        "evidence": str(patch_evidence),
                    }
                ],
            },
        )
        patch_check = {
            "type": "picture_patch_integrity",
            "path": str(patch_manifest),
            "before_match_sheet_path": str(before),
            "after_match_sheet_path": str(after),
            "timing_contract_path": str(timing),
            "repair_approval_path": str(repair_approval),
            "base_approval_path": str(render_manifest),
            "base_segment_manifest_path": str(base_segments),
            "output_segment_manifest_path": str(output_segments),
            "verify_decoded_segment_hashes": True,
        }
        passed, _, metrics = run_check(self.root, patch_check)
        self.assertTrue(passed, metrics)

        repair_approval_data = json.loads(
            repair_approval.read_text(encoding="utf-8")
        )
        repair_approval_data["after_match_sheet_sha256"] = "0" * 64
        repair_approval.write_text(
            json.dumps(repair_approval_data, ensure_ascii=False),
            encoding="utf-8",
        )
        patch_manifest_data = json.loads(
            patch_manifest.read_text(encoding="utf-8")
        )
        patch_manifest_data["repair_approval_sha256"] = file_sha256(
            repair_approval
        )
        patch_manifest.write_text(
            json.dumps(patch_manifest_data, ensure_ascii=False),
            encoding="utf-8",
        )
        passed, _, metrics = run_check(self.root, patch_check)
        self.assertFalse(passed)
        self.assertTrue(
            any(
                "repair approval is not bound to after match sheet" in item
                for item in metrics["failures"]
            )
        )
        repair_approval_data["after_match_sheet_sha256"] = file_sha256(after)
        repair_approval.write_text(
            json.dumps(repair_approval_data, ensure_ascii=False),
            encoding="utf-8",
        )
        patch_manifest_data["repair_approval_sha256"] = file_sha256(
            repair_approval
        )
        patch_manifest.write_text(
            json.dumps(patch_manifest_data, ensure_ascii=False),
            encoding="utf-8",
        )

        secretly_changed_picture = render_halves(
            "visuals/picture_patched_secret.mp4", "blue", "yellow"
        )
        patch_manifest_data = json.loads(patch_manifest.read_text(encoding="utf-8"))
        patch_manifest_data["output_picture"] = {
            "path": str(secretly_changed_picture),
            "sha256": file_sha256(secretly_changed_picture),
        }
        patch_manifest.write_text(
            json.dumps(patch_manifest_data, ensure_ascii=False),
            encoding="utf-8",
        )
        patch_check["output_picture_path"] = str(secretly_changed_picture)
        self.write_tsv(
            "visuals/output_segments.tsv",
            [
                "line_id",
                "output_start_frame",
                "output_end_frame",
                "segment_sha256",
            ],
            [
                {
                    "line_id": 1,
                    "output_start_frame": 0,
                    "output_end_frame": 5,
                    "segment_sha256": frame_slice_sha256(
                        output_frame_hashes, 0, 5
                    ),
                },
                {
                    "line_id": 2,
                    "output_start_frame": 5,
                    "output_end_frame": 10,
                    "segment_sha256": frame_slice_sha256(
                        base_frame_hashes, 5, 10
                    ),
                },
            ],
        )
        patch_manifest_data["output_segment_manifest_sha256"] = file_sha256(
            output_segments
        )
        patch_manifest.write_text(
            json.dumps(patch_manifest_data, ensure_ascii=False),
            encoding="utf-8",
        )
        passed, _, metrics = run_check(self.root, patch_check)
        self.assertFalse(passed)
        self.assertTrue(
            any(
                "output segment SHA is not derived" in item
                or "decoded unlisted segment changes" in item
                for item in metrics["failures"]
            )
        )

    def test_empty_music_root_uses_home_music(self) -> None:
        environment = os.environ.copy()
        environment["AI_VIDEO_MUSIC_ROOT"] = ""
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "from harness import MUSIC_SOURCE_ROOT; print(MUSIC_SOURCE_ROOT)",
            ],
            cwd=SCRIPT_DIR,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), str((Path.home() / "Music").resolve()))

    def test_srt_integrity_catches_count_and_coverage(self) -> None:
        reference = self.root / "clean_script.md"
        reference.write_text("你好世界", encoding="utf-8")
        srt = self.root / "captions/test.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\n你好\n\n2\n00:00:01,000 --> 00:00:02,000\n世界\n", encoding="utf-8")
        check = {
            "id": "caption_gate",
            "type": "srt_integrity",
            "path": "captions/test.srt",
            "expected_count": 2,
            "reference_text_path": "clean_script.md",
            "expected_end_seconds": 2.0,
            "end_tolerance_ms": 1,
            "forbidden_terminal_punctuation": list(CAPTION_FORBIDDEN_TERMINAL_PUNCTUATION),
            "terminal_closing_marks": list(CAPTION_TRAILING_CLOSING_MARKS),
        }
        passed, _, metrics = run_check(self.root, check)
        self.assertTrue(passed, metrics)
        check["expected_count"] = 3
        passed, _, _ = run_check(self.root, check)
        self.assertFalse(passed)

    def test_srt_integrity_rejects_forbidden_terminal_punctuation_before_closer(self) -> None:
        reference = self.root / "clean_script.md"
        reference.write_text("「一句话；」真的吗？好！", encoding="utf-8")
        srt = self.root / "captions/terminal-punctuation.srt"
        srt.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n「一句话；」\n\n"
            "2\n00:00:01,000 --> 00:00:02,000\n真的吗？\n\n"
            "3\n00:00:02,000 --> 00:00:03,000\n好！\n",
            encoding="utf-8",
        )
        check = {
            "id": "caption_terminal_gate",
            "type": "srt_integrity",
            "path": "captions/terminal-punctuation.srt",
            "expected_count": 3,
            "reference_text_path": "clean_script.md",
            "expected_end_seconds": 3.0,
            "end_tolerance_ms": 1,
            "forbidden_terminal_punctuation": list(CAPTION_FORBIDDEN_TERMINAL_PUNCTUATION),
            "terminal_closing_marks": list(CAPTION_TRAILING_CLOSING_MARKS),
        }
        passed, _, metrics = run_check(self.root, check)
        self.assertFalse(passed)
        self.assertEqual(
            [entry["entry"] for entry in metrics["forbidden_terminal_punctuation_entries"]],
            [1],
        )

        srt.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n「一句话」\n\n"
            "2\n00:00:01,000 --> 00:00:02,000\n真的吗？\n\n"
            "3\n00:00:02,000 --> 00:00:03,000\n好！\n",
            encoding="utf-8",
        )
        passed, _, metrics = run_check(self.root, check)
        self.assertTrue(passed, metrics)

    def test_caption_actions_require_exact_terminal_punctuation_policy(self) -> None:
        check = {
            "type": "srt_integrity",
            "forbidden_terminal_punctuation": list(CAPTION_FORBIDDEN_TERMINAL_PUNCTUATION),
            "terminal_closing_marks": list(CAPTION_TRAILING_CLOSING_MARKS),
        }
        validate_caption_terminal_punctuation_policy(check)
        for action_key in ("caption_replace_atomic", "caption_canonical_export"):
            self.assertTrue(
                ACTION_REGISTRY[action_key].get("caption_terminal_punctuation_policy_required"),
                action_key,
            )

        check["forbidden_terminal_punctuation"] = ["。"]
        with self.assertRaisesRegex(ValueError, "forbidden_terminal_punctuation"):
            validate_caption_terminal_punctuation_policy(check)

    def test_caption_replace_route_requires_verified_local_subtitle_card_drag(self) -> None:
        steps = [
            {
                "sequence": 1,
                "action": "press",
                "target": self.ui_target(name="文本", identifier="text-panel", visible_text="文本"),
            },
            {
                "sequence": 2,
                "action": "press",
                "target": self.ui_target(name="新建文本", identifier="new-text", visible_text="新建文本"),
            },
            {
                "sequence": 3,
                "action": "press",
                "target": self.ui_target(
                    name="导入本地字幕",
                    identifier="import-local-subtitle",
                    visible_text="导入本地字幕",
                ),
            },
            {
                "sequence": 4,
                "action": "confirm",
                "target": self.ui_target(name="导入", identifier="file-import", visible_text="导入"),
            },
            {
                "sequence": 5,
                "action": "drag",
                "target": self.ui_target(
                    name="修缮版.srt",
                    identifier="local-subtitle-card",
                    visible_text="本地字幕素材卡",
                ),
            },
            {
                "sequence": 6,
                "action": "key_press",
                "target": self.ui_target(
                    name="删除旧字幕轨",
                    identifier="remove-raw-caption-track",
                    visible_text="删除旧字幕轨",
                ),
            },
            {
                "sequence": 7,
                "action": "press",
                "target": self.ui_target(name="导出", identifier="open-export", visible_text="导出"),
            },
            {
                "sequence": 8,
                "action": "press",
                "target": self.ui_target(
                    name="字幕导出",
                    identifier="caption-export",
                    visible_text="字幕导出",
                ),
            },
            {
                "sequence": 9,
                "action": "confirm",
                "target": self.ui_target(
                    name="确认导出",
                    identifier="confirm-export",
                    visible_text="确认导出",
                ),
            },
        ]
        checkpoints = ACTION_REGISTRY["caption_replace_atomic"]["ui_required_step_checkpoints"]
        matches = validate_required_ui_route_checkpoints(steps, checkpoints)
        self.assertEqual(
            [match["checkpoint"] for match in matches],
            [checkpoint["name"] for checkpoint in checkpoints],
        )

        unsafe_steps = json.loads(json.dumps(steps, ensure_ascii=False))
        unsafe_steps[4]["action"] = "press"
        with self.assertRaisesRegex(ValueError, "drag_local_subtitle_card"):
            validate_required_ui_route_checkpoints(unsafe_steps, checkpoints)

    def test_caption_transaction_requires_import_before_old_track_removal(self) -> None:
        raw = self.root / "captions/raw.srt"
        canonical = self.root / "captions/canonical.srt"
        raw.write_text("1\n00:00:00,000 --> 00:00:01,000\n原始\n", encoding="utf-8")
        canonical.write_text("1\n00:00:00,000 --> 00:00:01,000\n语义\n", encoding="utf-8")
        transaction = self.write_json(
            "caption-transaction.json",
            {
                "events": [
                    "raw_backup_verified",
                    "semantic_srt_audited",
                    "local_subtitle_card_verified",
                    "semantic_track_dragged_verified",
                    "raw_track_removed",
                    "canonical_exported",
                ],
                "caption_track_counts": [1, 1, 2, 1],
                "exact_overlap_count": 0,
                "final_caption_count": 1,
                "raw_backup": str(raw),
                "imported_srt": str(canonical),
                "local_subtitle_card_name": canonical.name,
                "canonical_export": str(canonical),
                "subtitle_export_settings": {
                    "video_export": False,
                    "audio_export": False,
                    "caption_export": True,
                    "format": "SRT",
                    "encoding": "Unicode / UTF-8",
                },
            },
        )
        result = validate_caption_transaction(transaction, 1)
        self.assertEqual(result["caption_track_counts"], [1, 1, 2, 1])

        unsafe = json.loads(transaction.read_text(encoding="utf-8"))
        unsafe["caption_track_counts"] = [1, 0, 2, 1]
        transaction.write_text(json.dumps(unsafe), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "safe track counts"):
            validate_caption_transaction(transaction, 1)

    def test_indexed_visual_actions_use_specialized_checks_and_limits(self) -> None:
        contract = json.loads(
            (self.root / "request_contract.json").read_text(encoding="utf-8")
        )
        expected_limits = {
            "visual_indexes_per_batch",
            "match_plans_per_batch",
            "match_review_bundles_per_batch",
            "match_repair_sets_per_batch",
            "picture_masters_per_batch",
            "picture_patches_per_batch",
        }
        self.assertEqual(
            {key for key in expected_limits if contract["unit_limits"].get(key) == 1},
            expected_limits,
        )
        expected_actions = {
            "build_visual_index": "visual_index_integrity",
            "build_match_plan": "visual_match_plan_integrity",
            "review_match_plan": "visual_selection_review_integrity",
            "repair_match_plan": "visual_match_repair_integrity",
            "render_picture_master": "picture_master_integrity",
            "patch_picture_master": "picture_patch_integrity",
        }
        visual_template = json.loads(
            (
                self.root
                / "visuals/indexed_bulk_checks.template.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            len(visual_template.get("checks", [])),
            6,
        )
        for action_key, check_type in expected_actions.items():
            self.assertEqual(
                ACTION_REGISTRY[action_key]["allowed_primary_types"],
                [check_type],
            )
        self.assertIs(
            ACTION_REGISTRY["patch_picture_master"][
                "required_primary_config_values"
            ]["verify_decoded_segment_hashes"],
            True,
        )
        match_plan_config = ACTION_REGISTRY["build_match_plan"][
            "required_primary_config_values"
        ]
        self.assertEqual(match_plan_config["required_qa_status"], "machine_proposed")
        self.assertEqual(match_plan_config["preferred_pool_candidates"], 32)
        self.assertIs(
            match_plan_config["require_candidate_shortfall_evidence"],
            True,
        )

        plan_path = self.root / "verification_plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["checks"].extend(
            [
                {
                    "id": "visual_index_gate",
                    "type": "visual_index_integrity",
                    "path": "visuals/shot_index.tsv",
                    "ocr_index_path": "visuals/shot_ocr_index.tsv",
                    "source_manifest_path": "visuals/source_identity_manifest.json",
                    "contact_sheet_manifest_path": "visuals/contact_sheets/manifest.json",
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
                    "id": "disguised_visual",
                    "type": "file_nonempty",
                    "path": "visuals/plan.tsv",
                    "observes_mutations": ["offline.artifact"],
                    "observed_targets": ["visuals/plan.tsv"],
                },
                {
                    "id": "patch_without_decoded_proof",
                    "type": "picture_patch_integrity",
                    "path": "visuals/patches/patch_manifest.json",
                    "before_match_sheet_path": "visuals/snapshots/before.tsv",
                    "after_match_sheet_path": "visuals/match_sheet.tsv",
                    "timing_contract_path": "visuals/timing_contract.json",
                    "repair_approval_path": "visuals/repairs/approval.json",
                    "base_approval_path": "visuals/render_manifest.json",
                    "base_picture_path": "visuals/picture_base.mp4",
                    "output_picture_path": "visuals/picture_patch.mp4",
                    "require_segment_manifests": True,
                    "check_black_frames": True,
                    "verify_decoded_segment_hashes": False,
                    "observes_mutations": ["offline.picture.patch"],
                    "observed_targets": [
                        "visuals/patches/picture_only.mp4",
                        "visuals/patches/patch_manifest.json",
                    ],
                },
                {
                    "id": "benign_notes",
                    "type": "file_nonempty",
                    "path": "qa/notes.txt",
                    "observes_mutations": ["offline.artifact"],
                    "observed_targets": ["qa/notes.txt"],
                },
            ]
        )
        plan_path.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        rebound = self.run_command(
            HARNESS,
            "rebind",
            self.root,
            "--authorized-by",
            "user",
            "--reason",
            "测试 indexed bulk 视觉动作",
        )
        self.assertEqual(rebound.returncode, 0, rebound.stderr)

        generic = self.run_command(
            HARNESS,
            "prepare",
            self.root,
            "--action-key",
            "offline_artifact",
            "--recipe-id",
            "offline.objective-check.v1",
            "--assumption",
            "试图把整表伪装成普通离线文件",
            "--scope",
            "visuals/plan.tsv",
            "--unit-limit-key",
            "offline_artifacts_per_batch",
            "--unit-count",
            1,
            "--check-id",
            "disguised_visual",
        )
        self.assertEqual(generic.returncode, 2)
        self.assertIn("cannot mutate indexed-bulk visual targets", generic.stderr)

        scope_bypass = self.run_command(
            HARNESS,
            "prepare",
            self.root,
            "--action-key",
            "offline_artifact",
            "--recipe-id",
            "offline.objective-check.v1",
            "--assumption",
            "用普通 notes 检查掩护视觉写入",
            "--scope",
            "visuals/x.tsv",
            "--unit-limit-key",
            "offline_artifacts_per_batch",
            "--unit-count",
            1,
            "--check-id",
            "benign_notes",
        )
        self.assertEqual(scope_bypass.returncode, 2)
        self.assertIn(
            "cannot mutate indexed-bulk visual targets",
            scope_bypass.stderr,
        )

        weak_patch = self.run_command(
            HARNESS,
            "prepare",
            self.root,
            "--action-key",
            "patch_picture_master",
            "--recipe-id",
            "offline.picture-master-incremental-patch.v1",
            "--assumption",
            "仅信任 TSV 中自报的片段哈希",
            "--scope",
            "一个画面补丁",
            "--unit-limit-key",
            "picture_patches_per_batch",
            "--unit-count",
            1,
            "--check-id",
            "patch_without_decoded_proof",
        )
        self.assertEqual(weak_patch.returncode, 2)
        self.assertIn("verify_decoded_segment_hashes=False", weak_patch.stderr)

        wrong_limit = self.run_command(
            HARNESS,
            "prepare",
            self.root,
            "--action-key",
            "build_visual_index",
            "--recipe-id",
            "offline.indexed-vision-ocr-corpus.v1",
            "--assumption",
            "索引包可验证",
            "--scope",
            "一个完整视觉索引",
            "--unit-limit-key",
            "offline_artifacts_per_batch",
            "--unit-count",
            1,
            "--check-id",
            "visual_index_gate",
        )
        self.assertEqual(wrong_limit.returncode, 2)
        self.assertIn("requires unit limit key visual_indexes_per_batch", wrong_limit.stderr)

        prepared = self.run_command(
            HARNESS,
            "prepare",
            self.root,
            "--action-key",
            "build_visual_index",
            "--recipe-id",
            "offline.indexed-vision-ocr-corpus.v1",
            "--assumption",
            "索引包可验证",
            "--scope",
            "一个完整视觉索引",
            "--unit-limit-key",
            "visual_indexes_per_batch",
            "--unit-count",
            1,
            "--check-id",
            "visual_index_gate",
        )
        self.assertEqual(prepared.returncode, 0, prepared.stderr)

    def test_generation_binding_selects_matching_newer_prerequisite(
        self,
    ) -> None:
        render_primary = {
            "approval_path": "visuals/repair_new.json",
            "match_sheet_path": "visuals/match_new.tsv",
        }
        render_results = [
            {
                "attempts": [
                    {
                        "check_id": "review_old",
                        "type": "visual_selection_review_integrity",
                        "check_config": {
                            "path": "visuals/review_old.json",
                            "match_sheet_path": "visuals/match_old.tsv",
                        },
                        "pass": True,
                        "required_metric_failures": [],
                    },
                    {
                        "check_id": "repair_new",
                        "type": "visual_match_repair_integrity",
                        "check_config": {
                            "path": "visuals/repair_new.json",
                            "after_match_sheet_path": "visuals/match_new.tsv",
                        },
                        "pass": True,
                        "required_metric_failures": [],
                    },
                ],
                "selected": {},
            }
        ]
        validate_prerequisite_config_bindings(
            self.root,
            render_primary,
            render_results,
            ACTION_REGISTRY["render_picture_master"][
                "prerequisite_config_bindings"
            ],
        )
        self.assertEqual(
            render_results[0]["selected"]["check_id"], "repair_new"
        )

        patch_primary = {
            "base_approval_path": "visuals/patch_1.json",
            "base_picture_path": "visuals/picture_1.mp4",
        }
        patch_results = [
            {
                "attempts": [
                    {
                        "check_id": "master_0",
                        "type": "picture_master_integrity",
                        "check_config": {
                            "path": "visuals/picture_0.mp4",
                            "manifest_path": "visuals/render_0.json",
                        },
                        "pass": True,
                        "required_metric_failures": [],
                    },
                    {
                        "check_id": "patch_1",
                        "type": "picture_patch_integrity",
                        "check_config": {
                            "path": "visuals/patch_1.json",
                            "output_picture_path": "visuals/picture_1.mp4",
                        },
                        "pass": True,
                        "required_metric_failures": [],
                    },
                ],
                "selected": {},
            }
        ]
        patch_bindings = [
            binding
            for binding in ACTION_REGISTRY["patch_picture_master"][
                "prerequisite_config_bindings"
            ]
            if binding["type"]
            in {"picture_master_integrity", "picture_patch_integrity"}
        ]
        validate_prerequisite_config_bindings(
            self.root,
            patch_primary,
            patch_results,
            patch_bindings,
        )
        self.assertEqual(
            patch_results[0]["selected"]["check_id"], "patch_1"
        )


if __name__ == "__main__":
    unittest.main()
