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

    def prepare_rename(self, expected_name: str = "新草稿") -> str:
        pre = self.write_json("pre.json", observation())
        pre_evidence = self.evidence("pre.png")
        completed = self.run_command(
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
            "--expect",
            f"draft_name={expected_name}",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        state = json.loads((self.root / "harness/state.json").read_text(encoding="utf-8"))
        return state["open_action"]["token"]

    def test_live_action_passes_only_after_exact_delta(self) -> None:
        token = self.prepare_rename()
        first = self.run_command(HARNESS, "begin", self.root, "--token", token)
        self.assertEqual(first.returncode, 0, first.stderr)
        repeated = self.run_command(HARNESS, "begin", self.root, "--token", token)
        self.assertEqual(repeated.returncode, 2)

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
