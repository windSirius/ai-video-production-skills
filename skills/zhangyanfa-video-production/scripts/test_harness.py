#!/usr/bin/env python3
"""Regression tests for the production transaction harness."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from run_objective_checks import run_check
from harness import ACTION_REGISTRY, SCHEMA_VERSION, UI_ROUTE_SCHEMA_VERSION, fingerprint, sha256_file, utc_now


INIT = SCRIPT_DIR / "init_run.py"
HARNESS = SCRIPT_DIR / "harness.py"
VALIDATE = SCRIPT_DIR / "validate_run.py"


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
        path.write_bytes((name * 8).encode("utf-8"))
        return path

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
        }
        passed, _, metrics = run_check(self.root, check)
        self.assertTrue(passed, metrics)
        check["expected_count"] = 3
        passed, _, _ = run_check(self.root, check)
        self.assertFalse(passed)


if __name__ == "__main__":
    unittest.main()
